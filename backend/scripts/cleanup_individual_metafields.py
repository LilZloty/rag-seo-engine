"""
Phase 2.10g cleanup (NOT auto-run): null out the 6 individual AEO metafields
on products that have been migrated to the consolidated product_schema_json
blob. Theo runs this manually when he's ready to clean up after the theme
refactor is deployed.

Targets these keys on each product:
    custom.transmission_code
    custom.transmission_codes
    custom.oem_number
    custom.oem_numbers
    custom.related_products
    custom.rebuild_tier
    custom.product_tldr_summary
    custom.product_faqs

By default scopes to products that DO have custom.product_schema_json set
(safe — only touches migrated products). Defaults to --dry-run so nothing
ships unless --live is passed explicitly.

Usage from backend/ (NOT to be auto-run):
    python -m scripts.cleanup_individual_metafields              # dry-run, all migrated
    python -m scripts.cleanup_individual_metafields --skus K79900,K119AF
    python -m scripts.cleanup_individual_metafields --live --skus K79900
"""

from __future__ import annotations

import argparse
import logging
import time
from typing import List, Optional

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

from app.db.session import SessionLocal
from app.models.product import Product
from app.services.shopify_service import shopify_service


LEGACY_KEYS = [
    "transmission_code",
    "transmission_codes",
    "oem_number",
    "oem_numbers",
    "related_products",
    "rebuild_tier",
    "product_tldr_summary",
    "product_faqs",
]


def fetch_and_optionally_delete(shopify_id: str, live: bool) -> tuple:
    """Fetch legacy metafields and (if live=True) destroy them.

    Returns (found_keys: List[str], deleted_count: int).

    Quirk: the Shopify Python SDK's Metafield.destroy() returns False even
    when the DELETE call succeeded server-side, so we ignore its return value
    and re-fetch the metafields to determine which keys are actually gone.
    """
    shopify_service._ensure_initialized()
    import shopify
    try:
        prod = shopify.Product.find(int(shopify_id))
        if not prod:
            return ([], 0)
        legacy = [m for m in prod.metafields()
                  if m.namespace == "custom" and m.key in LEGACY_KEYS]
        keys_before = sorted(m.key for m in legacy)
        if not live or not keys_before:
            return (keys_before, 0)

        for m in legacy:
            try:
                m.destroy()
            except Exception as e:
                print(f"   ERROR destroying {m.key}: {e}")

        prod2 = shopify.Product.find(int(shopify_id))
        remaining = {m.key for m in prod2.metafields()
                     if m.namespace == "custom" and m.key in LEGACY_KEYS}
        deleted = len([k for k in keys_before if k not in remaining])
        for k in keys_before:
            if k in remaining:
                print(f"   FAIL: {k} still present after destroy()")
        return (keys_before, deleted)
    except Exception as e:
        print(f"   ERROR fetching metafields for {shopify_id}: {e}")
        return ([], 0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skus", help="Comma-separated SKUs (default: all products with product_schema_json populated)")
    parser.add_argument("--limit", type=int, help="Cap on number of products")
    parser.add_argument("--live", action="store_true", help="Actually delete (default: dry-run)")
    parser.add_argument("--delay", type=float, default=0.5)
    args = parser.parse_args()

    sku_list = None
    if args.skus:
        sku_list = [s.strip() for s in args.skus.split(",") if s.strip()]

    db = SessionLocal()
    try:
        if sku_list:
            products = db.query(Product).filter(Product.sku.in_(sku_list)).all()
        else:
            # All products are potential candidates; we filter by Shopify metafield
            # presence below since the DB doesn't track which products have the blob.
            q = db.query(Product).order_by(Product.gsc_impressions.desc().nullslast())
            if args.limit:
                q = q.limit(args.limit)
            products = q.all()
    finally:
        db.close()

    print(f"\n{'=' * 78}")
    print("LEGACY INDIVIDUAL METAFIELD CLEANUP  —  Phase 2.10g")
    print(f"{'=' * 78}\n")
    print(f"Mode:              {'LIVE DELETE' if args.live else 'DRY-RUN'}")
    print(f"Products to check: {len(products)}")
    print()

    if not products:
        print("Nothing to do.")
        return

    total_present = 0
    total_deleted = 0
    total_failed = 0
    skipped_no_blob = 0

    for i, p in enumerate(products, 1):
        # Safety check: only touch products that have the blob (migrated)
        shopify_data = shopify_service.get_product_full_details(p.shopify_id)
        metas = (shopify_data or {}).get("metafields", {}) or {}
        has_blob = bool(metas.get("custom.product_schema_json"))

        prefix = f"  [{i:>3}/{len(products)}] {p.sku or '(no sku)':<22} shopify={p.shopify_id}"
        if not has_blob:
            print(f"{prefix}  SKIP (no consolidated blob present — not yet migrated)")
            skipped_no_blob += 1
            continue

        keys_present, deleted = fetch_and_optionally_delete(p.shopify_id, live=args.live)
        if not keys_present:
            print(f"{prefix}  CLEAN (no legacy metafields to remove)")
            continue

        keys_str = ", ".join(keys_present)
        total_present += len(keys_present)

        if not args.live:
            print(f"{prefix}  WOULD DELETE {len(keys_present)} legacy: {keys_str}")
            continue

        total_deleted += deleted
        total_failed += (len(keys_present) - deleted)
        print(f"{prefix}  DELETED {deleted}/{len(keys_present)}: {keys_str}")
        if i < len(products):
            time.sleep(args.delay)

    print(f"\n{'=' * 78}")
    print(f"Legacy metafields found:   {total_present}")
    if args.live:
        print(f"Deleted:                   {total_deleted}")
        print(f"Failed:                    {total_failed}")
    else:
        print(f"Would delete:              {total_present}")
    print(f"Products skipped (no blob): {skipped_no_blob}")
    print(f"{'=' * 78}\n")


if __name__ == "__main__":
    main()
