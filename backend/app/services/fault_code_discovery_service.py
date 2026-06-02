"""
Phase 3.1g — fault-code discovery with KG-first / Grok-fallback strategy.

Two callers (content_generator and the /generate-schema endpoint) need the
exact same logic: "find fault codes this product genuinely remedies."
Centralizing here avoids drift.

Resolution order:
  1. Knowledge graph match — transmission_codes ∩ FaultCode.transmissions,
     filtered by component overlap (see knowledge_graph._extract_components_from_text).
  2. Grok fallback — only if KG returns 0 AND product has transmission_codes.
     Grok is instructed to return an empty list when no fault code genuinely
     fits (no fabrication). Confidence-gated; low-confidence responses drop to [].

The HowTo @graph entity builder lives here too so both callers emit identical
JSON-LD.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.services.aeo.knowledge_graph import KnowledgeGraphManager
from app.services.llm_providers.grok import GrokProvider

logger = get_logger("fault_code_discovery")

# Reject anything that isn't the standard OBD-II P-code shape — keeps Grok
# from inventing custom codes like "VW-001" or "FAULT-123".
P_CODE_PATTERN = re.compile(r"^P[0-9]{4}$")

GROK_CONFIDENCE_THRESHOLD = 0.6


class DiscoveredFaultCode(BaseModel):
    code: str
    name: str = Field(..., min_length=3, max_length=200)
    common_causes: List[str] = Field(default_factory=list, max_items=6)
    transmissions: List[str] = Field(default_factory=list, max_items=12)
    monthly_clicks: int = Field(default=0, ge=0)
    source: str = Field(default="kg")  # "kg" or "grok"

    @validator("code")
    def _validate_code(cls, v: str) -> str:
        v = v.strip().upper()
        if not P_CODE_PATTERN.match(v):
            raise ValueError(f"Invalid P-code shape: {v}")
        return v


class _GrokResponse(BaseModel):
    """Schema Grok must return. Empty list is valid (means no match)."""

    fault_codes: List[DiscoveredFaultCode] = Field(default_factory=list, max_items=6)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: Optional[str] = None


GROK_SYSTEM_PROMPT = """Eres un experto técnico en transmisiones automáticas para Example Store, una tienda mexicana de refacciones. Tu único trabajo es identificar códigos OBD-II (formato P####) que un producto específico PUEDE arreglar — basándote en lo que ES el producto y la transmisión que cubre.

REGLAS ESTRICTAS:
1. SOLO devuelve códigos donde el producto sea genuinamente una solución. Un filtro NO arregla códigos de sensor. Un solenoide NO arregla códigos de embrague.
2. Si el producto no tiene relación clara con ningún código → devuelve lista vacía con confidence ≥ 0.7. No inventes códigos.
3. Códigos deben ser estándar OBD-II reales en formato P#### (P0700, P0741, etc.). NUNCA inventes códigos.
4. Las transmisiones del producto son la fuente de verdad — solo devuelve códigos relevantes para esas transmisiones específicas.
5. common_causes: 2-4 causas técnicas reales en español (ej: "Solenoide EPC defectuoso", "Filtro tapado").
6. confidence ≥ 0.8 solo si estás muy seguro. < 0.6 si tienes dudas — preferimos lista vacía a contenido fabricado.

FORMATO DE SALIDA — SOLO JSON, sin markdown:
{
  "fault_codes": [
    {
      "code": "P0741",
      "name": "Convertidor de Torque Patinándose",
      "common_causes": ["Solenoide TCC defectuoso", "Embrague TCC desgastado"],
      "transmissions": ["01M", "01N"],
      "monthly_clicks": 0
    }
  ],
  "confidence": 0.85,
  "reasoning": "<una frase explicando por qué estos códigos aplican al producto>"
}

Si NO hay match: {"fault_codes": [], "confidence": 0.9, "reasoning": "Producto es X, no relacionado con códigos comunes de transmisión Y"}"""


def _build_user_prompt(product) -> str:
    title = (getattr(product, "title", "") or "").strip()
    desc = (getattr(product, "current_description_html", "") or "")
    if desc:
        desc = re.sub(r"<[^>]+>", " ", desc)
        desc = re.sub(r"\s+", " ", desc).strip()[:1500]
    codes = list(getattr(product, "transmission_codes", None) or [])
    ptype = (getattr(product, "product_type", "") or "").strip()
    vendor = (getattr(product, "vendor", "") or "").strip()

    parts = [
        f"## Producto\nTítulo: {title}",
        f"Vendor: {vendor or '(no especificado)'}",
        f"Product type: {ptype or '(no especificado)'}",
        f"\n## Transmisiones compatibles (fuente de verdad)\n{', '.join(codes) if codes else '(ninguna)'}",
    ]
    if desc:
        parts.append(f"\n## Descripción (primeros 1500 chars, HTML removido)\n{desc}")
    parts.append(
        "\n## Tarea\nIdentifica códigos OBD-II que este producto PUEDE arreglar. "
        "Si el producto no es una solución clara para ningún código, devuelve lista vacía."
    )
    return "\n".join(parts)


async def _discover_via_grok(product) -> List[DiscoveredFaultCode]:
    grok = GrokProvider()
    try:
        response = await grok.generate(
            system_prompt=GROK_SYSTEM_PROMPT,
            user_prompt=_build_user_prompt(product),
            json_mode=True,
            temperature=0.2,
        )
    except Exception as e:
        logger.warning(f"Grok fault-code call failed for {getattr(product, 'sku', '?')}: {e}")
        return []

    raw = response.get("content") or response.get("text") or response.get("response") or response
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning(f"Grok fault-code response not JSON: {e}; raw={raw[:200]}")
            return []
    else:
        parsed = raw

    try:
        validated = _GrokResponse(**parsed)
    except Exception as e:
        logger.warning(f"Grok fault-code response failed validation: {e}")
        return []

    if validated.confidence < GROK_CONFIDENCE_THRESHOLD:
        logger.info(
            f"Grok confidence {validated.confidence:.2f} < {GROK_CONFIDENCE_THRESHOLD} "
            f"for {getattr(product, 'sku', '?')} → returning []"
        )
        return []

    return [fc.copy(update={"source": "grok"}) for fc in validated.fault_codes]


async def discover_fault_codes_for_product(
    product,
    db: Session,
    *,
    use_grok_fallback: bool = True,
) -> List[DiscoveredFaultCode]:
    """Return fault codes this product genuinely remedies.

    KG-first: deterministic, free, instant. Grok fallback: per-product domain
    knowledge for cases the KG doesn't yet cover (e.g., VAG 01M family).
    """
    kg = KnowledgeGraphManager(db)
    kg_matches = kg.get_fault_codes_for_product(product)
    if kg_matches:
        return [
            DiscoveredFaultCode(
                code=fc.code,
                name=fc.name or fc.code,
                common_causes=list(fc.common_causes or []),
                transmissions=list(fc.transmissions or []),
                monthly_clicks=fc.monthly_clicks or 0,
                source="kg",
            )
            for fc in kg_matches
        ]

    if not use_grok_fallback:
        return []
    if not list(getattr(product, "transmission_codes", None) or []):
        return []

    return await _discover_via_grok(product)


def build_howto_entities(
    fault_codes: List[DiscoveredFaultCode],
    product_title: str,
) -> List[Dict[str, Any]]:
    """Build schema.org HowTo entities for @graph emission.

    One HowTo per fault code: step list from common_causes plus a final
    "repair with this product" step naming the product.
    """
    title = (product_title or "").strip() or "esta refacción"
    entities: List[Dict[str, Any]] = []
    for fc in fault_codes:
        steps: List[Dict[str, Any]] = []
        for i, cause in enumerate(fc.common_causes, start=1):
            steps.append({
                "@type": "HowToStep",
                "position": i,
                "name": f"Verificar: {cause}",
                "text": cause,
            })
        steps.append({
            "@type": "HowToStep",
            "position": len(steps) + 1,
            "name": f"Reparar con {title}",
            "text": f"Reemplazar el componente usando {title}.",
        })
        entities.append({
            "@type": "HowTo",
            "name": f"Diagnóstico y reparación del código {fc.code}",
            "description": fc.name,
            "step": steps,
        })
    return entities


def to_compact_dicts(fault_codes: List[DiscoveredFaultCode]) -> List[Dict[str, Any]]:
    """Compact list for store_aeo.fixes_fault_codes — frontend reads this."""
    return [
        {
            "code": fc.code,
            "name": fc.name,
            "monthly_clicks": fc.monthly_clicks,
            "source": fc.source,
        }
        for fc in fault_codes
    ]
