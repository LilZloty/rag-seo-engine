"""
Phase 1.2 backfill: populate Product.transmission_codes (array) for every product.

Triggers init_db() so the auto-migration adds the new column if missing, then
recomputes the multi-code array for every product using the expanded KG seed
from Phase 1.1.

Idempotent — safe to re-run after further title sync or KG expansion.

Run from backend/:
    python -m scripts.backfill_transmission_codes
"""

from __future__ import annotations

import logging
from sqlalchemy import func

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

from app.db.session import SessionLocal, init_db
from app.models.product import Product
from app.services.aeo.knowledge_graph import create_knowledge_graph_manager


def main() -> None:
    # init_db() triggers the ALTER TABLE migration list — ensures the new
    # transmission_codes column exists before we try to populate it.
    init_db()

    db = SessionLocal()
    try:
        total = db.query(func.count(Product.id)).scalar() or 0
        with_array_before = (
            db.query(func.count(Product.id))
            .filter(Product.transmission_codes.isnot(None))
            .scalar()
        ) or 0
        with_single_before = (
            db.query(func.count(Product.id))
            .filter(Product.transmission_code.isnot(None))
            .scalar()
        ) or 0

        print(f"\n{'=' * 70}")
        print("MULTI-CODE BACKFILL  -  Phase 1.2")
        print(f"{'=' * 70}\n")
        print("Before:")
        print(f"  Products total:                            {total}")
        print(f"  Products with transmission_code (single):  {with_single_before}")
        print(f"  Products with transmission_codes (array):  {with_array_before}")
        print()

        kg = create_knowledge_graph_manager(db)
        changed = kg.update_product_transmission_codes(force_recompute=True)
        print(f"Products updated:                           {changed}")
        print()

        with_array_after = (
            db.query(func.count(Product.id))
            .filter(Product.transmission_codes.isnot(None))
            .scalar()
        ) or 0
        with_single_after = (
            db.query(func.count(Product.id))
            .filter(Product.transmission_code.isnot(None))
            .scalar()
        ) or 0

        print("After:")
        print(f"  Products with transmission_code (single):  {with_single_after}")
        print(f"  Products with transmission_codes (array):  {with_array_after}")
        print()

        # Anchor SKU smoke test
        anchors = (
            db.query(Product)
            .filter(Product.sku.in_(['K79900', 'K119AF']))
            .all()
        )
        if anchors:
            print("Anchor SKU verification:")
            for p in anchors:
                print(f"  {p.sku}")
                print(f"    title:              {p.title}")
                print(f"    transmission_code:  {p.transmission_code!r}")
                print(f"    transmission_codes: {p.transmission_codes!r}")
            print()

        # Sample distribution of array sizes
        all_arrays = (
            db.query(Product.transmission_codes)
            .filter(Product.transmission_codes.isnot(None))
            .all()
        )
        from collections import Counter
        size_hist: Counter = Counter()
        for (arr,) in all_arrays:
            size_hist[len(arr or [])] += 1
        print("transmission_codes array size distribution:")
        for n in sorted(size_hist.keys()):
            print(f"  {n} codes: {size_hist[n]:>5}")
        print()
        print(f"{'=' * 70}\n")
    finally:
        db.close()


if __name__ == "__main__":
    main()
