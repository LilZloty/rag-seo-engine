"""
Phase 2.10 dry-run: call /products/{id}/generate-schema with dry_run=true
locally and print the composed consolidated blob WITHOUT writing to Shopify.

Lets us verify the blob structure on K79900 + K119AF before any live writes.

Usage from backend/:
    python -m scripts.dry_run_consolidated_schema
    python -m scripts.dry_run_consolidated_schema --skus K79900,K119AF
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from typing import List

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

from app.db.session import SessionLocal
from app.models.product import Product
from app.api.v1.endpoints.products import generate_product_schema_endpoint


async def run_for_sku(sku: str, live: bool = False) -> None:
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.sku == sku).first()
        if not product:
            print(f"\n{sku}: NOT FOUND in local DB")
            return
        print(f"\n{'=' * 78}")
        mode = "LIVE WRITE" if live else "DRY-RUN"
        print(f"{mode} consolidated blob for SKU={sku} (shopify_id={product.shopify_id})")
        print(f"Title: {product.title}")
        print(f"{'=' * 78}")
        result = await generate_product_schema_endpoint(
            product_id=str(product.id),
            data=None,
            dry_run=not live,
            db=db,
        )
        # Compact summary first
        print(f"\nSummary:")
        print(f"  dry_run:           {result.get('dry_run')}")
        print(f"  blob_size_chars:   {result.get('blob_size_chars')}")
        print(f"  @graph entities:   {result.get('entities_count')}")
        print(f"  has_faq:           {result.get('has_faq')}")
        print(f"  has_howto:         {result.get('has_howto')}")
        print(f"  aeo_fields_set:    {result.get('aeo_fields_set')}")
        print(f"\nFull composed blob (would be written to custom.product_schema_json):")
        print(json.dumps(result.get('schema'), indent=2, ensure_ascii=False, default=str))
    finally:
        db.close()


async def main_async() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skus", default="K79900,K119AF",
                        help="Comma-separated SKUs (default K79900,K119AF)")
    parser.add_argument("--live", action="store_true",
                        help="Push live to Shopify (default: dry-run only)")
    args = parser.parse_args()
    skus: List[str] = [s.strip() for s in args.skus.split(",") if s.strip()]
    for sku in skus:
        await run_for_sku(sku, live=args.live)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
