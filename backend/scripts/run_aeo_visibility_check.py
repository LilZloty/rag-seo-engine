"""
Run a visibility check against the AI_CITATION_TEST_PLAYBOOK.md queries.

Calls each configured LLM provider for each playbook prompt and records:
- brand_mentioned (Example Store mentioned in response)
- url_cited (example-store.com URL in response)
- mentioned_brands / mentioned_urls / mentioned_products
- competitor_mentioned + which competitors

Results land in AIVisibilityResult table. Summary printed after.

Usage:
    # Dry-run (counts only, no LLM calls)
    python -m scripts.run_aeo_visibility_check

    # Run with default safe provider (grok)
    python -m scripts.run_aeo_visibility_check --live

    # Run with multiple providers
    python -m scripts.run_aeo_visibility_check --live --providers grok anthropic

    # Run with all main providers (costs more API credits)
    python -m scripts.run_aeo_visibility_check --live --all

    # Run against ALL prompts (not just playbook source)
    python -m scripts.run_aeo_visibility_check --live --all-prompts

Note: batch_check_visibility() respects temperature=0 for reproducibility
and limits max_concurrent=3 to avoid rate limits.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from typing import List

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.db.session import SessionLocal
from app.models.aeo_models import PromptPanelItem, AIVisibilityResult
from app.services.ai_visibility_service import AIVisibilityService

SOURCE_TAG = "playbook"

DEFAULT_PROVIDER = "grok"  # Memory: Grok is the production-tested provider
ALL_PROVIDERS = ["anthropic", "openai", "perplexity", "grok"]


async def run(args) -> None:
    db = SessionLocal()
    try:
        # Get prompts to check
        query = db.query(PromptPanelItem).filter(PromptPanelItem.is_active == True)
        if not args.all_prompts:
            query = query.filter(PromptPanelItem.source == SOURCE_TAG)
        prompts = query.order_by(PromptPanelItem.priority.desc()).all()

        providers: List[str] = ALL_PROVIDERS if args.all else args.providers

        print(f"\n{'=' * 70}")
        print(f"AEO VISIBILITY CHECK  ({'LIVE' if args.live else 'DRY-RUN'})")
        print(f"{'=' * 70}\n")
        print(f"Prompts source filter: {'all-active' if args.all_prompts else SOURCE_TAG}")
        print(f"Prompts to check:      {len(prompts)}")
        print(f"Providers:             {providers}")
        print(f"Total LLM calls:       {len(prompts) * len(providers)}")
        print(f"Concurrency limit:     3 simultaneous calls")
        print(f"Timeout per call:      60s")
        print()

        if not args.live:
            for i, p in enumerate(prompts, 1):
                tag = f"#{i}"
                trans = p.linked_transmission or "-"
                fc = p.linked_fault_code or "-"
                print(f"  {tag:4s} id={p.id:3d} pri={p.priority:3d} cat={p.category:12s} trans={trans:8s} fc={fc:6s}")
                print(f"        {p.prompt_text[:90]}")
            print(f"\n[DRY-RUN] No LLM calls made. Re-run with --live.")
            return

        # Live run — use max_concurrent=1 to avoid shared-session conflicts
        # (SQLAlchemy Session is NOT async-safe when multiple coroutines
        # db.add/commit concurrently on the same instance)
        svc = AIVisibilityService()
        start = time.time()
        result = await svc.batch_check_visibility(
            db,
            prompt_ids=[p.id for p in prompts],
            provider_names=providers,
            max_concurrent=1,
            timeout_per_check=90,
        )
        elapsed = time.time() - start

        # Safely stringify result (avoid emoji crash on Windows cp1252)
        result_safe = str(result).encode("ascii", errors="replace").decode("ascii")

        print(f"\n{'=' * 70}")
        print("BATCH COMPLETE")
        print(f"{'=' * 70}\n")
        print(f"Elapsed: {elapsed:.1f}s")
        print(f"Returned: {result_safe}\n")

        # Re-query the freshest results for these prompts
        prompt_ids = [p.id for p in prompts]
        results = (
            db.query(AIVisibilityResult)
            .filter(AIVisibilityResult.prompt_id.in_(prompt_ids))
            .order_by(AIVisibilityResult.id.desc())
            .limit(len(prompts) * len(providers))
            .all()
        )

        # ---- Per-provider summary ----
        print("=" * 70)
        print("RESULTS BY PROVIDER")
        print("=" * 70)
        by_provider: dict[str, dict] = {}
        for r in results:
            d = by_provider.setdefault(
                r.llm_provider,
                {"total": 0, "brand": 0, "url": 0, "comp": 0, "err": 0},
            )
            d["total"] += 1
            if r.brand_mentioned:
                d["brand"] += 1
            if r.url_cited:
                d["url"] += 1
            if r.competitor_mentioned:
                d["comp"] += 1
            if r.error:
                d["err"] += 1

        for provider, d in sorted(by_provider.items()):
            print(f"\n  {provider}:")
            print(f"    Total checks:        {d['total']}")
            print(f"    Brand mentioned:     {d['brand']}/{d['total']} ({d['brand']/max(d['total'],1)*100:.0f}%)")
            print(f"    URL cited:           {d['url']}/{d['total']} ({d['url']/max(d['total'],1)*100:.0f}%)")
            print(f"    Competitor mentions: {d['comp']}/{d['total']}")
            print(f"    Errors:              {d['err']}")

        # ---- Per-prompt summary ----
        print(f"\n{'=' * 70}")
        print("RESULTS BY PROMPT (newest result per provider)")
        print("=" * 70)
        # Build {(prompt_id, provider): newest_result}
        newest: dict[tuple[int, str], AIVisibilityResult] = {}
        for r in results:
            key = (r.prompt_id, r.llm_provider)
            if key not in newest:
                newest[key] = r

        for p in prompts:
            print(f"\n  id={p.id} pri={p.priority} [{p.category}]")
            print(f"  {p.prompt_text[:100]}")
            for provider in providers:
                r = newest.get((p.id, provider))
                if not r:
                    print(f"    {provider:12s}: (no result)")
                    continue
                if r.error:
                    print(f"    {provider:12s}: ERROR: {r.error[:60]}")
                    continue
                signals = []
                if r.brand_mentioned:
                    signals.append("BRAND✓")
                if r.url_cited:
                    signals.append("URL✓")
                if r.competitor_mentioned:
                    competitors = r.mentioned_brands or []
                    signals.append(f"COMP({','.join(competitors[:3])})")
                if not signals:
                    signals = ["—no mention—"]
                print(f"    {provider:12s}: {' '.join(signals)}")

        print(f"\n{'=' * 70}")
        print("DONE. Review full responses in AIVisibilityResult.response_text via /aeo dashboard.")
        print("=" * 70)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true",
        help="Actually make LLM API calls. Default is dry-run.",
    )
    parser.add_argument(
        "--providers", nargs="+", default=[DEFAULT_PROVIDER],
        help=f"Providers to query. Default: {DEFAULT_PROVIDER}",
    )
    parser.add_argument(
        "--all", action="store_true",
        help=f"Use all major providers: {ALL_PROVIDERS}",
    )
    parser.add_argument(
        "--all-prompts", action="store_true",
        help="Check all active prompts (not just playbook source).",
    )
    args = parser.parse_args()

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
