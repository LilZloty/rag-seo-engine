"""
Seed AI Visibility test queries from AI_CITATION_TEST_PLAYBOOK.md.

These are the 12 starter queries used to track Example Store's citation footprint
across Claude, ChatGPT, Perplexity, Grok and other LLM providers.

The queries are inserted into `PromptPanelItem` table and consumed by
`AIVisibilityService.batch_check_visibility()`.

Usage:
    # Dry-run (default — prints what would be inserted, no DB writes)
    python -m scripts.seed_aeo_test_queries

    # Live insert
    python -m scripts.seed_aeo_test_queries --live

    # Re-activate previously-inserted queries that got deactivated
    python -m scripts.seed_aeo_test_queries --live --reactivate

Idempotent — safe to re-run. Skips queries whose `prompt_text` already exists.
Linked to: AI_CITATION_TEST_PLAYBOOK.md (project root), source="playbook".
"""

from __future__ import annotations

import argparse
import logging
from typing import Optional

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

from app.db.session import SessionLocal
from app.models.aeo_models import PromptPanelItem


# (prompt_text, category, priority, linked_fault_code, linked_transmission)
# - category: fault_code | product | competitor | general
# - priority: 0-100, higher = more important
# - linked_fault_code / linked_transmission: optional FK / tag for slicing
QUERIES: list[tuple[str, str, int, Optional[str], Optional[str]]] = [
    # === Spanish — primary market (8) ===
    (
        "Dónde comprar kit de empaques transmisión 4L60E en México",
        "product", 90, None, "4L60E",
    ),
    (
        "Mejor distribuidor de Sonnax en México",
        "competitor", 85, None, None,
    ),
    (
        "Necesito Transgo shift kit 4L60E, ¿dónde lo encuentro en México?",
        "product", 90, None, "4L60E",
    ),
    (
        "Aceite ATF Dexron VI para Cadillac Escalade en México",
        "product", 75, None, None,
    ),
    (
        "Síntomas código P0740 y qué refacciones cambiar",
        "fault_code", 80, "P0740", None,
    ),
    (
        "Tienda de refacciones transmisión automática tu ciudad",
        "general", 70, None, None,
    ),
    (
        "¿Cuál es el mejor kit de empaques para transmisión 4EAT-F en una Ford Escort 1994 en México? Necesito el OEM Freudenberg-NOK.",
        "product", 85, None, "4EAT-F",
    ),
    (
        "Cómo identificar fallas en transmisión automática Chrysler 45RFE",
        "product", 75, None, "45RFE",
    ),

    # === English — secondary (2) ===
    (
        "Where to buy Sonnax 4L60E shift kit in Mexico",
        "product", 70, None, "4L60E",
    ),
    (
        "Mexican supplier for Freudenberg transmission gaskets",
        "general", 70, None, None,
    ),

    # === Specific SKU — worst-case stress test (2) ===
    (
        "TransTec 2265 distribuidor México",
        "product", 80, None, "4EAT-F",
    ),
    (
        "Sonnax 144740-16K en México",
        "product", 80, None, None,
    ),
]

SOURCE_TAG = "playbook"


def find_existing(db, prompt_text: str) -> Optional[PromptPanelItem]:
    """Return existing PromptPanelItem matching this exact prompt_text, or None."""
    return db.query(PromptPanelItem).filter(
        PromptPanelItem.prompt_text == prompt_text
    ).first()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true",
        help="Actually write to DB. Default is dry-run (no writes).",
    )
    parser.add_argument(
        "--reactivate", action="store_true",
        help="If a matching prompt exists but is inactive, set is_active=True.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        print(f"\n{'=' * 70}")
        print(f"SEED AI VISIBILITY TEST QUERIES  ({'LIVE' if args.live else 'DRY-RUN'})")
        print(f"{'=' * 70}\n")
        print(f"Source tag:    {SOURCE_TAG}")
        print(f"Total queries: {len(QUERIES)}\n")

        active_before = db.query(PromptPanelItem).filter(
            PromptPanelItem.is_active == True
        ).count()
        print(f"Active PromptPanelItem rows BEFORE: {active_before}\n")

        new_count = 0
        skip_count = 0
        reactivate_count = 0

        for prompt_text, category, priority, fault_code, transmission in QUERIES:
            existing = find_existing(db, prompt_text)

            if existing is None:
                # Net-new prompt
                new_count += 1
                tag = "[INSERT]" if args.live else "[INSERT (dry-run)]"
                print(f"{tag} cat={category:12s} pri={priority:3d}  {prompt_text[:80]}")
                if args.live:
                    item = PromptPanelItem(
                        prompt_text=prompt_text,
                        category=category,
                        priority=priority,
                        linked_fault_code=fault_code,
                        linked_transmission=transmission,
                        source=SOURCE_TAG,
                        is_active=True,
                    )
                    db.add(item)
            elif args.reactivate and not existing.is_active:
                reactivate_count += 1
                tag = "[REACTIVATE]" if args.live else "[REACTIVATE (dry-run)]"
                print(f"{tag} id={existing.id} {prompt_text[:80]}")
                if args.live:
                    existing.is_active = True
            else:
                skip_count += 1
                status = "active" if existing.is_active else "inactive"
                print(f"[SKIP    ] id={existing.id} ({status}) {prompt_text[:80]}")

        if args.live and (new_count > 0 or reactivate_count > 0):
            db.commit()
            print("\nDB commit OK.")

        active_after = db.query(PromptPanelItem).filter(
            PromptPanelItem.is_active == True
        ).count()

        print(f"\n{'=' * 70}")
        print("SUMMARY")
        print(f"{'=' * 70}")
        print(f"  Inserted:    {new_count}")
        print(f"  Reactivated: {reactivate_count}")
        print(f"  Skipped:     {skip_count}")
        print(f"  Active PromptPanelItem rows AFTER:  {active_after}")
        print(f"  Net delta:                          +{active_after - active_before}")

        if not args.live:
            print("\n[DRY-RUN] No changes written. Re-run with --live to apply.")
        else:
            print("\n✓ Seed complete. Next steps:")
            print("  1. View prompts in /aeo dashboard")
            print("  2. Run a batch visibility check (manually first):")
            print("     AIVisibilityService().batch_check_visibility(")
            print("         db,")
            print("         provider_names=['anthropic', 'openai', 'perplexity', 'grok'],")
            print("     )")
            print("  3. Inspect results in AIVisibilityResult table")
            print("  4. Set up nightly scheduled run (see ops/cron docs)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
