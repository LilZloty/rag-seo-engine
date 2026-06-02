"""
Audit transmission_model coverage across vehicle fitments.

For each product with cached_vehicle_fitments, computes:
  - how many fitment rows have transmission_model populated
  - how many have only transmission_type (brand) populated
  - how many have nothing
  - whether the engine free-text field contains a known transmission code
    (these are backfill candidates)

Output:
  - Aggregate stats
  - Distribution buckets (0%, 1-50%, 51-99%, 100% populated)
  - Sample products per bucket
  - Backfill potential: how many empty rows have a code hiding in engine

Run:
    cd backend
    python -m scripts.audit_fitment_transmission_coverage
"""

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

from app.db.session import SessionLocal
from app.models.product import Product


# Expanded regex set — covers the patterns the title-extractor misses
# (R4AXEL, RL4R01A, RE4R01A, JR402E, TZ10, EC8, 4EAT, etc.)
TRANSMISSION_PATTERNS = [
    re.compile(r"\bZF\d+HP\d*\b", re.I),                    # ZF8HP, ZF8HP55
    re.compile(r"\b\d{1,2}[LR]\d{2}[EWNSF]?\b", re.I),      # 4L60E, 6R80, 5R55W
    re.compile(r"\b[RJ][ELN]?\d[LR]?\d{2,3}[A-Z]*\b", re.I),  # RE4R01A, RL4R01A, JR402E
    re.compile(r"\bR\d[A-Z]{3,}\b", re.I),                  # R4AXEL, R4AX-EL
    re.compile(r"\b\d{3}RE\b", re.I),                       # 845RE, 850RE
    re.compile(r"\b[A-Z]{2}\d{3}[A-Z]*\b"),                 # JF506E, JF015E
    re.compile(r"\b\dEAT\b", re.I),                         # 4EAT, 5EAT
    re.compile(r"\bDQ\d{3}\b", re.I),                       # DQ200, DQ250
    re.compile(r"\bDPS\d\b", re.I),                         # DPS6
    re.compile(r"\b\d{2}TE\b", re.I),                       # 41TE, 42TE
    re.compile(r"\bTZ\d{2}\b", re.I),                       # TZ10
    re.compile(r"\bEC\d\b", re.I),                          # EC8
    re.compile(r"\bA\d{3}[A-Z]*\b"),                        # A604, A606, A618
    re.compile(r"\b\dHP\d{2}\b", re.I),                     # 5HP19, 6HP28
    re.compile(r"\b\d[A-Z]{1,3}\d{1,2}\b"),                 # 8L90, 6L80
]


def _is_populated(value) -> bool:
    """Treat None, empty string, and whitespace-only as not populated."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _engine_has_transmission_code(engine_text: str) -> str | None:
    """If engine free-text contains a recognizable transmission code, return it."""
    if not engine_text or not isinstance(engine_text, str):
        return None
    for pattern in TRANSMISSION_PATTERNS:
        match = pattern.search(engine_text)
        if match:
            return match.group(0).upper()
    return None


def _classify_product(fitments: list) -> dict:
    """Return per-product stats for one product's fitment list."""
    if not fitments or not isinstance(fitments, list):
        return None

    total = len(fitments)
    with_model = 0
    with_type_only = 0
    empty = 0
    backfillable = 0  # empty rows that have a code hiding in engine
    sample_engine_hits = []

    for fitment in fitments:
        if not isinstance(fitment, dict):
            continue
        has_model = _is_populated(fitment.get("transmission_model"))
        has_type = _is_populated(fitment.get("transmission_type"))

        if has_model:
            with_model += 1
        elif has_type:
            with_type_only += 1
        else:
            empty += 1

        if not has_model:
            engine_code = _engine_has_transmission_code(fitment.get("engine", ""))
            if engine_code:
                backfillable += 1
                if len(sample_engine_hits) < 2:
                    sample_engine_hits.append(engine_code)

    return {
        "total": total,
        "with_model": with_model,
        "with_type_only": with_type_only,
        "empty": empty,
        "backfillable": backfillable,
        "coverage_pct": round(100 * with_model / total, 1) if total else 0,
        "sample_engine_hits": sample_engine_hits,
    }


def _bucket(coverage_pct: float) -> str:
    if coverage_pct == 0:
        return "0% (none populated)"
    if coverage_pct < 50:
        return "1-49% (mostly empty)"
    if coverage_pct < 100:
        return "50-99% (partial)"
    return "100% (fully populated)"


def main() -> None:
    db = SessionLocal()
    try:
        products = (
            db.query(Product.id, Product.handle, Product.title, Product.cached_vehicle_fitments)
            .filter(Product.cached_vehicle_fitments.isnot(None))
            .all()
        )
    finally:
        db.close()

    print(f"\n{'=' * 70}")
    print("VEHICLE FITMENT — transmission_model coverage audit")
    print(f"{'=' * 70}\n")

    total_products_in_db = len(products)
    print(f"Products with non-null cached_vehicle_fitments: {total_products_in_db}")

    products_with_fitments = 0
    total_fitment_rows = 0
    total_with_model = 0
    total_with_type_only = 0
    total_empty = 0
    total_backfillable = 0

    bucket_counts: Counter = Counter()
    bucket_samples: dict = defaultdict(list)

    for product in products:
        stats = _classify_product(product.cached_vehicle_fitments)
        if not stats or stats["total"] == 0:
            continue
        products_with_fitments += 1
        total_fitment_rows += stats["total"]
        total_with_model += stats["with_model"]
        total_with_type_only += stats["with_type_only"]
        total_empty += stats["empty"]
        total_backfillable += stats["backfillable"]

        bucket = _bucket(stats["coverage_pct"])
        bucket_counts[bucket] += 1
        if len(bucket_samples[bucket]) < 5:
            bucket_samples[bucket].append({
                "handle": product.handle,
                "title": (product.title or "")[:60],
                "fitments": stats["total"],
                "with_model": stats["with_model"],
                "backfillable": stats["backfillable"],
                "samples": stats["sample_engine_hits"],
            })

    print(f"Products with at least 1 fitment row:     {products_with_fitments}")
    print(f"Total fitment rows across catalog:        {total_fitment_rows}\n")

    if total_fitment_rows == 0:
        print("No fitment rows found — nothing to audit.")
        return

    pct_model = 100 * total_with_model / total_fitment_rows
    pct_type_only = 100 * total_with_type_only / total_fitment_rows
    pct_empty = 100 * total_empty / total_fitment_rows
    pct_backfillable = (
        100 * total_backfillable / (total_with_type_only + total_empty)
        if (total_with_type_only + total_empty)
        else 0
    )

    print("ROW-LEVEL COVERAGE:")
    print(f"  transmission_model populated:           {total_with_model:>6} ({pct_model:5.1f}%)")
    print(f"  transmission_type only (brand):         {total_with_type_only:>6} ({pct_type_only:5.1f}%)")
    print(f"  both empty:                             {total_empty:>6} ({pct_empty:5.1f}%)")
    print(f"  ↳ backfillable from engine free-text:   {total_backfillable:>6} ({pct_backfillable:5.1f}% of empty)\n")

    print("PRODUCT-LEVEL DISTRIBUTION:")
    bucket_order = [
        "100% (fully populated)",
        "50-99% (partial)",
        "1-49% (mostly empty)",
        "0% (none populated)",
    ]
    for bucket in bucket_order:
        count = bucket_counts.get(bucket, 0)
        pct = 100 * count / products_with_fitments if products_with_fitments else 0
        print(f"  {bucket:<28} {count:>5} products ({pct:5.1f}%)")

    print("\nSAMPLES PER BUCKET (up to 5 each):")
    for bucket in bucket_order:
        samples = bucket_samples.get(bucket, [])
        if not samples:
            continue
        print(f"\n  [{bucket}]")
        for s in samples:
            sample_str = f" → engine hits: {s['samples']}" if s["samples"] else ""
            print(
                f"    {s['handle'][:50]:<52} "
                f"{s['with_model']}/{s['fitments']} populated, "
                f"{s['backfillable']} backfillable{sample_str}"
            )

    print("\nINTERPRETATION GUIDE:")
    print("  - If most products are in 0% / 1-49% buckets: metaobjects exist but")
    print("    the import script never split transmission code from engine notes.")
    print("    Backfilling from engine free-text is the highest-leverage move.")
    print("  - If most products are in 100% bucket: the data is clean — fitment")
    print("    table issues are downstream (LLM guessing) and a deterministic")
    print("    renderer can use the metaobject directly.")
    print(f"\n{'=' * 70}\n")


if __name__ == "__main__":
    main()
