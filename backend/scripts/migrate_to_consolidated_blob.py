"""
Phase 2.10f migration: write the consolidated product_schema_json blob to
top-N products by GSC impressions (union K79900 + K119AF).

Dual-write safe — the underlying /generate-schema endpoint writes the blob
to custom.product_schema_json AND keeps the legacy individual metafields
in place. Theme rendering continues unchanged until the 2.10d theme
refactor lands.

Usage from backend/:
    # Dry-run (default): print intended writes without calling Shopify
    python -m scripts.migrate_to_consolidated_blob

    # Live (writes blob + legacy metafields to top-25 by impressions)
    python -m scripts.migrate_to_consolidated_blob --live

    # Different size
    python -m scripts.migrate_to_consolidated_blob --live --limit 100

    # Specific SKUs only
    python -m scripts.migrate_to_consolidated_blob --live --skus K79900,K119AF,DCVT
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from typing import List, Optional

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

from app.db.session import SessionLocal
from app.models.product import Product
from app.api.v1.endpoints.products import generate_product_schema_endpoint


def pick_products(
    skus: Optional[List[str]],
    limit: int,
    include_anchors: bool = True,
) -> List[Product]:
    """Return ordered, deduplicated product list to migrate."""
    db = SessionLocal()
    try:
        if skus:
            ordered = []
            seen = set()
            for sku in skus:
                p = db.query(Product).filter(Product.sku == sku).first()
                if p and p.shopify_id not in seen:
                    seen.add(p.shopify_id)
                    ordered.append(p)
            return ordered

        # Default: top-N by GSC impressions + anchors
        top = (
            db.query(Product)
            .order_by(Product.gsc_impressions.desc().nullslast())
            .limit(limit)
            .all()
        )
        anchors = (
            db.query(Product).filter(Product.sku.in_(["K79900", "K119AF"])).all()
            if include_anchors else []
        )
        seen = set()
        ordered: List[Product] = []
        for p in list(top) + list(anchors):
            if p.shopify_id and p.shopify_id not in seen:
                seen.add(p.shopify_id)
                ordered.append(p)
        return ordered
    finally:
        db.close()


async def migrate_one(product: Product, live: bool) -> dict:
    db = SessionLocal()
    try:
        return await generate_product_schema_endpoint(
            product_id=str(product.id),
            data=None,
            dry_run=not live,
            db=db,
        )
    finally:
        db.close()


async def main_async() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=25,
                        help="Top-N by GSC impressions (default 25). Ignored if --skus is provided.")
    parser.add_argument("--skus", default=None,
                        help="Comma-separated SKUs to migrate explicitly")
    parser.add_argument("--live", action="store_true",
                        help="Actually write to Shopify (default: dry-run)")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="Seconds between products (Shopify rate-limit headroom)")
    args = parser.parse_args()

    sku_list = None
    if args.skus:
        sku_list = [s.strip() for s in args.skus.split(",") if s.strip()]

    products = pick_products(sku_list, args.limit)

    print(f"\n{'=' * 78}")
    print(f"CONSOLIDATED BLOB MIGRATION  —  Phase 2.10f")
    print(f"{'=' * 78}\n")
    print(f"Mode:              {'LIVE' if args.live else 'DRY-RUN'}")
    print(f"Products to touch: {len(products)}")
    print(f"Delay per call:    {args.delay}s")
    print()

    if not products:
        print("No products matched — nothing to do.")
        return

    successes = 0
    failures = 0
    failed_skus: List[str] = []
    total_blob_chars = 0

    for i, p in enumerate(products, 1):
        prefix = f"  [{i:>2}/{len(products)}] {p.sku or '(no sku)':<22} impr={p.gsc_impressions or 0:>5}"
        try:
            result = await migrate_one(p, live=args.live)
            blob_chars = result.get("blob_size_chars") or 0
            total_blob_chars += blob_chars
            aeo_fields = result.get("aeo_fields_set") or []
            graph_n = result.get("entities_count") or 0
            print(f"{prefix}  OK  blob={blob_chars}ch  graph={graph_n}  aeo={len(aeo_fields)}fields")
            successes += 1
        except Exception as e:
            failures += 1
            failed_skus.append(p.sku or "(no sku)")
            print(f"{prefix}  FAIL  {type(e).__name__}: {e}")

        if i < len(products):
            time.sleep(args.delay)

    print(f"\n{'=' * 78}")
    print(f"Pushed:           {successes}")
    print(f"Failed:           {failures}")
    print(f"Total blob chars: {total_blob_chars}  (avg {total_blob_chars // max(successes,1)} per product)")
    if failed_skus:
        print(f"Failed SKUs: {failed_skus[:20]}{'...' if len(failed_skus) > 20 else ''}")
    print(f"{'=' * 78}\n")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
