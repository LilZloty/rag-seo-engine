"""
Product Enrichment Service — TL;DR generator (Phase 2.1)
========================================================

Generates an AEO-optimized TL;DR summary for a Shopify product by combining
local DB signals (title, description, transmission_codes) and Grok.

The output writes a `custom.product_tldr_summary` metafield (multi_line_text)
on the Shopify product. The theme's structured-data.liquid emits it as
schema.org `disambiguatingDescription` in the Product JSON-LD — a citation-
friendly short description LLMs (ChatGPT/Perplexity browse, Google AI
Overviews, Bing Copilot) tend to extract over the full HTML description.

Pattern mirrors `article_enrichment_service.py` (May 18 2026):
  - Pydantic-validated result with min/max char bounds
  - Grok call with json_mode + low temperature
  - Confidence threshold (default 0.7); writes only when confidence ≥ threshold
  - Dry-run by default

Endpoint: POST /api/v1/aeo/products/{product_id}/enrich-tldr

Phase 2.2 follow-ups (deferred):
  - PAA (DataForSEO) context
  - GSC top-query context for the product URL
  - Vehicle fitment context
  - FAQ generation
  - Theme visual card (currently structured-data only)
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models.product import Product
from app.services.llm_providers.grok import GrokProvider
from app.services.shopify_service import shopify_service

logger = get_logger("product_enrichment_service")


# ============ Pydantic schemas ============


class FAQItem(BaseModel):
    q: str = Field(..., min_length=10, max_length=200)
    a: str = Field(..., min_length=20, max_length=2000)


class ProductEnrichmentResult(BaseModel):
    tldr_summary: str = Field(..., min_length=40, max_length=500)
    # Phase 2.4: FAQs in same Grok call (mirrors article_enrichment pattern).
    # 0-8 allowed so products with sparse context can still ship a TL;DR.
    faqs: List[FAQItem] = Field(default_factory=list, max_items=8)
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_signals: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


# ============ Grok system prompt ============


SYSTEM_PROMPT = """Eres un experto en AEO (Answer Engine Optimization) y SEO para Example Store, una tienda mexicana de refacciones para transmisiones automáticas. Tu trabajo es generar un TL;DR óptimo para que motores de IA (ChatGPT, Perplexity, Google AI Overviews, Bing Copilot) lo citen directamente como respuesta a consultas de productos.

REGLAS CRÍTICAS:

1. **Idioma**: Español de México. Vocabulario técnico automotriz mexicano (refacción NO repuesto, transmisión NO caja, empaques NO juntas).

2. **TL;DR Summary** (1-3 oraciones, ≤320 caracteres total):
   - PRIMERA oración: respuesta directa que contiene la entidad principal en las primeras 8 palabras. Debe incluir: tipo de pieza + código(s) de transmisión compatibles + variante de marca/calidad si aplica.
   - SEGUNDA oración (opcional): contexto técnico clave — compatibilidad de vehículos o nivel de reconstrucción (servicio normal, rebuild, overhaul, profesional).
   - TERCERA oración (opcional): recomendación concreta de uso.
   - NO uses frases tipo "este producto es…" o "aquí tienes…".
   - NO repitas el título del producto verbatim.
   - Mantén bajo los 320 caracteres totales — AI Overviews puede truncar más allá.

3. **FAQs** (3-5 preguntas):
   - Cubre los tipos que usuarios reales buscan en productos de transmisión: compatibilidad (¿es compatible con [código]?), contenido del kit (¿qué incluye?), uso recomendado (¿para overhaul o servicio?), aplicación vehicular (¿qué vehículos?), diferencias técnicas/tier (¿qué diferencia con la versión [otra]?).
   - La PRIMERA oración de cada respuesta debe ser CITABLE (≤320 caracteres) — es lo que los motores de IA extraen y citan directamente.
   - Después de la primera oración puedes expandir con detalles técnicos o aclaraciones.
   - Sin markdown — texto plano o HTML básico (<strong>, <ul>, <li>) permitido.
   - Cada pregunta debe ser semánticamente distinta — no traslapes obvios.
   - Si la lista de códigos de transmisión es vacía o el producto no parece de transmisión, puedes devolver `"faqs": []` — pero PRIORIZA generar al menos 3 FAQs cuando haya contexto suficiente.

4. **Hechos del contexto**: Los códigos de transmisión y fitments provistos son la fuente de verdad. NO inventes compatibilidad. Si el producto no es claramente una refacción de transmisión (ej. fluido, herramienta, accesorio genérico), genera un TL;DR honesto describiendo lo que SÍ es.

5. **Confidence** (0.0–1.0):
   - 0.9+: producto con transmisiones identificadas, descripción rica, fitments disponibles
   - 0.7–0.9: datos suficientes (título + descripción) pero algunos huecos
   - <0.7: información insuficiente — el sistema NO publica automáticamente cuando confidence <0.7.

6. Devuelve SOLO JSON válido con esta forma exacta:
{
  "tldr_summary": "<1-3 oraciones, ≤320 caracteres, español MX>",
  "faqs": [
    {"q": "<pregunta natural>", "a": "<respuesta; primera oración ≤320 caracteres>"},
    ... 3 a 5 items (o [] si no hay contexto suficiente)
  ],
  "confidence": <float 0.0-1.0>
}

Sin markdown wrapping, sin explicación previa, sin comentarios.
"""


# ============ Service ============


class ProductEnrichmentService:
    """Generates and writes product TL;DR summaries."""

    def __init__(self):
        self.grok = GrokProvider()

    async def enrich_product(
        self,
        product_id: str,
        dry_run: bool = True,
        write_threshold: float = 0.7,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Generate a TL;DR for the product and optionally write to Shopify.

        Args:
            product_id: Internal Product.id (== shopify_id in this project).
            dry_run: If True, generate but don't write. Default True for safety.
            write_threshold: Min confidence to publish. Default 0.7.
            db: SQLAlchemy session; opens its own if not provided.

        Returns:
            dict with tldr_summary, confidence, source_signals, warnings,
            written, dry_run, skip_reason, product_id, product_title.
        """
        logger.info(f"[product-enrich] start product_id={product_id} dry_run={dry_run}")

        owns_db = False
        if db is None:
            db = SessionLocal()
            owns_db = True
        try:
            product = db.query(Product).filter(Product.id == product_id).first()
            if product is None:
                raise ValueError(f"Product {product_id} not found in local DB")

            context = self._gather_context(product)
            result = await self._generate(product, context)
            result = self._validate(result)
        finally:
            if owns_db:
                db.close()

        written = False
        skip_reason: Optional[str] = None
        if dry_run:
            skip_reason = "dry_run=true"
        elif result.confidence < write_threshold:
            skip_reason = (
                f"confidence {result.confidence:.2f} < threshold {write_threshold}"
            )
        else:
            payload: Dict[str, Any] = {"product_tldr_summary": result.tldr_summary}
            if result.faqs:
                # Phase 2.4: write FAQs as a separate JSON metafield. Theme emits
                # them as a standalone FAQPage JSON-LD script block.
                payload["product_faqs"] = [
                    {"q": faq.q, "a": faq.a} for faq in result.faqs
                ]
            # Phase 2.5: write the classified rebuild_tier alongside, so the
            # theme can emit it as additionalProperty in the same metafield
            # write call. Skip if the classifier returned None (unknown brand).
            if context.get("rebuild_tier"):
                payload["rebuild_tier"] = context["rebuild_tier"]
            ok = shopify_service.update_product_seo_metafields(
                product.shopify_id,
                payload,
            )
            written = bool(ok)
            if not ok:
                skip_reason = "shopify_write_failed"

        payload = result.dict()
        payload["written"] = written
        payload["dry_run"] = dry_run
        payload["skip_reason"] = skip_reason
        payload["product_id"] = product_id
        payload["product_title"] = product.title
        payload["product_sku"] = product.sku
        return payload

    # ---- Context gathering ----

    def _gather_context(self, product: Product) -> Dict[str, Any]:
        from app.services.rebuild_tier import classify_rebuild_tier, repair_intent_label

        desc_text = self._strip_html(product.current_description_html or "")
        codes = list(product.transmission_codes or [])
        primary_code = product.transmission_code or (codes[0] if codes else None)

        # Top vehicle fitments — first 8 so the prompt stays compact
        fitments_compact: List[str] = []
        for f in (product.cached_vehicle_fitments or [])[:8]:
            if not isinstance(f, dict):
                continue
            make = (f.get("make") or "").strip()
            model = (f.get("modelo") or f.get("model") or "").strip()
            yr_s = f.get("year_start") or ""
            yr_e = f.get("year_end") or ""
            tm = (f.get("transmission_model") or "").strip()
            parts = [p for p in (make, model, f"{yr_s}-{yr_e}".strip("-")) if p]
            entry = " ".join(parts)
            if tm:
                entry = f"{entry} ({tm})"
            if entry.strip():
                fitments_compact.append(entry.strip())

        # Phase 2.5: classify rebuild tier from vendor + product_type so Grok
        # uses the explicit tier instead of inferring (and overstating) it
        # from description marketing copy.
        rebuild_tier = classify_rebuild_tier(product.vendor, product.product_type)

        return {
            "title": product.title or "",
            "description_text": desc_text[:4000],
            "transmission_codes": codes,
            "primary_code": primary_code,
            "vendor": product.vendor or "",
            "product_type": product.product_type or "",
            "vehicle_fitments_compact": fitments_compact,
            "rebuild_tier": rebuild_tier,
            "repair_intent_label": repair_intent_label(rebuild_tier),
        }

    # ---- Grok call ----

    async def _generate(
        self, product: Product, context: Dict[str, Any]
    ) -> ProductEnrichmentResult:
        user_prompt = self._build_user_prompt(context)

        response = await self.grok.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            json_mode=True,
            temperature=0.3,
        )

        raw = response.get("content") or response.get("text") or response.get("response")
        if raw is None and isinstance(response, dict):
            raw = response
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as e:
                logger.error(f"[product-enrich] Grok returned non-JSON: {raw[:500]}")
                raise ValueError(f"Grok response not valid JSON: {e}")
        else:
            parsed = raw

        # Backend-injected metadata
        parsed["source_signals"] = {
            "transmission_codes_count": len(context.get("transmission_codes", [])),
            "transmission_codes": context.get("transmission_codes", []),
            "primary_code": context.get("primary_code"),
            "fitment_count": len(context.get("vehicle_fitments_compact", [])),
            "description_word_count": len(context["description_text"].split()),
            "has_vendor": bool(context.get("vendor")),
            "has_product_type": bool(context.get("product_type")),
        }
        return ProductEnrichmentResult(**parsed)

    def _build_user_prompt(self, context: Dict[str, Any]) -> str:
        # Phase 2.5c: tier is NOT injected into the copy prompt anymore. It
        # stays in the rebuild_tier metafield (machine-readable structured
        # signal for Google Shopping / agentic protocols). Human-readable
        # TL;DR + FAQs follow Example Store's aspirational marketing voice, free
        # of tier-imposed ceilings. See feedback_aspirational_copy.md —
        # tiering the copy actively hurt sales positioning. Two audiences,
        # two different optimizations.
        sections: List[str] = [
            f"## Producto\nTítulo: {context['title']}\nVendor: {context.get('vendor') or '(no especificado)'}\nProduct type: {context.get('product_type') or '(no especificado)'}",
        ]

        codes = context.get("transmission_codes") or []
        if codes:
            sections.append(
                "## Códigos de transmisión compatibles (fuente de verdad)\n"
                + ", ".join(codes)
            )
        else:
            sections.append(
                "## Códigos de transmisión\n"
                "(ninguno detectado — el producto puede no ser una refacción de transmisión específica)"
            )

        if context.get("vehicle_fitments_compact"):
            fitments_lines = [f"- {f}" for f in context["vehicle_fitments_compact"]]
            sections.append(
                "## Vehículos compatibles (top 8)\n" + "\n".join(fitments_lines)
            )

        sections.append(
            "## Descripción actual (primeros 4000 caracteres, HTML removido)\n"
            + (context["description_text"] or "(descripción vacía)")
        )

        sections.append(
            "## Formato de salida\n"
            "Devuelve SOLO JSON válido con esta forma exacta:\n"
            "{\n"
            '  "tldr_summary": "<1-3 oraciones, ≤320 caracteres, español MX>",\n'
            '  "faqs": [\n'
            '    {"q": "<pregunta natural en español>", "a": "<respuesta; primera oración ≤320 caracteres>"}\n'
            "    ... 3 a 5 items (o [] si el producto no tiene contexto suficiente)\n"
            "  ],\n"
            '  "confidence": <float 0.0-1.0>\n'
            "}"
        )

        return "\n\n".join(sections)

    # ---- Validation ----

    def _validate(self, result: ProductEnrichmentResult) -> ProductEnrichmentResult:
        warnings: List[str] = []
        if len(result.tldr_summary) > 320:
            warnings.append(
                f"TL;DR es {len(result.tldr_summary)} caracteres (>320 puede truncarse en AI Overviews)"
            )
        # Detect leftover scaffold phrases the prompt rules forbid
        forbidden_phrases = ["este producto es", "aquí tienes", "este artículo"]
        lower = result.tldr_summary.lower()
        for phrase in forbidden_phrases:
            if phrase in lower:
                warnings.append(f"TL;DR contiene frase prohibida: '{phrase}'")

        # FAQ validation: first-sentence length + dedup
        seen_norms: set = set()
        deduped: List[FAQItem] = []
        for i, faq in enumerate(result.faqs):
            first_sentence = re.split(r"(?<=[.!?])\s", faq.a, maxsplit=1)[0]
            if len(first_sentence) > 320:
                warnings.append(
                    f"FAQ #{i+1} primera oración es {len(first_sentence)} caracteres (>320 puede truncarse)"
                )
            norm = re.sub(r"[¿?¡!.,;:]", "", faq.q).lower().strip()
            if norm in seen_norms:
                warnings.append(f"FAQ duplicada removida: {faq.q}")
                continue
            seen_norms.add(norm)
            deduped.append(faq)
        result.faqs = deduped

        result.warnings = warnings
        return result

    # ---- Helpers ----

    def _strip_html(self, html: str) -> str:
        text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
        text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text


# Module-level singleton (parallel pattern to article_enrichment_service)
product_enrichment_service = ProductEnrichmentService()
