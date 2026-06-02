"""
Phase 1.3: push Product.transmission_codes from the DB to the Shopify list
metafield `custom.transmission_codes`. This is what makes the multi-code data
LLM-visible via JSON-LD `additionalProperty` (the theme already loops over
the list metafield as of the Phase 1.2 commit).

Usage (from backend/):

    # Staged: anchor SKUs only, live push
    python -m scripts.push_transmission_metafields --skus K79900,K119AF

    # Dry-run: print intended writes without calling Shopify
    python -m scripts.push_transmission_metafields --skus K79900,K119AF --dry-run

    # Top-100 by GSC impressions
    python -m scripts.push_transmission_metafields --order-by impressions --limit 100

    # Full eligible backfill
    python -m scripts.push_transmission_metafields

Idempotent — re-running just re-writes the same value (Shopify treats it as
no-op when value+type haven't changed).
"""

from __future__ import annotations

import argparse
import logging
import time
from typing import List

from sqlalchemy.orm import Session

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

from app.db.session import SessionLocal
from app.models.product import Product
from app.services.shopify_service import shopify_service


def fetch_products(
    db: Session,
    skus: List[str] | None,
    order_by: str,
    limit: int | None,
) -> List[Product]:
    query = db.query(Product).filter(Product.transmission_codes.isnot(None))
    if skus:
        query = query.filter(Product.sku.in_(skus))
    if order_by == "impressions":
        query = query.order_by(Product.gsc_impressions.desc().nullslast())
    elif order_by == "sku":
        query = query.order_by(Product.sku.asc())
    if limit:
        query = query.limit(limit)
    return query.all()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skus",
        help="Comma-separated SKUs to push (default: all products with transmission_codes)",
    )
    parser.add_argument(
        "--order-by",
        choices=["impressions", "sku", "none"],
        default="impressions",
        help="Sort order when --skus is not provided",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Cap on number of products to process (applied after --order-by)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print intended writes; do NOT call Shopify",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Seconds between Shopify writes (rate-limit headroom, default 0.5)",
    )
    args = parser.parse_args()

    sku_list = None
    if args.skus:
        sku_list = [s.strip() for s in args.skus.split(",") if s.strip()]

    db = SessionLocal()
    try:
        products = fetch_products(db, sku_list, args.order_by, args.limit)
    finally:
        db.close()

    print(f"\n{'=' * 70}")
    print(f"TRANSMISSION_CODES METAFIELD PUSH  -  Phase 1.3")
    print(f"{'=' * 70}\n")
    print(f"Mode:              {'DRY-RUN' if args.dry_run else 'LIVE'}")
    print(f"Filter:            "
          f"{('skus=' + ','.join(sku_list)) if sku_list else f'order_by={args.order_by}'}"
          f"{(' limit=' + str(args.limit)) if args.limit else ''}")
    print(f"Eligible products: {len(products)}")
    print(f"Delay per call:    {args.delay}s")
    print()

    if not products:
        print("No products match the criteria. Did backfill_transmission_codes.py run?")
        return

    successes = 0
    failures = 0
    skipped = 0
    failed_skus: List[str] = []

    for i, p in enumerate(products, 1):
        codes = p.transmission_codes or []
        if not codes:
            skipped += 1
            continue
        if not p.shopify_id:
            print(f"  [{i}/{len(products)}] SKIP: {p.sku!r} has no shopify_id")
            skipped += 1
            continue

        prefix = f"  [{i}/{len(products)}] {p.sku or '(no sku)':<14} shopify={p.shopify_id}"

        if args.dry_run:
            print(f"{prefix}  WOULD WRITE codes={codes}")
            successes += 1
            continue

        ok = shopify_service.update_product_seo_metafields(
            p.shopify_id,
            {"transmission_codes": codes},
        )
        if ok:
            successes += 1
            print(f"{prefix}  OK codes={codes}")
        else:
            failures += 1
            failed_skus.append(p.sku or "(no sku)")
            print(f"{prefix}  FAIL codes={codes}")

        if i < len(products):
            time.sleep(args.delay)

    print(f"\n{'=' * 70}")
    print(f"Pushed:    {successes}")
    print(f"Failed:    {failures}")
    print(f"Skipped:   {skipped}")
    if failed_skus:
        print(f"Failed SKUs: {failed_skus[:20]}{'...' if len(failed_skus) > 20 else ''}")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
