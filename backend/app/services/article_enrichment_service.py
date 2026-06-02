"""
Article Enrichment Service

Generates AEO-optimized TL;DR summaries + FAQ sets for Shopify blog articles
by combining real signal sources:
  - Article content (Shopify Article API)
  - DataForSEO PAA (People Also Ask — the literal questions real users search)
  - Google Search Console top queries for the article URL (actual landing queries)
  - Article tags / first tag as target keyword

Output is validated, then written to three article metafields read by the
Empire V8 AEO article template:
  - custom.article_metafields_tldr_summary  (multi_line_text)
  - custom.article_metafields_faqs          (json — [{q, a}, ...])
  - custom.article_metafields_last_reviewed_at  (date)

The same metafields flow into JSON-LD (BlogPosting.abstract, FAQPage,
SpeakableSpecification) via `Empire V8/snippets/structured-data.liquid` +
`example-store-article-faq.liquid`.

Endpoint: POST /api/v1/aeo/articles/{article_id}/enrich
"""

import json
import re
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models.aeo_models import FaultCode
from app.services.llm_providers.grok import GrokProvider
from app.services.dataforseo_service import dataforseo_service
from app.services.google_api_service import GoogleApiService
from app.services.shopify_service import shopify_service

logger = get_logger("article_enrichment_service")

# OBD-II fault code pattern: [PBCU] + digit(0-3) + 3 hex chars
# Mirrors Empire V8's `example-store-article-fault-chips.liquid` detection logic.
FAULT_CODE_PATTERN = re.compile(r"\b([PBCU][0-3][0-9A-F]{3})\b", re.IGNORECASE)


# ============ Pydantic schemas ============

class FAQItem(BaseModel):
    q: str = Field(..., min_length=10, max_length=200)
    a: str = Field(..., min_length=20, max_length=2000)


class EnrichmentResult(BaseModel):
    tldr_summary: str = Field(..., min_length=40, max_length=500)
    faqs: List[FAQItem] = Field(..., min_items=3, max_items=8)
    confidence: float = Field(..., ge=0.0, le=1.0)
    target_keyword: Optional[str] = None
    source_signals: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


# ============ System prompt ============

SYSTEM_PROMPT = """Eres un experto en AEO (Answer Engine Optimization) y SEO para Example Store, una tienda mexicana de refacciones para transmisiones automáticas. Tu trabajo es generar contenido optimizado para que motores de IA (Google AI Overviews, ChatGPT, Perplexity, Claude) extraigan y citen como respuesta directa.

REGLAS CRÍTICAS:

1. **Idioma**: Español de México. Vocabulario técnico automotriz mexicano (refacción, NO repuesto; transmisión, NO caja).

2. **TL;DR Summary** (1-3 oraciones, ≤320 caracteres total):
   - PRIMERA oración: respuesta directa que contiene la entidad principal (código de falla, modelo de transmisión, tipo de parte) en las primeras 8 palabras.
   - SEGUNDA oración: causa más probable o contexto técnico clave.
   - TERCERA oración (opcional): recomendación concreta de acción o producto.
   - NO repetir el título del artículo verbatim.
   - NO usar frases tipo "este artículo explica..." o "aquí veremos...".

3. **FAQs** (3-5 preguntas):
   - Las preguntas deben coincidir con cómo los usuarios REALMENTE buscan. Usa las "People Also Ask" y "queries reales de Search Console" provistas como fuente primaria.
   - Variedad de tipos: definición, síntomas, causa, solución, costo/compatibilidad.
   - La PRIMERA oración de cada respuesta debe ser citable (≤320 caracteres) — es lo que los motores de IA extraen y citan.
   - Después de la primera oración, puedes expandir con detalles.
   - Sin markdown — texto plano o HTML básico permitido (<strong>, <a href>, <ul>, <li>).
   - Cada pregunta debe ser semánticamente distinta — no preguntas que se solapen.
   - Si el artículo es sobre un código de falla específico, AL MENOS UNA pregunta debe ser del estilo "¿Qué refacción/producto necesito para resolver [código]?".

4. **Hechos del Knowledge Graph**: Si la sección "Hechos verificados" está presente, esos son datos estructurados de nuestro grafo de conocimiento (códigos de falla, síntomas, causas, transmisiones, partes recomendadas). Trátalos como la fuente de verdad técnica — el cuerpo del artículo puede tener inexactitudes, los hechos del KG no. Cita números/listas del KG textualmente cuando apliquen.

5. **Confidence** (0.0–1.0):
   - 0.9+: Datos sólidos (artículo + PAA + GSC + hechos del Knowledge Graph alineados).
   - 0.7–0.9: Datos suficientes pero algunos huecos (ej. PAA disponible pero sin KG).
   - <0.7: Información insuficiente — el contenido generado puede ser genérico. El sistema NO publicará automáticamente cuando confidence <0.7.

6. Devuelve SOLO JSON válido. Sin markdown wrapping, sin explicación previa, sin comentarios.
"""


# ============ Service ============

class ArticleEnrichmentService:
    """
    Orchestrates the article enrichment pipeline:
        article + PAA + GSC -> Grok -> validated metafields -> Shopify
    """

    def __init__(self):
        self.grok = GrokProvider()
        self.google = GoogleApiService()

    async def enrich_article(
        self,
        article_id: int,
        blog_id: Optional[int] = None,
        target_keyword: Optional[str] = None,
        dry_run: bool = True,
        write_threshold: float = 0.7,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Generate AEO-optimized TL;DR + FAQs for an article.

        Args:
            article_id: Shopify article ID
            blog_id: Shopify blog ID. If None, auto-discovers by iterating blogs.
            target_keyword: Target keyword for SERP analysis. If None, derived
                from the article's first tag, falling back to its title.
            dry_run: If True, generate but do not write to Shopify.
            write_threshold: Minimum confidence required to write back when
                dry_run=False. Below this, writes are skipped (review queue).
            db: SQLAlchemy session for Knowledge Graph lookups. If None, a
                short-lived session is opened internally.

        Returns:
            dict with tldr_summary, faqs, confidence, target_keyword,
            source_signals, warnings, written, dry_run.
        """
        logger.info(f"[enrich] start article_id={article_id} dry_run={dry_run}")

        article = self._fetch_article(article_id, blog_id)
        if article is None:
            raise ValueError(f"Article {article_id} not found in Shopify")

        keyword = target_keyword or self._derive_keyword(article)
        logger.info(f"[enrich] article='{article.title}' target_keyword='{keyword}'")

        owns_db = False
        if db is None:
            db = SessionLocal()
            owns_db = True
        try:
            context = await self._gather_context(article, keyword, db)
        finally:
            if owns_db:
                db.close()

        result = await self._generate(article, keyword, context)
        result = self._validate(result)

        written = False
        skip_reason = None
        if dry_run:
            skip_reason = "dry_run=true"
        elif result.confidence < write_threshold:
            skip_reason = f"confidence {result.confidence:.2f} < threshold {write_threshold}"
        else:
            written = self._write_metafields(article, result)
            if not written:
                skip_reason = "shopify_write_failed"

        payload = result.dict()
        payload["written"] = written
        payload["dry_run"] = dry_run
        payload["skip_reason"] = skip_reason
        payload["article_id"] = article.id
        payload["article_title"] = article.title
        return payload

    # ---- Article fetch ----

    def _fetch_article(self, article_id: int, blog_id: Optional[int]):
        shopify_service._ensure_initialized()
        import shopify

        if blog_id:
            try:
                return shopify.Article.find(article_id, blog_id=blog_id)
            except Exception as e:
                logger.warning(f"[enrich] direct fetch failed for blog_id={blog_id}: {e}")

        # Auto-discover blog_id
        try:
            for blog in shopify.Blog.find():
                try:
                    art = shopify.Article.find(article_id, blog_id=blog.id)
                    if art is not None:
                        return art
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"[enrich] blog iteration failed: {e}")
        return None

    # ---- Keyword derivation ----

    def _derive_keyword(self, article) -> str:
        tags = (article.tags or "")
        if isinstance(tags, str) and tags.strip():
            first_tag = tags.split(",")[0].strip()
            if first_tag:
                return first_tag
        return article.title or ""

    # ---- Context gathering ----

    async def _gather_context(self, article, keyword: str, db: Session) -> Dict[str, Any]:
        body_text = self._strip_html(article.body_html or "")
        ctx: Dict[str, Any] = {
            "article_title": article.title or "",
            "article_body_text": body_text[:6000],
            "target_keyword": keyword,
            "paa_questions": [],
            "gsc_queries": [],
            "fault_code_facts": [],
        }

        # DataForSEO PAA
        try:
            serp = await dataforseo_service.fetch_serp(keyword, db=db)
            if serp and not serp.get("error"):
                paa = serp.get("people_also_ask") or []
                ctx["paa_questions"] = [
                    {
                        "q": (p.get("question") or "").strip(),
                        "snippet": (p.get("answer") or "")[:300],
                    }
                    for p in paa[:10]
                    if p.get("question")
                ]
        except Exception as e:
            logger.warning(f"[enrich] PAA fetch failed for '{keyword}': {e}")

        # GSC queries for the article URL
        try:
            blog_handle = self._get_blog_handle(article)
            if blog_handle and getattr(article, "handle", None):
                article_path = f"/blogs/{blog_handle}/{article.handle}"
                gsc_queries = self.google.get_search_console_queries_for_url(
                    article_path, days=90, limit=20
                )
                ctx["gsc_queries"] = gsc_queries or []
        except Exception as e:
            logger.warning(f"[enrich] GSC fetch failed: {e}")

        # Knowledge graph: fault-code facts grounded against article body + title
        try:
            ctx["fault_code_facts"] = self._lookup_fault_codes(
                f"{ctx['article_title']} {body_text} {keyword}", db
            )
        except Exception as e:
            logger.warning(f"[enrich] KG lookup failed: {e}")

        return ctx

    def _lookup_fault_codes(self, text: str, db: Session) -> List[Dict[str, Any]]:
        """Scan text for OBD-II fault codes and pull structured KG facts."""
        if not text:
            return []

        codes = {m.group(1).upper() for m in FAULT_CODE_PATTERN.finditer(text)}
        if not codes:
            return []

        # Cap to top 5 codes so we don't bloat the prompt for catch-all articles
        rows = (
            db.query(FaultCode)
            .filter(FaultCode.code.in_(list(codes)[:5]))
            .all()
        )

        facts: List[Dict[str, Any]] = []
        for fc in rows:
            facts.append({
                "code": fc.code,
                "name": fc.name,
                "description": (fc.description or "")[:500],
                "severity": fc.severity,
                "transmissions": fc.transmissions or [],
                "vehicles": fc.vehicles or [],
                "common_causes": fc.common_causes or [],
                "symptoms": fc.symptoms_text or [],
            })
        return facts

    def _get_blog_handle(self, article) -> Optional[str]:
        try:
            import shopify
            blog_id = getattr(article, "blog_id", None)
            if not blog_id:
                return None
            blog = shopify.Blog.find(blog_id)
            return getattr(blog, "handle", None) if blog else None
        except Exception:
            return None

    def _strip_html(self, html: str) -> str:
        text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
        text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    # ---- Grok call ----

    async def _generate(self, article, keyword: str, context: Dict[str, Any]) -> EnrichmentResult:
        user_prompt = self._build_user_prompt(article, keyword, context)

        response = await self.grok.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            json_mode=True,
            temperature=0.3,
        )

        # Grok returns various shapes depending on wrapper; try common keys
        raw = response.get("content") or response.get("text") or response.get("response")
        if raw is None and isinstance(response, dict):
            raw = response

        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as e:
                logger.error(f"[enrich] Grok returned non-JSON: {raw[:500]}")
                raise ValueError(f"Grok response not valid JSON: {e}")
        else:
            parsed = raw

        # Backend-injected metadata (not from Grok)
        parsed["source_signals"] = {
            "paa_count": len(context.get("paa_questions", [])),
            "gsc_query_count": len(context.get("gsc_queries", [])),
            "fault_code_count": len(context.get("fault_code_facts", [])),
            "fault_codes": [fc["code"] for fc in context.get("fault_code_facts", [])],
            "article_word_count": len(context["article_body_text"].split()),
        }
        parsed["target_keyword"] = keyword

        return EnrichmentResult(**parsed)

    def _build_user_prompt(self, article, keyword: str, context: Dict[str, Any]) -> str:
        sections = [
            f"## Artículo\nTítulo: {article.title}\nKeyword objetivo: {keyword}",
            f"## Cuerpo del artículo (primeros 6000 caracteres, HTML removido)\n{context['article_body_text']}",
        ]

        paa = context.get("paa_questions", [])
        if paa:
            paa_lines = [f"- {p['q']}" for p in paa]
            sections.append(
                "## People Also Ask (preguntas reales de Google para esta keyword)\n"
                + "\n".join(paa_lines)
            )

        gsc = context.get("gsc_queries", [])
        if gsc:
            gsc_lines = [
                f"- '{q['query']}' — {q['impressions']} impresiones, {q['clicks']} clicks, posición media {q['position']:.1f}"
                for q in gsc[:15]
            ]
            sections.append(
                "## Queries reales que llevan tráfico a este artículo (Search Console, últimos 90 días)\n"
                + "\n".join(gsc_lines)
            )

        facts = context.get("fault_code_facts", [])
        if facts:
            fact_blocks = []
            for fc in facts:
                lines = [f"### {fc['code']} — {fc['name'] or '(sin nombre)'}"]
                if fc.get("severity"):
                    lines.append(f"Severidad: {fc['severity']}")
                if fc.get("description"):
                    lines.append(f"Descripción: {fc['description']}")
                if fc.get("symptoms"):
                    lines.append("Síntomas: " + ", ".join(fc["symptoms"]))
                if fc.get("common_causes"):
                    lines.append("Causas comunes: " + ", ".join(fc["common_causes"]))
                if fc.get("transmissions"):
                    lines.append("Transmisiones afectadas: " + ", ".join(fc["transmissions"]))
                if fc.get("vehicles"):
                    lines.append("Vehículos afectados: " + ", ".join(fc["vehicles"]))
                fact_blocks.append("\n".join(lines))
            sections.append(
                "## Hechos verificados (Knowledge Graph — fuente de verdad técnica)\n"
                + "\n\n".join(fact_blocks)
            )

        sections.append(
            "## Formato de salida\n"
            "Devuelve SOLO JSON válido con esta forma exacta:\n"
            "{\n"
            '  "tldr_summary": "<1-3 oraciones, ≤320 caracteres, español MX>",\n'
            '  "faqs": [\n'
            '    {"q": "<pregunta natural>", "a": "<respuesta; primera oración ≤320 caracteres>"},\n'
            "    ... 3 a 5 items\n"
            "  ],\n"
            '  "confidence": <float 0.0-1.0>\n'
            "}"
        )

        return "\n\n".join(sections)

    # ---- Validation ----

    def _validate(self, result: EnrichmentResult) -> EnrichmentResult:
        warnings: List[str] = []

        if len(result.tldr_summary) > 320:
            warnings.append(
                f"TL;DR es {len(result.tldr_summary)} caracteres (>320 puede truncarse en AI Overviews)"
            )

        for i, faq in enumerate(result.faqs):
            first_sentence = re.split(r"(?<=[.!?])\s", faq.a, maxsplit=1)[0]
            if len(first_sentence) > 320:
                warnings.append(
                    f"FAQ #{i+1} primera oración es {len(first_sentence)} caracteres (>320)"
                )

        # Deduplicate near-identical questions
        seen = set()
        deduped: List[FAQItem] = []
        for faq in result.faqs:
            norm = re.sub(r"[¿?¡!.,;:]", "", faq.q).lower().strip()
            if norm in seen:
                warnings.append(f"FAQ duplicada removida: {faq.q}")
                continue
            seen.add(norm)
            deduped.append(faq)
        result.faqs = deduped

        result.warnings = warnings
        return result

    # ---- Shopify write ----

    def _write_metafields(self, article, result: EnrichmentResult) -> bool:
        try:
            shopify_service._ensure_initialized()
            import shopify

            today = datetime.now().strftime("%Y-%m-%d")
            faqs_json = json.dumps(
                [{"q": f.q, "a": f.a} for f in result.faqs],
                ensure_ascii=False,
            )

            payloads = [
                {
                    "namespace": "custom",
                    "key": "article_metafields_tldr_summary",
                    "value": result.tldr_summary,
                    "type": "multi_line_text_field",
                    "owner_resource": "article",
                    "owner_id": article.id,
                },
                {
                    "namespace": "custom",
                    "key": "article_metafields_faqs",
                    "value": faqs_json,
                    "type": "json",
                    "owner_resource": "article",
                    "owner_id": article.id,
                },
                {
                    "namespace": "custom",
                    "key": "article_metafields_last_reviewed_at",
                    "value": today,
                    "type": "date",
                    "owner_resource": "article",
                    "owner_id": article.id,
                },
            ]

            for data in payloads:
                mf = shopify.Metafield(data)
                if not mf.save():
                    err = getattr(mf, "errors", None)
                    logger.error(
                        f"[enrich] metafield save failed key={data['key']} errors={err.full_messages() if err else 'unknown'}"
                    )
                    return False

            logger.info(
                f"[enrich] wrote 3 metafields to article_id={article.id} title='{article.title}'"
            )
            return True
        except Exception as e:
            logger.error(f"[enrich] write_metafields exception: {e}", exc_info=True)
            return False


article_enrichment_service = ArticleEnrichmentService()
