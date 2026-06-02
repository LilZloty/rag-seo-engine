"""
Phase 2.1 smoke test: run product_enrichment_service.enrich_product on one or
more SKUs and print the result.

Default: dry-run on the two anchor SKUs (K79900, K119AF).

Usage from backend/:
    python -m scripts.test_product_tldr
    python -m scripts.test_product_tldr --skus K79900,K119AF
    python -m scripts.test_product_tldr --skus K79900 --live
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

from app.db.session import SessionLocal
from app.models.product import Product
from app.services.product_enrichment_service import product_enrichment_service


async def main_async() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skus",
        default="K79900,K119AF",
        help="Comma-separated SKUs to test (default: K79900,K119AF)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Actually write the metafield to Shopify (default: dry-run)",
    )
    args = parser.parse_args()

    sku_list = [s.strip() for s in args.skus.split(",") if s.strip()]

    db = SessionLocal()
    try:
        products = db.query(Product).filter(Product.sku.in_(sku_list)).all()
    finally:
        db.close()

    if not products:
        print(f"No products found for SKUs: {sku_list}")
        return

    for p in products:
        print(f"\n{'=' * 78}")
        print(f"SKU:   {p.sku}")
        print(f"Title: {p.title}")
        print(f"Mode:  {'LIVE' if args.live else 'DRY-RUN'}")
        print(f"{'=' * 78}")
        result = await product_enrichment_service.enrich_product(
            product_id=p.id,
            dry_run=not args.live,
        )

        tldr = result.get("tldr_summary", "")
        print(f"\nTL;DR ({len(tldr)} chars):")
        print(f"  {tldr}")
        faqs = result.get("faqs") or []
        print(f"\nFAQs ({len(faqs)}):")
        for i, faq in enumerate(faqs, 1):
            print(f"  Q{i}: {faq.get('q', '')}")
            a = faq.get('a', '')
            print(f"  A{i}: {a[:280]}{'...' if len(a) > 280 else ''}")
            print()
        print(f"Confidence: {result.get('confidence')}")
        print(f"Written:    {result.get('written')}  (skip_reason={result.get('skip_reason')!r})")
        warnings = result.get("warnings") or []
        if warnings:
            print(f"Warnings:")
            for w in warnings:
                print(f"  - {w}")
        signals = result.get("source_signals") or {}
        print(f"Source signals: {json.dumps(signals, ensure_ascii=False)}")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
