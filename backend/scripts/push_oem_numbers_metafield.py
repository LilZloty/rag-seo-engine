"""
Phase 2.3: push all OEM cross-references (parsed from current_description_html)
to Shopify list metafield `custom.oem_numbers`. The theme emits each as a
schema.org/additionalProperty entry with name="OEM Cross-Reference".

Today the content generator stores only the FIRST OEM as `custom.oem_number`
(→ schema.org/mpn, kept unchanged). This script surfaces the rest so search
systems can match the product by any equivalent part number.

Usage (from backend/):

    # Anchors only
    python -m scripts.push_oem_numbers_metafield --skus K79900,K119AF

    # Dry-run
    python -m scripts.push_oem_numbers_metafield --skus K79900,K119AF --dry-run

    # Full catalog with descriptions
    python -m scripts.push_oem_numbers_metafield
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
from app.services.aeo.schema_generator import extract_oem_references_from_html
from app.services.shopify_service import shopify_service


def fetch_products(
    db: Session,
    skus: Optional[List[str]],
    limit: Optional[int],
) -> List[Product]:
    query = db.query(Product).filter(Product.current_description_html.isnot(None))
    if skus:
        query = query.filter(Product.sku.in_(skus))
    else:
        query = query.order_by(Product.gsc_impressions.desc().nullslast())
    if limit:
        query = query.limit(limit)
    return query.all()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skus",
        help="Comma-separated SKUs (default: all products with description, sorted by GSC impressions)",
    )
    parser.add_argument("--limit", type=int)
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
        products = fetch_products(db, sku_list, args.limit)
    finally:
        db.close()

    print(f"\n{'=' * 70}")
    print("OEM_NUMBERS METAFIELD PUSH  -  Phase 2.3")
    print(f"{'=' * 70}\n")
    print(f"Mode:              {'DRY-RUN' if args.dry_run else 'LIVE'}")
    print(f"Eligible products: {len(products)}")
    print()

    if not products:
        print("No products match the criteria.")
        return

    successes = 0
    failures = 0
    skipped_no_oem = 0
    skipped_no_shopify = 0
    failed_skus: List[str] = []

    for i, p in enumerate(products, 1):
        prefix = f"  [{i}/{len(products)}] {p.sku or '(no sku)':<14} shopify={p.shopify_id}"

        oem_refs = extract_oem_references_from_html(p.current_description_html or "") or []
        if not oem_refs:
            skipped_no_oem += 1
            continue
        if not p.shopify_id:
            print(f"{prefix}  SKIP (no shopify_id)")
            skipped_no_shopify += 1
            continue

        if args.dry_run:
            print(f"{prefix}  WOULD WRITE {len(oem_refs)} OEM refs: {oem_refs}")
            successes += 1
            continue

        ok = shopify_service.update_product_seo_metafields(
            p.shopify_id,
            {"oem_numbers": oem_refs},
        )
        if ok:
            successes += 1
            print(f"{prefix}  OK {len(oem_refs)} OEM refs: {oem_refs}")
        else:
            failures += 1
            failed_skus.append(p.sku or "(no sku)")
            print(f"{prefix}  FAIL")

        if i < len(products):
            time.sleep(args.delay)

    print(f"\n{'=' * 70}")
    print(f"Pushed:               {successes}")
    print(f"Failed:               {failures}")
    print(f"Skipped (no OEM):     {skipped_no_oem}")
    print(f"Skipped (no shopify): {skipped_no_shopify}")
    if failed_skus:
        print(f"Failed SKUs: {failed_skus[:20]}{'...' if len(failed_skus) > 20 else ''}")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
