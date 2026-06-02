"""
Cross-verify Product.transmission_codes (the array we extracted from titles
and pushed to Shopify metafields) against Product.cached_vehicle_fitments
(curated vehicle compatibility data with transmission_model per fitment).

For each SKU:
  - List every transmission_model that appears in any fitment.
  - Mark which ones are also in our pushed transmission_codes array.
  - Flag pushed codes that appear in NO fitment (possible false positive).
  - Flag fitment transmissions NOT in our pushed array (missed signal).

Read-only. Catches both false positives (we pushed a code with no fitment
backing it) and false negatives (fitments declare a code we didn't extract).

Usage from backend/:
    python -m scripts.verify_transmission_codes K79900 K119AF
    # No args -> defaults to the two anchor SKUs.
"""

from __future__ import annotations

import sys
import logging
from collections import Counter
from typing import List

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

from app.db.session import SessionLocal
from app.models.product import Product
from app.services.aeo.knowledge_graph import DEFAULT_PATTERNS, HONDA_AUTOMATIC_CODES

KG_KNOWN = {code for code, _, _, _ in DEFAULT_PATTERNS} | set(HONDA_AUTOMATIC_CODES)


def main(skus: List[str]) -> None:
    db = SessionLocal()
    try:
        products = db.query(Product).filter(Product.sku.in_(skus)).all()
    finally:
        db.close()

    if not products:
        print(f"No products found for SKUs: {skus}")
        return

    # Order results in the same order as skus argv so it's predictable.
    by_sku = {p.sku: p for p in products}
    ordered = [by_sku[s] for s in skus if s in by_sku]

    for p in ordered:
        pushed = list(p.transmission_codes or [])
        fitments = p.cached_vehicle_fitments or []

        print(f"\n{'=' * 78}")
        print(f"SKU:           {p.sku}")
        print(f"Title:         {p.title}")
        print(f"Pushed codes:  {pushed}")
        print(f"Fitment rows:  {len(fitments)}")
        print(f"{'=' * 78}")

        if not fitments:
            print("\nNo cached_vehicle_fitments — cannot cross-verify this SKU.")
            print("Trust falls back to title text + curator authorship.")
            continue

        # Aggregate transmission_model values across fitments
        trans_counts: Counter = Counter()
        type_only: Counter = Counter()  # transmission_type when no model
        empty_count = 0
        for f in fitments:
            if not isinstance(f, dict):
                continue
            tm = (f.get("transmission_model") or "").strip().upper()
            tt = (f.get("transmission_type") or "").strip().upper()
            if tm:
                trans_counts[tm] += 1
            elif tt:
                type_only[tt] += 1
            else:
                empty_count += 1

        print(f"\nFitment composition:")
        print(f"  with transmission_model:    {sum(trans_counts.values())}")
        print(f"  with transmission_type only:{sum(type_only.values())}")
        print(f"  both empty:                 {empty_count}")

        if trans_counts:
            print(f"\nTransmissions declared in fitments:")
            pushed_set = {c.strip().upper() for c in pushed}
            for trans, count in sorted(trans_counts.items(), key=lambda x: -x[1]):
                in_pushed = "[Y]" if trans in pushed_set else "[N]"
                in_kg = "KG" if trans in KG_KNOWN else "UNKNOWN"
                print(f"  {in_pushed} {trans:<12} {count:>3} fitments   ({in_kg})")

            fitment_set = set(trans_counts.keys())

            only_pushed = pushed_set - fitment_set
            only_fitments = fitment_set - pushed_set

            if only_pushed:
                print(f"\n!! In pushed array but NOT in any fitment ({len(only_pushed)}):")
                for c in sorted(only_pushed):
                    print(f"    - {c}")
                print("    Possible false positive, or an alias of a fitment code")
                print("    (e.g. AG4 = marketing alias of 01M, both could be valid).")

            if only_fitments:
                print(f"\n!! In fitments but NOT in pushed array ({len(only_fitments)}):")
                for c in sorted(only_fitments):
                    extra = " (NOT in KG seed)" if c not in KG_KNOWN else ""
                    print(f"    - {c}{extra}")
                print("    Either the title doesn't carry this code, or the audit")
                print("    regex missed it. Worth a manual look.")
        else:
            print("\nNo fitments declare a transmission_model field; cannot verify")
            print("against fitment data. Title-text trust only.")

        # Show a few sample fitments for human spot-check
        print(f"\nSample fitments (first 5):")
        for f in fitments[:5]:
            if not isinstance(f, dict):
                continue
            make = f.get("make", "")
            modelo = f.get("modelo") or f.get("model", "")
            yr_s = f.get("year_start", "")
            yr_e = f.get("year_end", "")
            tm = f.get("transmission_model") or "(empty)"
            engine = f.get("engine") or "(empty)"
            yr = f"{yr_s}-{yr_e}" if (yr_s or yr_e) else "?"
            print(f"  {make} {modelo} {yr}  trans={tm}  engine={engine}")

    print(f"\n{'=' * 78}\n")


if __name__ == "__main__":
    skus = sys.argv[1:] if len(sys.argv) > 1 else ["K79900", "K119AF"]
    main(skus)
