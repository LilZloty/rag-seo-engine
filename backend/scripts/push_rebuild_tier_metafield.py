"""
Phase 2.5: classify and push rebuild_tier to Shopify list metafield
`custom.rebuild_tier`. Theme emits as additionalProperty name="Rebuild Tier".

No Grok call — pure classification from existing Product.vendor +
Product.product_type via app.services.rebuild_tier.classify_rebuild_tier.
Fast and catalog-scale safe.

Usage (from backend/):

    # Anchors only, dry-run
    python -m scripts.push_rebuild_tier_metafield --skus K79900,K119AF --dry-run

    # Anchors live
    python -m scripts.push_rebuild_tier_metafield --skus K79900,K119AF

    # Full catalog
    python -m scripts.push_rebuild_tier_metafield

Idempotent — Shopify treats same-value writes as no-ops.
"""

from __future__ import annotations

import argparse
import logging
import time
from collections import Counter
from typing import List, Optional

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.product import Product
from app.services.rebuild_tier import classify_rebuild_tier
from app.services.shopify_service import shopify_service


def fetch_products(
    db: Session,
    skus: Optional[List[str]],
    limit: Optional[int],
) -> List[Product]:
    query = db.query(Product)
    if skus:
        query = query.filter(Product.sku.in_(skus))
    else:
        query = query.order_by(Product.gsc_impressions.desc().nullslast())
    if limit:
        query = query.limit(limit)
    return query.all()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skus", help="Comma-separated SKUs (default: full catalog sorted by GSC impressions)")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay", type=float, default=0.5)
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
    print("REBUILD_TIER METAFIELD PUSH  -  Phase 2.5")
    print(f"{'=' * 70}\n")
    print(f"Mode:              {'DRY-RUN' if args.dry_run else 'LIVE'}")
    print(f"Eligible products: {len(products)}")
    print()

    tier_distribution: Counter = Counter()
    successes = 0
    failures = 0
    unclassified = 0
    failed_skus: List[str] = []

    for i, p in enumerate(products, 1):
        tier = classify_rebuild_tier(p.vendor, p.product_type)
        prefix = f"  [{i}/{len(products)}] {p.sku or '(no sku)':<14}"
        if tier is None:
            unclassified += 1
            tier_distribution["(unclassified)"] += 1
            if args.skus:  # only print unclassified in --skus mode (full catalog would be noisy)
                print(f"{prefix}  SKIP (vendor={p.vendor!r} product_type={p.product_type!r})")
            continue
        tier_distribution[tier] += 1
        if not p.shopify_id:
            print(f"{prefix}  SKIP (no shopify_id) tier={tier!r}")
            continue

        if args.dry_run:
            print(f"{prefix}  WOULD WRITE tier={tier!r}  (vendor={p.vendor!r}, product_type={p.product_type!r})")
            successes += 1
            continue

        ok = shopify_service.update_product_seo_metafields(
            p.shopify_id,
            {"rebuild_tier": tier},
        )
        if ok:
            successes += 1
            print(f"{prefix}  OK tier={tier!r}")
        else:
            failures += 1
            failed_skus.append(p.sku or "(no sku)")
            print(f"{prefix}  FAIL tier={tier!r}")

        if i < len(products):
            time.sleep(args.delay)

    print(f"\n{'=' * 70}")
    print("Tier distribution:")
    for tier, count in sorted(tier_distribution.items(), key=lambda x: -x[1]):
        print(f"  {tier:<20} {count:>5}")
    print()
    print(f"Pushed:       {successes}")
    print(f"Failed:       {failures}")
    print(f"Unclassified: {unclassified}")
    if failed_skus:
        print(f"Failed SKUs: {failed_skus[:20]}{'...' if len(failed_skus) > 20 else ''}")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
