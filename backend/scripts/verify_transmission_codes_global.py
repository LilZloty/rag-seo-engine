"""
Catalog-wide accuracy check for Product.transmission_codes (extracted by regex
from titles) against Product.cached_vehicle_fitments (curated vehicle data
with transmission_model per fitment).

For products that have BOTH columns populated, compute per-product:
  - precision = |pushed ∩ fitment_models| / |pushed|
  - recall    = |pushed ∩ fitment_models| / |fitment_models|
  - F1        = harmonic mean of precision and recall

Output:
  - Coverage: how many products have both columns
  - Aggregate precision / recall / F1
  - Buckets of perfect / partial / mismatched products
  - Sample worst-precision products (false positives - extracted codes not
    backed by fitments)
  - Sample worst-recall products (missed codes - fitments declare a code
    we didn't extract)

Read-only. Run from backend/:
    python -m scripts.verify_transmission_codes_global
"""

from __future__ import annotations

import logging
from collections import Counter
from statistics import mean

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

from app.db.session import SessionLocal
from app.models.product import Product
from app.services.aeo.knowledge_graph import DEFAULT_PATTERNS, HONDA_AUTOMATIC_CODES

KG_KNOWN = {code for code, _, _, _ in DEFAULT_PATTERNS} | set(HONDA_AUTOMATIC_CODES)


def fitment_transmission_set(fitments):
    """Return the set of uppercase transmission_model values across a fitment list."""
    result = set()
    if not fitments:
        return result
    for f in fitments:
        if not isinstance(f, dict):
            continue
        tm = (f.get("transmission_model") or "").strip().upper()
        if tm:
            result.add(tm)
    return result


def main() -> None:
    db = SessionLocal()
    try:
        products = (
            db.query(
                Product.sku,
                Product.title,
                Product.transmission_codes,
                Product.cached_vehicle_fitments,
                Product.gsc_impressions,
            )
            .filter(Product.transmission_codes.isnot(None))
            .filter(Product.cached_vehicle_fitments.isnot(None))
            .all()
        )
    finally:
        db.close()

    print(f"\n{'=' * 78}")
    print("CATALOG-WIDE PRECISION/RECALL  -  regex codes vs fitment data")
    print(f"{'=' * 78}\n")
    print(f"Products with BOTH transmission_codes AND cached_vehicle_fitments: {len(products)}")

    if not products:
        print("No products have both columns populated. Nothing to verify.\n")
        return

    perfect = []           # precision=recall=1
    high_precision = []    # precision=1, recall<1 (we under-extract but are never wrong)
    low_precision = []     # precision<1 (some extracted codes not in fitments)
    no_fitment_trans = 0   # has fitments but none declare a transmission

    precisions = []
    recalls = []
    f1s = []

    fp_examples = []   # false positive examples (pushed code not in fitments)
    fn_examples = []   # false negative examples (fitment code not pushed)

    for p in products:
        pushed = {c.strip().upper() for c in (p.transmission_codes or [])}
        fitment_trans = fitment_transmission_set(p.cached_vehicle_fitments)

        if not fitment_trans:
            no_fitment_trans += 1
            continue
        if not pushed:
            continue

        tp = pushed & fitment_trans
        precision = len(tp) / len(pushed) if pushed else 0
        recall = len(tp) / len(fitment_trans) if fitment_trans else 0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0

        precisions.append(precision)
        recalls.append(recall)
        f1s.append(f1)

        if precision == 1.0 and recall == 1.0:
            perfect.append(p)
        elif precision == 1.0:
            high_precision.append(p)
        else:
            low_precision.append(p)

        fps = pushed - fitment_trans
        fns = fitment_trans - pushed
        if fps and len(fp_examples) < 12:
            fp_examples.append((p, sorted(fps), sorted(pushed), sorted(fitment_trans)))
        if fns and len(fn_examples) < 12:
            fn_examples.append((p, sorted(fns), sorted(pushed), sorted(fitment_trans)))

    total_compared = len(precisions)
    print(f"Products with fitments declaring transmissions: {total_compared}")
    print(f"Products with fitments but no transmission_model: {no_fitment_trans}\n")

    if total_compared == 0:
        print("Nothing comparable. Done.\n")
        return

    print(f"Aggregate metrics across {total_compared} comparable products:")
    print(f"  Mean precision: {mean(precisions):.3f}  (extracted codes that ARE in fitments)")
    print(f"  Mean recall:    {mean(recalls):.3f}  (fitment codes that ARE in extracted)")
    print(f"  Mean F1:        {mean(f1s):.3f}\n")

    print(f"Bucket distribution:")
    print(f"  Perfect (P=R=1.0):           {len(perfect):>5} ({100*len(perfect)/total_compared:.1f}%)")
    print(f"  High precision (P=1, R<1):   {len(high_precision):>5} ({100*len(high_precision)/total_compared:.1f}%)")
    print(f"  Low precision (P<1):         {len(low_precision):>5} ({100*len(low_precision)/total_compared:.1f}%)")
    print()

    if fp_examples:
        print(f"Sample FALSE POSITIVES — extracted codes NOT in fitments")
        print(f"({len(fp_examples)} shown; possible regex errors or alias-only codes):")
        for p, fps, pushed, fitments in fp_examples:
            print(f"  {p.sku or '(no sku)':<14} impr={p.gsc_impressions or 0:>5}")
            print(f"    title:       {(p.title or '')[:100]}")
            print(f"    extracted:   {pushed}")
            print(f"    fitments:    {fitments}")
            print(f"    -> NOT in fitments: {fps}")
        print()

    if fn_examples:
        print(f"Sample FALSE NEGATIVES — fitment codes NOT extracted")
        print(f"({len(fn_examples)} shown; codes title doesn't carry or regex missed):")
        for p, fns, pushed, fitments in fn_examples:
            print(f"  {p.sku or '(no sku)':<14} impr={p.gsc_impressions or 0:>5}")
            print(f"    title:       {(p.title or '')[:100]}")
            print(f"    extracted:   {pushed}")
            print(f"    fitments:    {fitments}")
            print(f"    -> NOT extracted: {fns}")
        print()

    print(f"{'=' * 78}\n")


if __name__ == "__main__":
    main()
