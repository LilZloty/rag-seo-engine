"""
Rebuild tier classification from Product.vendor + Product.product_type
=======================================================================

Example Store's catalog implicitly encodes rebuild tier via vendor + product_type
naming. This module normalizes those signals into a canonical Spanish tier
value emitted as schema.org/additionalProperty in JSON-LD (Phase 2.5).

Tier values map to the AEO framework "Repair-Intent Language" category
ChatGPT named as a value driver (see reference_chatgpt_aeo_framework.md):

    Servicio       — basic / reseal / light maintenance (TSS Rojo, fluids)
    Estándar       — standard rebuild (generic TSS, unspecified brands)
    Reconstrucción — mid-grade rebuild
    Profesional    — professional rebuild / overhaul (Allomatic, Raybestos,
                     Sonnax, TSS H-D, TSS Dorado)
    OE Premium     — OEM-grade sealing (Freudenberg, Freudenberg Nok, ZF,
                     SACHS)
    Especialidad   — specialty parts (TransGo shift kits)

Output is Spanish because the catalog targets MX market and AI Overviews /
ChatGPT browse mode read product JSON-LD in the page's language. Future
expansion: add English aliases as a separate field if Google AI Shopping
needs them, but Spanish is what surfaces for MX queries.

Read-only — no DB writes. Caller embeds the tier into the metafield payload.
"""

from __future__ import annotations

from typing import Optional


# Brand → default tier when no product_type variant overrides. Lookup is
# upper-cased + stripped, so additions don't need exact casing.
BRAND_TIERS = {
    "FREUDENBERG": "OE Premium",
    "FREUDENBERG NOK": "OE Premium",
    "ZF AFTERMARKET": "OE Premium",
    "SACHS": "OE Premium",
    "RAYBESTOS": "Profesional",
    "RAYBESTOS POWERTRAIN": "Profesional",
    "ALLOMATIC": "Profesional",
    "SUPERIOR": "Profesional",
    "TRANSGO": "Especialidad",
    "SONNAX": "Especialidad",
    "TSS": "Estándar",  # TSS default; Rojo/Dorado/H-D variants below override
    "YOKOMITSU": "Estándar",
    "XTRA REV": "Servicio",
    "LUBEGARD": "Servicio",
}


# product_type substring → tier override (case-insensitive). Order matters —
# first match wins, so place MORE specific patterns first. These take
# precedence over the brand default because the variant is the actual product
# the customer buys, while the brand is a fallback signal.
PRODUCT_TYPE_OVERRIDES = (
    ("DORADO", "Profesional"),       # TSS Dorados / TSS Dorado — premium line
    ("DORADOS", "Profesional"),
    ("H-D", "Profesional"),          # KIT CAJA TSS H-D — heavy-duty
    ("HEAVY DUTY", "Profesional"),
    ("HEAVY-DUTY", "Profesional"),
    ("ECONOMICO", "Servicio"),       # explicit basic
    ("ECONÓMICO", "Servicio"),
    ("ROJO", "Servicio"),            # TSS Rojo basic line
)


def classify_rebuild_tier(
    vendor: Optional[str],
    product_type: Optional[str],
) -> Optional[str]:
    """Return the canonical rebuild_tier string, or None if not classifiable.

    Order:
      1. product_type variant override (Rojo / Dorado / H-D / Económico)
      2. brand-level default (Freudenberg / Allomatic / TSS / etc.)
      3. None — caller decides whether to skip emission

    None is returned for products outside the known catalog brands (e.g.,
    custom or one-off SKUs) so we don't force-fit a tier we can't justify.
    """
    pt_upper = (product_type or "").upper()
    for pattern, tier in PRODUCT_TYPE_OVERRIDES:
        if pattern in pt_upper:
            return tier

    vendor_upper = (vendor or "").strip().upper()
    if vendor_upper in BRAND_TIERS:
        return BRAND_TIERS[vendor_upper]

    return None


def repair_intent_label(tier: Optional[str]) -> Optional[str]:
    """Map a tier value to its repair-intent phrase for prompt injection.

    Used by product_enrichment_service to give Grok accurate tier context
    instead of letting it parrot marketing copy in descriptions (which
    consistently overstates basic-tier kits as "professional overhaul").
    """
    if not tier:
        return None
    return {
        "Servicio": "servicio normal / resellado ligero / mantenimiento preventivo",
        "Estándar": "rebuild estándar de transmisión",
        "Reconstrucción": "rebuild / reconstrucción de transmisión",
        "Profesional": "reconstrucción profesional / overhaul completo",
        "OE Premium": "reconstrucción profesional con sellado OE-grade",
        "Especialidad": "kit especializado de calibración (shift kit / valve body)",
    }.get(tier)


# Phase 3.5b — repair_intent as a structured list for schema.org emission.
# Distinct from repair_intent_label (single sentence for Grok prompts):
# this returns canonical CATEGORY labels for store_aeo.repair_intent,
# which the theme could later surface as additionalProperty or filter chips.
_TIER_INTENT_BASE = {
    "Servicio":       ["mantenimiento preventivo", "servicio ligero"],
    "Estándar":       ["rebuild estándar"],
    "Reconstrucción": ["reconstrucción"],
    "Profesional":    ["overhaul profesional", "reconstrucción completa"],
    "OE Premium":     ["overhaul OE-grade", "sellado profesional"],
    "Especialidad":   ["calibración de cambios"],
}

# product_type substring → component-specific intents. First match wins so
# put more specific patterns first (KIT CAJA before KIT, etc.).
_PRODUCT_TYPE_INTENTS = (
    ("KIT CAJA",             ["overhaul completo", "rebuild profesional"]),
    ("KITS DE REPARACION",   ["overhaul completo"]),
    ("KIT DE REPARACION",    ["overhaul completo"]),
    ("JUEGO DE EMPAQUE",     ["resellado completo", "reparación de fugas"]),
    ("EMPAQUE",              ["resellado", "reparación de fugas"]),
    ("RETEN",                ["resellado", "reparación de fugas"]),
    ("FILTRO",               ["cambio de filtro", "mantenimiento"]),
    ("DISCO PASTA",          ["reemplazo de embragues"]),
    ("DISCO DE HIERRO",      ["reemplazo de embragues"]),
    ("PACK FR",              ["reemplazo de embragues"]),
    ("PACK DE METALES",      ["reemplazo de discos"]),
    ("BANDA",                ["reemplazo de banda"]),
    ("CONVERTIDOR",          ["overhaul de convertidor de torque"]),
    ("SOLENOIDE",            ["reemplazo de solenoides", "reparación eléctrica"]),
    ("PARTES ELECTRICAS",    ["reparación eléctrica"]),
    ("SERVO",                ["reemplazo de servo / pistón"]),
    ("BOMBA",                ["reemplazo de bomba"]),
    ("VALVE BODY",           ["overhaul de cuerpo de válvulas"]),
    ("CUERPO DE VALV",       ["overhaul de cuerpo de válvulas"]),
    ("BUJE",                 ["reemplazo de bujes"]),
)


def derive_repair_intent(
    tier: Optional[str],
    product_type: Optional[str],
) -> list:
    """Return a list of canonical repair-intent categories for this product.

    Combines tier base intents with one product_type-specific addition.
    Deduped, ordered: tier intents first, then product-type specifics.
    Empty list if no signal — caller skips emission.
    """
    intents: list = []
    if tier and tier in _TIER_INTENT_BASE:
        intents.extend(_TIER_INTENT_BASE[tier])

    pt_upper = (product_type or "").upper()
    for pattern, type_intents in _PRODUCT_TYPE_INTENTS:
        if pattern in pt_upper:
            for t in type_intents:
                if t not in intents:
                    intents.append(t)
            break
    return intents
