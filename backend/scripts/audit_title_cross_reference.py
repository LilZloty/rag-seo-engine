"""
Audit title cross-reference density vs Product.transmission_code.

For every active product:
  1. Parse all transmission codes from title using an expanded regex set
     (existing fitment-audit set + VAG 01-series + VW0xx + AG-series + 2-digit RE).
  2. Compare against Product.transmission_code (the single stored code).
  3. Bucket by gsc_impressions tier (HIGH / ESTABLISHED / DEVELOPING / COLD).
  4. Categorize the rewrite action available per product:
       - LOCKED: single-code title, high impressions — do not touch
       - EXTENSION_LOCKED: multi-code title, HIGH tier — meta_title only
       - EXTENSION_CANDIDATE: multi-code title, ESTABLISHED tier
       - EXTENSION_OR_REWRITE: multi-code title, low tier
       - REWRITE_CANDIDATE: single-code title, low tier — full rewrite allowed
       - UNCLASSIFIED: no transmission code detected in title

Output: distribution histogram + per-tier counts + tier×category matrix +
samples per category + anchor SKU breakdown (K79900, K119AF — the May 20
ChatGPT-sourced sale).

Run from backend/:
    python -m scripts.audit_title_cross_reference

Read-only — does not modify any data.
"""

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from typing import Optional

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

from app.db.session import SessionLocal
from app.models.product import Product
from app.services.aeo.knowledge_graph import DEFAULT_PATTERNS, HONDA_AUTOMATIC_CODES


# Expanded regex set — existing audit_fitment patterns plus the four families
# the May 20 case study exposed as missing (VAG 01M, VW0xx, AG, 2-digit RE).
# Kept inclusive over precise: false positives in audit mode are cheaper than
# missed families, since each sample is human-spot-checked downstream.
TRANSMISSION_PATTERNS = [
    # --- Inherited from audit_fitment_transmission_coverage.py ---
    re.compile(r"\bZF\d+HP\d*\b", re.I),                       # ZF8HP, ZF8HP55
    re.compile(r"\b\d{1,2}[LR]\d{2}[EWNSF]?\b", re.I),         # 4L60E, 6R80, 5R55W
    re.compile(r"\b[RJ][ELN]?\d[LR]?\d{2,3}[A-Z]*\b", re.I),   # RE4R01A, RL4R01A, JR402E
    re.compile(r"\bR\d[A-Z]{3,}\b", re.I),                     # R4AXEL
    re.compile(r"\b\d{3}RE\b", re.I),                          # 845RE
    re.compile(r"\b[A-Z]{2}\d{3}[A-Z]*\b"),                    # JF506E, JF015E
    re.compile(r"\b\dEAT\b", re.I),                            # 4EAT
    re.compile(r"\bDQ\d{3}\b", re.I),                          # DQ200, DQ250
    re.compile(r"\bDPS\d\b", re.I),                            # DPS6
    re.compile(r"\b\d{2}TE\b", re.I),                          # 41TE
    re.compile(r"\bTZ\d{2}\b", re.I),                          # TZ10
    re.compile(r"\bEC\d\b", re.I),                             # EC8
    re.compile(r"\bA\d{3}[A-Z]*\b"),                           # A604
    re.compile(r"\b\dHP\d{2}\b", re.I),                        # 5HP19, 6HP28
    re.compile(r"\b\d[A-Z]{1,3}\d{1,2}\b"),                    # 8L90, 6L80
    # --- Additions from the May 20 case study ---
    re.compile(r"\b0\d[A-Z]\b", re.I),                         # 01M, 01N, 01P, 09G, 09M
    re.compile(r"\bVW\d{3}\b", re.I),                          # VW095, VW096, VW097, VW098
    re.compile(r"\bAG\d\b", re.I),                             # AG4, AG5, AG6
    re.compile(r"\b\d{2}RE\b", re.I),                          # 42RE, 46RE, 48RE
]


# KG seed coverage check — sourced from the canonical seed in knowledge_graph.py
# so this audit stays in sync with the live KG after future expansions.
KG_KNOWN_CODES = {code for code, _, _, _ in DEFAULT_PATTERNS} | set(HONDA_AUTOMATIC_CODES)


# GSC impressions thresholds — mirror the >1000-impression guardrail in
# content_generator.py's SEO Asset Lock so the audit's "LOCKED" bucket is
# consistent with what the generator actually refuses to overwrite.
TIER_HIGH = 1000
TIER_ESTABLISHED = 100
TIER_DEVELOPING = 1


def classify_tier(impressions: Optional[int]) -> str:
    if impressions is None or impressions < TIER_DEVELOPING:
        return "COLD"
    if impressions < TIER_ESTABLISHED:
        return "DEVELOPING"
    if impressions < TIER_HIGH:
        return "ESTABLISHED"
    return "HIGH"


def extract_codes(title: str) -> list[str]:
    """Deduplicated, uppercased transmission codes found in title (order preserved)."""
    if not title:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for pattern in TRANSMISSION_PATTERNS:
        for match in pattern.finditer(title):
            code = match.group(0).upper()
            if code not in seen:
                seen.add(code)
                found.append(code)
    return found


def categorize(codes_in_title: int, tier: str) -> str:
    if codes_in_title == 0:
        return "UNCLASSIFIED"
    if codes_in_title == 1:
        if tier in ("HIGH", "ESTABLISHED"):
            return "LOCKED"
        return "REWRITE_CANDIDATE"
    if tier == "HIGH":
        return "EXTENSION_LOCKED"
    if tier == "ESTABLISHED":
        return "EXTENSION_CANDIDATE"
    return "EXTENSION_OR_REWRITE"


def main() -> None:
    db = SessionLocal()
    try:
        products = (
            db.query(
                Product.id,
                Product.handle,
                Product.sku,
                Product.title,
                Product.transmission_code,
                Product.gsc_impressions,
                Product.gsc_position,
                Product.gsc_clicks,
            )
            .all()
        )
    finally:
        db.close()

    print(f"\n{'=' * 78}")
    print("TITLE CROSS-REFERENCE DENSITY AUDIT")
    print(f"{'=' * 78}\n")
    print(f"Total products: {len(products)}\n")

    code_count_histogram: Counter = Counter()
    tier_counts: Counter = Counter()
    category_counts: Counter = Counter()
    tier_category_matrix: dict = defaultdict(Counter)
    category_samples: dict = defaultdict(list)

    stored_vs_title_gap = 0  # title has more codes than the single stored one
    stored_not_in_title = 0  # stored code doesn't appear in title (data drift)
    unknown_to_kg = 0
    impressions_at_risk = 0  # impressions of products where extraction differs from storage

    anchor_skus = {"K79900", "K119AF"}
    anchor_hits = []

    for p in products:
        codes = extract_codes(p.title)
        n_codes = len(codes)
        tier = classify_tier(p.gsc_impressions)
        category = categorize(n_codes, tier)

        if codes and not any(c in KG_KNOWN_CODES for c in codes):
            unknown_to_kg += 1

        if p.transmission_code:
            stored_upper = p.transmission_code.upper()
            if stored_upper not in codes:
                stored_not_in_title += 1
        if n_codes > 1 and p.transmission_code:
            stored_vs_title_gap += 1
            impressions_at_risk += (p.gsc_impressions or 0)

        code_count_histogram[n_codes] += 1
        tier_counts[tier] += 1
        category_counts[category] += 1
        tier_category_matrix[tier][category] += 1

        if len(category_samples[category]) < 8:
            category_samples[category].append({
                "sku": p.sku,
                "handle": (p.handle or "")[:40],
                "title": (p.title or "")[:80],
                "codes": codes,
                "stored": p.transmission_code,
                "impressions": p.gsc_impressions or 0,
                "tier": tier,
            })

        if p.sku in anchor_skus:
            anchor_hits.append({
                "sku": p.sku,
                "title": p.title,
                "codes_in_title": codes,
                "stored_code": p.transmission_code,
                "impressions": p.gsc_impressions or 0,
                "clicks": p.gsc_clicks or 0,
                "position": p.gsc_position or 0,
                "tier": tier,
                "category": category,
            })

    total = len(products)
    if total == 0:
        print("No products in DB — verify the products table is populated.\n")
        return

    print("CODES PER TITLE (histogram):")
    for n in sorted(code_count_histogram.keys()):
        count = code_count_histogram[n]
        pct = 100 * count / total
        bar = "#" * int(pct / 2)
        print(f"  {n} codes: {count:>5} ({pct:5.1f}%) {bar}")
    print()

    print("GSC IMPRESSIONS TIER:")
    for tier in ("HIGH", "ESTABLISHED", "DEVELOPING", "COLD"):
        count = tier_counts.get(tier, 0)
        pct = 100 * count / total
        print(f"  {tier:<12} {count:>5} ({pct:5.1f}%)")
    print()

    print("ACTION CATEGORY:")
    cat_order = (
        "LOCKED",
        "EXTENSION_LOCKED",
        "EXTENSION_CANDIDATE",
        "EXTENSION_OR_REWRITE",
        "REWRITE_CANDIDATE",
        "UNCLASSIFIED",
    )
    for cat in cat_order:
        count = category_counts.get(cat, 0)
        pct = 100 * count / total
        print(f"  {cat:<22} {count:>5} ({pct:5.1f}%)")
    print()

    print("TIER x CATEGORY:")
    header = "  " + "".rjust(13) + "".join(f"{cat[:18]:>20}" for cat in cat_order)
    print(header)
    for tier in ("HIGH", "ESTABLISHED", "DEVELOPING", "COLD"):
        row = f"  {tier:<13}"
        for cat in cat_order:
            n = tier_category_matrix[tier].get(cat, 0)
            row += f"{n:>20}"
        print(row)
    print()

    print("DATA-INTEGRITY SIGNALS:")
    print(f"  Products with multi-code title but only 1 stored:  {stored_vs_title_gap}")
    print(f"    -> combined GSC impressions at risk of loss:   {impressions_at_risk:,}")
    print(f"  Products whose stored code is NOT in the title:    {stored_not_in_title}")
    print(f"    (likely set by alias logic, not by title parser)")
    print()

    pct_unknown = 100 * unknown_to_kg / total
    print("KG SEED COVERAGE:")
    print(f"  Products with at least one extracted code NOT in KG seed: {unknown_to_kg} ({pct_unknown:.1f}%)")
    print(f"  KG_KNOWN_CODES (current seed in knowledge_graph.py):")
    print(f"    {sorted(KG_KNOWN_CODES)}")
    print()

    if anchor_hits:
        print("ANCHOR SKUs (May 20 ChatGPT-sourced sale):")
        for hit in anchor_hits:
            print(f"  {hit['sku']}:")
            print(f"    title:           {hit['title']}")
            print(f"    codes_in_title:  {hit['codes_in_title']}")
            print(f"    stored_code:     {hit['stored_code']!r}")
            print(f"    impressions:     {hit['impressions']}")
            print(f"    clicks:          {hit['clicks']}")
            print(f"    position:        {hit['position']:.1f}")
            print(f"    tier:            {hit['tier']}")
            print(f"    category:        {hit['category']}")
            print()
    else:
        print("ANCHOR SKUs (K79900, K119AF) NOT FOUND in Product table.")
        print("  Verify Shopify product sync if they should be present.\n")

    print("SAMPLES PER CATEGORY (up to 8 each):")
    for cat in cat_order:
        samples = category_samples.get(cat, [])
        if not samples:
            continue
        print(f"\n  [{cat}]")
        for s in samples:
            sku = s["sku"] or "(no sku)"
            stored = s["stored"] or "(none)"
            print(
                f"    {sku:<10} impr={s['impressions']:>5} "
                f"stored={stored:<10} codes={s['codes']}"
            )
            print(f"      title: {s['title']}")

    print(f"\n{'=' * 78}")
    print("INTERPRETATION")
    print(f"{'=' * 78}")
    print("  LOCKED — single-code title already ranking. Leave H1/handle alone;")
    print("    sibling codes belong in meta_title or metafield only.")
    print("  EXTENSION_LOCKED — multi-code title, HIGH tier. The title already")
    print("    carries the codes; the metafield is the bottleneck (currently a")
    print("    single string). Shipping the multi-code metafield + theme loop")
    print("    update is the unlock here.")
    print("  EXTENSION_CANDIDATE — multi-code title, ESTABLISHED tier. Same as")
    print("    above plus safe to extend meta_title for additional reach.")
    print("  EXTENSION_OR_REWRITE — low-tier, multi-code title. Full content")
    print("    regeneration safe; metafield should still capture all codes.")
    print("  REWRITE_CANDIDATE — single-code COLD/DEVELOPING. Safe for full")
    print("    content rewrite with the expanded KG cross-reference set.")
    print("  UNCLASSIFIED — regex matched no codes. Either a non-transmission")
    print("    SKU (fluids, tools, ATRA membership) or the title uses a code")
    print("    family the regex set doesn't know yet. Spot-check the samples.")
    print()
    print("  The DATA-INTEGRITY SIGNALS section tells you how much of the")
    print("  cross-reference signal is being lost today by the single-string")
    print("  Product.transmission_code column. That is the foundation work for")
    print("  Phase 1 path A.")
    print(f"\n{'=' * 78}\n")


if __name__ == "__main__":
    main()
