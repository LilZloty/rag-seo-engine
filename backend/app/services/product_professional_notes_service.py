"""
Phase 3.5c — Grok-generated "Professional Notes" block for product JSON-LD.

Output goes into store_aeo.professional_notes:

    {
      "common_failures":   [...],   # 2-4 typical failure modes this product remedies
      "companion_parts":   [...],   # 2-4 parts often replaced alongside
      "installation_tips": [...],   # 2-4 technical tips for mechanics
      "confidence":        0.0-1.0
    }

Mirrors product_enrichment_service (Phase 2.4 TL;DR+FAQ) and
fault_code_discovery_service (Phase 3.1g Grok fallback) patterns:
- Pydantic-validated, json_mode, low temperature (0.2)
- Confidence floor (0.6) — below → return None, no fabrication
- Each field can be empty independently
- Graceful: any Grok failure → None, schema composition continues

Caller decision: regenerate every /generate-schema vs preserve if already
in blob. The endpoint passes the existing value through so smart-merge can
skip the Grok call when notes already exist (cost / latency control).
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.services.llm_providers.grok import GrokProvider

logger = get_logger("product_professional_notes")

GROK_CONFIDENCE_THRESHOLD = 0.6


class ProfessionalNotes(BaseModel):
    common_failures: List[str] = Field(default_factory=list, max_items=4)
    companion_parts: List[str] = Field(default_factory=list, max_items=4)
    installation_tips: List[str] = Field(default_factory=list, max_items=4)
    confidence: float = Field(..., ge=0.0, le=1.0)


GROK_SYSTEM_PROMPT = """Eres un técnico experto en transmisiones automáticas mexicanas. Tu trabajo es generar "Notas Profesionales" técnicas para un producto específico, dirigidas a mecánicos de transmisión.

CONTENIDO QUE DEBES PRODUCIR (3 secciones):

1. common_failures (2-4 ítems): Fallas comunes de la transmisión que ESTE producto remedia. Sé específico (ej: "Pérdida de presión por empaques de bomba degradados") — NO genérico ("fallas mecánicas").

2. companion_parts (2-4 ítems): Refacciones que el mecánico típicamente reemplaza JUNTO con este producto en el mismo job. Categorías genéricas en español (ej: "Filtro de transmisión", "Solenoide EPC"). NO inventes part numbers ni OEMs específicos.

3. installation_tips (2-4 ítems): Tips técnicos prácticos para la instalación o reemplazo. Específicos al tipo de producto (ej para empaques: "Limpiar superficies de sellado con thinner antes de instalar"; ej para solenoides: "Programar el TCM después del reemplazo con scanner OBD-II").

REGLAS ESTRICTAS:
- Si NO tienes conocimiento técnico específico del producto → devuelve listas vacías con confidence ≥ 0.7. NO inventes.
- Español técnico mexicano. Lenguaje de taller, no marketing.
- Cada ítem ≤120 caracteres.
- confidence ≥ 0.8 solo si tienes alta certeza en TODAS las secciones. < 0.6 si dudas — preferimos vacío a contenido inventado.
- NO menciones Example Store ni marca el producto como "el mejor". Solo información técnica accionable.

FORMATO DE SALIDA — SOLO JSON, sin markdown:
{
  "common_failures": ["...", "..."],
  "companion_parts": ["...", "..."],
  "installation_tips": ["...", "..."],
  "confidence": 0.0-1.0
}"""


def _build_user_prompt(product, fault_code_codes: Optional[List[str]] = None) -> str:
    title = (getattr(product, "title", "") or "").strip()
    desc = getattr(product, "current_description_html", "") or ""
    if desc:
        desc = re.sub(r"<[^>]+>", " ", desc)
        desc = re.sub(r"\s+", " ", desc).strip()[:2000]
    codes = list(getattr(product, "transmission_codes", None) or [])
    vendor = (getattr(product, "vendor", "") or "").strip()
    ptype = (getattr(product, "product_type", "") or "").strip()

    parts = [
        f"## Producto\nTítulo: {title}",
        f"Vendor: {vendor or '(no especificado)'}",
        f"Product type: {ptype or '(no especificado)'}",
        f"Transmisiones compatibles: {', '.join(codes) if codes else '(ninguna detectada)'}",
    ]
    if fault_code_codes:
        parts.append(f"Códigos de falla que este producto remedia: {', '.join(fault_code_codes)}")
    if desc:
        parts.append(f"\n## Descripción (primeros 2000 chars, HTML removido)\n{desc}")
    parts.append(
        "\n## Tarea\nGenera Notas Profesionales (fallas comunes / refacciones acompañantes / "
        "tips de instalación) para mecánicos. Si no tienes conocimiento específico del producto, "
        "devuelve listas vacías con confidence alta."
    )
    return "\n".join(parts)


async def generate_professional_notes(
    product,
    db: Session,
    fault_code_codes: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Return professional notes dict or None if Grok unavailable/low-confidence.

    Returns shape: {common_failures: [...], companion_parts: [...],
    installation_tips: [...], confidence: float} — same keys as Pydantic
    model but as plain dict for direct JSON serialization into the blob.

    Returns None (not empty dict) on any failure — caller checks truthy
    and skips emission when None.
    """
    grok = GrokProvider()
    try:
        response = await grok.generate(
            system_prompt=GROK_SYSTEM_PROMPT,
            user_prompt=_build_user_prompt(product, fault_code_codes),
            json_mode=True,
            temperature=0.2,
        )
    except Exception as e:
        logger.info(f"[pro-notes] Grok call failed for {getattr(product, 'sku', '?')}: {e}")
        return None

    raw = response.get("content") or response.get("text") or response.get("response") or response
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning(f"[pro-notes] non-JSON response: {e}")
            return None
    else:
        parsed = raw

    try:
        validated = ProfessionalNotes(**parsed)
    except Exception as e:
        logger.warning(f"[pro-notes] response failed validation: {e}")
        return None

    if validated.confidence < GROK_CONFIDENCE_THRESHOLD:
        logger.info(
            f"[pro-notes] confidence {validated.confidence:.2f} < {GROK_CONFIDENCE_THRESHOLD} "
            f"for {getattr(product, 'sku', '?')} → returning None"
        )
        return None

    # If ALL three sections are empty, return None — no point persisting an
    # empty notes block. confidence=high+empty means "I confidently have nothing".
    if not (validated.common_failures or validated.companion_parts or validated.installation_tips):
        return None

    return validated.dict()
