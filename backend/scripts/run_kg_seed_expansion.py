"""
One-off: re-seed TransmissionPattern table + recompute Product.transmission_code
after expanding DEFAULT_PATTERNS in knowledge_graph.py (Phase 1.1, May 20 2026).

Steps:
  1. Snapshot the pattern + code-coverage counts.
  2. Idempotently insert missing DEFAULT_PATTERNS rows.
  3. Re-extract transmission codes for ALL products (force_recompute=True)
     so previously-unrecognized titles (01M family, Honda 4-letters, etc.)
     pick up their newly-seeded codes.
  4. Print before/after counts and the coverage delta.

Run from backend/:
    python -m scripts.run_kg_seed_expansion

Idempotent — safe to re-run after further DEFAULT_PATTERNS expansions.
"""

from __future__ import annotations

import logging
from sqlalchemy import func

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

from app.db.session import SessionLocal
from app.models.product import Product
from app.models.aeo_models import TransmissionPattern
from app.services.aeo.knowledge_graph import create_knowledge_graph_manager


def main() -> None:
    db = SessionLocal()
    try:
        pattern_count_before = db.query(TransmissionPattern).count()
        products_with_code_before = (
            db.query(func.count(Product.id))
            .filter(Product.transmission_code.isnot(None))
            .scalar()
        ) or 0
        total_products = db.query(func.count(Product.id)).scalar() or 0

        print(f"\n{'=' * 70}")
        print("KG SEED EXPANSION  -  Phase 1.1")
        print(f"{'=' * 70}\n")
        print("Before:")
        print(f"  TransmissionPattern rows:            {pattern_count_before}")
        print(f"  Products with transmission_code:     {products_with_code_before} / {total_products}")
        print()

        kg = create_knowledge_graph_manager(db)
        added_patterns = kg.ensure_default_patterns_seeded()
        print(f"Patterns inserted (idempotent fill):  +{added_patterns}")

        recomputed = kg.update_product_transmission_codes(force_recompute=True)
        print(f"Products with code updated/added:      {recomputed}")
        print()

        pattern_count_after = db.query(TransmissionPattern).count()
        products_with_code_after = (
            db.query(func.count(Product.id))
            .filter(Product.transmission_code.isnot(None))
            .scalar()
        ) or 0

        print("After:")
        print(f"  TransmissionPattern rows:            {pattern_count_after}")
        print(f"  Products with transmission_code:     {products_with_code_after} / {total_products}")

        delta = products_with_code_after - products_with_code_before
        pct_before = 100 * products_with_code_before / total_products if total_products else 0
        pct_after = 100 * products_with_code_after / total_products if total_products else 0
        print()
        print(f"Coverage:  {pct_before:.1f}%  ->  {pct_after:.1f}%  (delta: +{delta} products)")
        print(f"{'=' * 70}\n")
    finally:
        db.close()


if __name__ == "__main__":
    main()
