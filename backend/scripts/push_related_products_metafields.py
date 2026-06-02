"""
Phase 2.2: push Product.top_companions to the Shopify list.product_reference
metafield `custom.related_products`. The theme then emits each entry as
schema.org/isRelatedTo in Product JSON-LD, exposing the co-purchase bundle
pattern to AI shopping and agentic commerce protocols.

Top_companions is derived from real order history (frequently-bought-together
pairs) — already populated on ~40% of the catalog. This script just surfaces
the data to a new external surface (Shopify metafield + JSON-LD).

Usage (from backend/):

    # Staged: anchor SKUs only, live push
    python -m scripts.push_related_products_metafields --skus K79900,K119AF

    # Dry-run
    python -m scripts.push_related_products_metafields --skus K79900,K119AF --dry-run

    # Top-100 by anchor_score
    python -m scripts.push_related_products_metafields --order-by anchor_score --limit 100

    # Full catalog with top_companions populated
    python -m scripts.push_related_products_metafields

Idempotent — Shopify treats same-value writes as no-ops.
"""

from __future__ import annotations

import argparse
import logging
import time
from typing import List, Optional

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.product import Product
from app.services.shopify_service import shopify_service


def extract_companion_ids(top_companions, max_count: int = 5) -> List[str]:
    """Pull up to max_count shopify_ids from a top_companions JSON column."""
    if not top_companions:
        return []
    ids: List[str] = []
    for entry in top_companions[:max_count]:
        if not isinstance(entry, dict):
            continue
        sid = entry.get("shopify_id")
        if sid is None:
            continue
        bare = str(sid).strip()
        if bare and bare.isdigit():
            ids.append(bare)
    return ids


def fetch_products(
    db: Session,
    skus: Optional[List[str]],
    order_by: str,
    limit: Optional[int],
) -> List[Product]:
    query = db.query(Product).filter(Product.top_companions.isnot(None))
    if skus:
        query = query.filter(Product.sku.in_(skus))
    if order_by == "anchor_score":
        query = query.order_by(Product.anchor_score.desc().nullslast())
    elif order_by == "co_purchase_count":
        query = query.order_by(Product.co_purchase_count.desc().nullslast())
    elif order_by == "sku":
        query = query.order_by(Product.sku.asc())
    if limit:
        query = query.limit(limit)
    return query.all()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skus",
        help="Comma-separated SKUs (default: all with top_companions populated)",
    )
    parser.add_argument(
        "--order-by",
        choices=["anchor_score", "co_purchase_count", "sku", "none"],
        default="anchor_score",
        help="Sort order when --skus is not provided",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Cap on number of products to process",
    )
    parser.add_argument(
        "--max-companions",
        type=int,
        default=5,
        help="Max companion products to emit per product (default 5)",
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
        help="Seconds between Shopify writes",
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
    print("RELATED_PRODUCTS METAFIELD PUSH  -  Phase 2.2")
    print(f"{'=' * 70}\n")
    print(f"Mode:              {'DRY-RUN' if args.dry_run else 'LIVE'}")
    print(f"Filter:            "
          f"{('skus=' + ','.join(sku_list)) if sku_list else f'order_by={args.order_by}'}"
          f"{(' limit=' + str(args.limit)) if args.limit else ''}")
    print(f"Eligible products: {len(products)}")
    print(f"Max companions:    {args.max_companions}")
    print()

    if not products:
        print("No products with top_companions populated. Did the co-purchase compute run?")
        return

    successes = 0
    failures = 0
    skipped = 0
    failed_skus: List[str] = []

    for i, p in enumerate(products, 1):
        companion_ids = extract_companion_ids(p.top_companions, args.max_companions)
        prefix = f"  [{i}/{len(products)}] {p.sku or '(no sku)':<14} shopify={p.shopify_id}"

        if not companion_ids:
            print(f"{prefix}  SKIP (no usable companion shopify_ids)")
            skipped += 1
            continue
        if not p.shopify_id:
            print(f"{prefix}  SKIP (no shopify_id)")
            skipped += 1
            continue

        if args.dry_run:
            print(f"{prefix}  WOULD WRITE {len(companion_ids)} companions: {companion_ids}")
            successes += 1
            continue

        ok = shopify_service.update_product_seo_metafields(
            p.shopify_id,
            {"related_products": companion_ids},
        )
        if ok:
            successes += 1
            print(f"{prefix}  OK {len(companion_ids)} companions")
        else:
            failures += 1
            failed_skus.append(p.sku or "(no sku)")
            print(f"{prefix}  FAIL")

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
