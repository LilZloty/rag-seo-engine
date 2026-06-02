"""
List products with the largest transmission_codes arrays so we can sanity-
check the description-text extraction (Phase 1.4) for false positives.

Run from backend/:
    python -m scripts.inspect_top_code_products
    python -m scripts.inspect_top_code_products --limit 20
"""

from __future__ import annotations

import argparse
import logging

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

from app.db.session import SessionLocal
from app.models.product import Product


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        products = (
            db.query(Product)
            .filter(Product.transmission_codes.isnot(None))
            .all()
        )
    finally:
        db.close()

    sized = [(p, len(p.transmission_codes or [])) for p in products]
    sized.sort(key=lambda x: -x[1])

    for p, n in sized[: args.limit]:
        sku = p.sku or "(no sku)"
        title = (p.title or "")[:80]
        print(f"{n:>3} codes  {sku:<16} {title}")
        print(f"           {p.transmission_codes}")
        print()


if __name__ == "__main__":
    main()
