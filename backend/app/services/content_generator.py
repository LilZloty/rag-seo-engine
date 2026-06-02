"""
Content Generator Service - SEO-optimized product content generation

This service is being refactored to use modular components:
- Prompt management: app.services.content.PromptMerger
- Response normalization: app.services.content.ResponseNormalizer

Refactored per Modularization Plan:
- Prompts merged via PromptMerger
- Responses normalized via ResponseNormalizer
- LLM calls delegated to llm_service
"""

import httpx
import hashlib
import time
import logging
from typing import List, Dict, Tuple, Optional
from app.core.config import settings
from app.services.content import PromptMerger, PromptTemplateManager, ResponseNormalizer

# Structured logging setup
logger = logging.getLogger("content_generator")

# Token estimation function (for backward compatibility)
def estimate_tokens(text: str) -> int:
    """Estimate token count using a simple word-based heuristic (approx 1.3 tokens per word)."""
    return int(len(text.split()) * 1.3)


class ContentGeneratorService:
    """Content generation service using modular components."""

    def __init__(self):
        from app.services.qdrant_service import qdrant_service
        from app.services.llm_service import llm_service
        from app.services.shopify_service import shopify_service

        self.qdrant_service = qdrant_service
        self.llm_service = llm_service
        self.shopify_service = shopify_service
        self.prompt_merger = PromptMerger()

    async def generate_for_product(
        self,
        product_id: str,
        library_ids: Optional[List[str]] = None,
        template_id: Optional[str] = None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        analysis_insights: Optional[Dict] = None  # NEW: Grok analysis insights
    ) -> Dict:
        """
        Generate SEO content for a product using RAG-powered context retrieval.

        Enhanced with analysis insights integration:
        - Uses Grok analysis recommendations to guide content
        - Includes keyword opportunities targets
        - Incorporates suggested meta tags and FAQ

        Refactored to use:
        - PromptTemplateManager for template retrieval
        - PromptMerger for prompt assembly
        - ResponseNormalizer for response processing
        """
        from app.services.document_ingestion_service import document_ingestion_service
        from app.db.session import SessionLocal
        from app.models.library import PromptTemplate, Library, document_library_association
        from sqlalchemy import select

        product = self.shopify_service.get_product_by_id(product_id)

        if not product:
            raise ValueError(f"Product {product_id} not found")

        # Fetch analytics data from local DB (freshened by the product analytics endpoint)
        db = SessionLocal()
        from app.models.product import Product as DBProduct
        db_product = db.query(DBProduct).filter(DBProduct.id == product_id).first()
        gsc_impressions = getattr(db_product, 'gsc_impressions', 0) if db_product else 0
        gsc_position = getattr(db_product, 'gsc_position', 0) if db_product else 0
        ga4_sessions = getattr(db_product, 'ga4_sessions', 0) if db_product else 0
        sold_30d = getattr(db_product, 'sold_30d', 0) if db_product else 0
        sold_90d = getattr(db_product, 'sold_90d', 0) if db_product else 0
        # Phase 1.5: refresh transmission_codes from the latest title+desc so
        # the metafield write below uses fresh data even if the backfill
        # hasn't run for this product. Best-effort — never block content gen.
        #
        # We also parse the curator-declared "Compatibilidad:" line into a
        # narrower closed list for the per-row vehicle table. The cached
        # transmission_codes array unions every code mentioned anywhere in
        # title+description and over-includes for kit products (a universal
        # filter mentioning 6L50/6L90 leaks into kits that only fit 6L80).
        compatibility_codes: List[str] = []
        existing_vehicle_rows: List[Dict] = []
        if db_product:
            try:
                from app.services.aeo.knowledge_graph import create_knowledge_graph_manager
                _kg = create_knowledge_graph_manager(db)
                if _kg.refresh_codes_for_product(db_product):
                    db.commit()
                _desc_html = getattr(product, 'body_html', '') or ''
                compatibility_codes = self._extract_compatibility_codes(_desc_html, _kg)
                existing_vehicle_rows = self._parse_existing_vehicle_table(_desc_html, _kg)
            except Exception as _kg_err:
                logger.warning(f"transmission_codes refresh skipped: {_kg_err}")
        # Phase 1.2 multi-code cross-reference list — pushed through to a list
        # metafield below so the theme emits multiple additionalProperty entries.
        db_transmission_codes = (
            getattr(db_product, 'transmission_codes', None) if db_product else None
        )
        db.close()

        # Fetch structured vehicle fitments from Shopify metaobjects — these
        # carry transmission_model codes (JF506E, A604, ZF8HP) that are NOT in
        # the raw description HTML. Pass them to the LLM so the generated table
        # can show the transmission column, not just engine/drivetrain.
        fitments_for_prompt = []
        try:
            full_details = self.shopify_service.get_product_full_details(product_id)
            if full_details:
                fitments_for_prompt = full_details.get('vehicle_fitments', []) or []
        except Exception as _fit_err:
            print(f"[ContentGen] Could not fetch structured fitments: {_fit_err}")

        # Transmission code alias expansion — same unit may sell under multiple
        # OEM names (A44DE = 03-72LE, AX4N = 4F50N, ZF8HP = 845RE, etc.). Mexican
        # mechanics search whichever name their manual uses. Passing all aliases
        # into the prompt lets the LLM fold them into meta/title/body naturally.
        trans_aliases = self._get_transmission_alternates(product.title)

        # Extract metadata from product title — done before product_info so the
        # primary code can be threaded in for per-row vehicle table population.
        transmission_code = self._extract_transmission_code(product.title)
        part_type = self._extract_part_type(product.title)
        brand = self._extract_brand(product.title)

        # Build complete product info for LLM
        _all_images = self.shopify_service.get_product_images(product_id)
        product_info = {
            'title': product.title,
            'sku': product.variants[0].sku if product.variants else '',
            'handle': product.handle,
            'image_filenames': [img.get('filename', '') for img in _all_images],
            '_image_urls': [img.get('src', '') for img in _all_images if img.get('src')],
            'description': getattr(product, 'body_html', '') or '',
            'vendor': getattr(product, 'vendor', '') or '',
            'product_type': getattr(product, 'product_type', '') or '',
            'tags': getattr(product, 'tags', []) or [],
            'meta_title': getattr(product, 'metafields_global_title_tag', '') or '',
            'meta_description': getattr(product, 'metafields_global_description_tag', '') or '',
            'gsc_impressions': gsc_impressions,
            'gsc_position': gsc_position,
            'ga4_sessions': ga4_sessions,
            'sold_30d': sold_30d,
            'sold_90d': sold_90d,
            'vehicle_fitments': fitments_for_prompt,
            'transmission_aliases': trans_aliases,
            'primary_transmission_code': transmission_code or '',
            'compatibility_codes': compatibility_codes,
            # Wider product-level code list (title + description union). Used as the
            # closed-list for per-vehicle Transmisión column mapping — the column
            # describes the vehicle's OEM transmission, not the product fit. The
            # narrower compatibility_codes is kept for cases where this is unavailable.
            'transmission_codes': db_transmission_codes or [],
            # Pre-parsed rows from the existing <h4>Vehiculos</h4> table. Rows
            # whose Transmisión cell already contains a recognised code are
            # passed through to the new table unchanged — never re-guessed by
            # the LLM. Highest-priority source for per-row transmission codes.
            'existing_vehicle_rows': existing_vehicle_rows,
        }

        # --- SEO keyword intelligence: real queries from GSC ---
        product_info['seo_keyword_intelligence'] = self._gather_keyword_intelligence(
            db_product, product_info, transmission_code, part_type, brand,
        )

        # --- Rank transmission codes by search demand ---
        product_info['ranked_transmission_codes'] = self._rank_transmission_codes(
            db_transmission_codes or [], transmission_code,
        )

        # --- Analyze product images with vision for accurate alt tags ---
        image_descriptions = await self._analyze_product_images(
            product_info.get('_image_urls', []),
            product_info['title'],
        )
        if image_descriptions:
            product_info['image_descriptions'] = image_descriptions

        print(f"[ContentGen] Product info: title={product_info['title']}")

        logger.info("Starting content generation", extra={
            "product_id": product_id,
            "product_title": product.title,
            "brand": brand,
            "transmission_code": transmission_code,
            "part_type": part_type,
            "library_count": len(library_ids) if library_ids else 0
        })

        # Collect prompts with priority using PromptTemplateManager
        instruction_tuples: List[Tuple[int, str, str]] = []

        with SessionLocal() as db:
            template_manager = PromptTemplateManager(db)

            # Get prompts from libraries using the modular system
            if library_ids:
                library_prompts = template_manager.get_prompts_for_libraries(library_ids)
                instruction_tuples.extend(library_prompts)

            # Get override template if specified
            if template_id:
                template = template_manager.get_template(template_id)
                if template:
                    priority = template.priority if template.priority is not None else 100
                    instruction_tuples.append((priority, template.system_instructions, f"override:{template.name}"))

        # Merge prompts using PromptMerger
        conflict_header = (
            "NOTA: Si instrucciones posteriores contradicen instrucciones anteriores, "
            "prioriza las instrucciones más recientes (las que aparecen al final).\n\n"
        )

        merge_result = self.prompt_merger.merge_prompts(instruction_tuples, conflict_header)
        system_prompt = merge_result.merged_prompt if merge_result.merged_prompt else self.llm_service._get_system_prompt()

        # Get document IDs for selected libraries
        document_ids = None
        with SessionLocal() as db:
            if library_ids:
                stmt = select(document_library_association.c.document_id).where(
                    document_library_association.c.library_id.in_(library_ids)
                )
                results = db.execute(stmt).fetchall()
                document_ids = [r[0] for r in results]

        # Use RAG to retrieve relevant context
        rag_context = await document_ingestion_service.retrieve_rag_context(
            product_title=product.title,
            brands=[brand] if brand else [],
            transmission_codes=[transmission_code] if transmission_code else [],
            product_types=[part_type] if part_type else [],
            document_ids=document_ids,
            limit=10
        )

        # Also search legacy Qdrant collection
        try:
            query_text = f"{product.title} {product_info['sku']}"
            query_vector = await self._get_embedding_ollama(query_text)
            legacy_context = self.qdrant_service.search_parts(
                query_vector=query_vector,
                limit=3
            )
        except Exception as e:
            logger.error("Legacy context search failed", extra={"error": str(e)})
            print(f"Legacy context search failed")
            legacy_context = []

        combined_context = rag_context + legacy_context
        print(f"[RAG] Found {len(combined_context)} relevant chunks")

        # Web search fallback
        web_search_context = ""
        if settings.WEB_SEARCH_FALLBACK and (not library_ids or len(combined_context) < settings.WEB_SEARCH_MIN_RAG_CHUNKS):
            reason = "no library selected" if not library_ids else f"only {len(combined_context)} RAG chunks"
            print(f"[WebSearch] Triggering web search ({reason})")
            from app.services.web_search_service import web_search_service

            if web_search_service.is_configured():
                search_query = f"{product.title} {transmission_code or ''} especificaciones transmision automatica"
                search_results = await web_search_service.search(search_query, num_results=5)

                if search_results:
                    web_search_context = web_search_service.format_for_context(search_results)
                    for result in search_results:
                        combined_context.append({
                            "payload": {
                                "content": f"{result['title']}: {result['snippet']}",
                                "source_filename": result['link'],
                                "supplier": "web_search"
                            }
                        })

        # Get performance data for dynamic optimization
        performance_data = self._get_performance_data()

        # Format analysis insights for prompt enhancement
        analysis_context = self._format_analysis_insights(analysis_insights, product_info)
        if analysis_context:
            print(f"[ContentGen] Using analysis insights: {len(analysis_context)} chars")
            # Prepend analysis context to the combined context
            combined_context.insert(0, {
                "payload": {
                    "content": analysis_context,
                    "source_filename": "grok_analysis_insights",
                    "supplier": "ai_analysis"
                }
            })

        # Generate content using llm_service
        result = await self.llm_service.generate_content(
            product_info=product_info,
            context=combined_context,
            system_prompt=system_prompt,
            provider=provider,
            model_name=model_name,
            performance_data=performance_data,
            analysis_insights=analysis_insights
        )

        # Normalize response using ResponseNormalizer
        normalizer = ResponseNormalizer(product_info)
        normalized = normalizer.normalize(result)

        # Convert NormalizedContent to dict and add metadata
        result_dict = normalized.to_dict()

        # --- SEO ASSET LOCK (deterministic safety layer) ---
        # URL, meta title, and H1 are ranked assets — LLM instruction compliance is probabilistic.
        # This enforces the locks after normalization, regardless of what the LLM output.
        #
        # Lock priority:
        #   url_handle  → locked for HIGH + ESTABLISHED (any indexed URL must not change)
        #   meta_title  → locked for HIGH (primary ranking signal in SERPs)
        #   h1_title    → locked for HIGH (validated keyword structure)
        if analysis_insights:
            _tier = (
                analysis_insights.get("performance_tier")
                or (analysis_insights.get("primary_issue") or {}).get("performance_tier")
                or "DEVELOPING"
            )

            # 1. URL LOCK
            # Shopify auto-creates 301 redirects on handle changes, so no 404 risk.
            # However, changing a URL still causes:
            #   - Re-evaluation of URL keyword signals (Google reads the URL as content)
            #   - Ranking reset window while Google processes the redirect (days to weeks)
            # HIGH: hard lock — position 3-9 products cannot afford any reset window
            # ESTABLISHED: warn only — redirect covers the risk, but log for visibility
            _existing_handle = product_info.get("handle", "")
            _generated_handle = result_dict.get("url_handle", "")
            if _existing_handle and _generated_handle and _generated_handle != _existing_handle:
                if _tier == "HIGH":
                    print(
                        f"[SEOLock] URL hard-locked (HIGH) — reverting handle.\n"
                        f"  LLM proposed: '{_generated_handle}'\n"
                        f"  Kept:         '{_existing_handle}'"
                    )
                    result_dict["url_handle"] = _existing_handle
                elif _tier == "ESTABLISHED":
                    print(
                        f"[SEOLock] URL change WARNING (ESTABLISHED) — Shopify will auto-redirect,\n"
                        f"  but URL keyword signals will reset. Review before publishing.\n"
                        f"  LLM proposed: '{_generated_handle}'\n"
                        f"  Existing:     '{_existing_handle}'"
                    )
                    result_dict.setdefault("_seo_warnings", []).append(
                        f"URL change detected: '{_existing_handle}' → '{_generated_handle}'. "
                        f"Shopify will auto-redirect, but URL keyword signals reset on Google's next crawl. "
                        f"Review before publishing."
                    )

            # 2. META TITLE LOCK — primary SERP ranking signal; lock for HIGH
            _existing_meta = product_info.get("meta_title", "")
            _generated_meta = result_dict.get("meta_title", "")
            if _tier == "HIGH" and _existing_meta and _generated_meta and _generated_meta != _existing_meta:
                print(
                    f"[SEOLock] Meta title locked (HIGH) — reverting.\n"
                    f"  LLM proposed: '{_generated_meta}'\n"
                    f"  Kept:         '{_existing_meta}'"
                )
                result_dict["meta_title"] = _existing_meta

            # 3. H1 TITLE LOCK — validated keyword structure; lock for HIGH
            _existing_title = product_info.get("title", "")
            _generated_title = result_dict.get("h1_title", "")
            if _tier == "HIGH" and _existing_title and _generated_title and _generated_title != _existing_title:
                print(
                    f"[SEOLock] H1 title locked (HIGH) — reverting.\n"
                    f"  LLM proposed: '{_generated_title}'\n"
                    f"  Kept:         '{_existing_title}'"
                )
                result_dict["h1_title"] = _existing_title
        result_dict["_generation_metrics"] = {
            "generation_time_seconds": 0,  # placeholder - use actual start time
            "context_chunks": len(combined_context),
            "prompt_hash": merge_result.prompt_hash,
            "sources": merge_result.sources
        }

        # Auto-generate JSON-LD schema from the generated content
        try:
            from app.services.aeo.schema_generator import generate_schema_from_product_page
            
            description_html = result_dict.get('description_html', product_info.get('description', ''))
            image_url = ''
            images = self.shopify_service.get_product_images(product_id)
            if images:
                image_url = images[0].get('src', '')
            
            schema_product_data = {
                'title': result_dict.get('h1_title', product_info['title']),
                'sku': product_info.get('sku', ''),
                'price': product_info.get('price', '0.00'),
                'vendor': product_info.get('vendor', ''),
                'handle': product_info.get('handle', ''),
                'product_type': product_info.get('product_type', ''),
                'image_url': image_url,
            }
            
            # Get vehicle fitments from Shopify data
            vehicle_fitments = []
            try:
                full_details = self.shopify_service.get_product_full_details(product_id)
                if full_details:
                    vehicle_fitments = full_details.get('vehicle_fitments', [])
            except Exception:
                pass
            
            product_schema = generate_schema_from_product_page(
                product_data=schema_product_data,
                description_html=description_html,
                vehicle_fitments=vehicle_fitments
            )
            result_dict['product_schema'] = product_schema
            print(f"[ContentGen] Generated JSON-LD schema with {len(product_schema.get('@graph', []))} entities")
        except Exception as e:
            print(f"[ContentGen] Warning: Could not generate JSON-LD schema: {e}")
            result_dict['product_schema'] = None

        # ─────────────────────────────────────────────────────────────
        # Phase 2.10g — extend product_schema with everything that used to
        # go into individual metafields. Adds FAQPage to @graph (from the
        # generator's own faq_items output) and the store_aeo extension
        # block (rebuild_tier + transmission codes + OEMs + related_product
        # GIDs + TL;DR). result_dict['product_schema'] is written by the
        # save-content endpoint to custom.product_schema_json — single
        # metafield, no parallel individual metafields per Theo's
        # consolidation directive.
        # ─────────────────────────────────────────────────────────────
        if result_dict.get('product_schema'):
            try:
                from app.services.aeo.schema_generator import extract_oem_references_from_html
                from app.services.rebuild_tier import classify_rebuild_tier, derive_repair_intent

                # FAQPage in @graph (Phase 2.10 keeps FAQs inside the consolidated
                # blob — reverses the Phase 2.9 dedupe since there's no separate
                # product_faqs metafield anymore).
                faq_items_raw = result_dict.get('faq_items') or []
                faq_entities = []
                for item in faq_items_raw:
                    if not isinstance(item, dict):
                        continue
                    q = (item.get('q') or item.get('question') or '').strip()
                    a = (item.get('a') or item.get('answer') or '').strip()
                    if q and a:
                        faq_entities.append({
                            "@type": "Question",
                            "name": q,
                            "acceptedAnswer": {"@type": "Answer", "text": a},
                        })
                if faq_entities:
                    result_dict['product_schema'].setdefault('@graph', []).insert(0, {
                        "@type": "FAQPage",
                        "name": f"Preguntas Frecuentes - {result_dict.get('h1_title') or product_info.get('title', '')}",
                        "mainEntity": faq_entities,
                    })

                # store_aeo extension — read by theme structured-data.liquid for
                # inline additionalProperty / disambiguatingDescription / isRelatedTo
                # emission inside the Product entity.
                oem_refs = extract_oem_references_from_html(description_html) or []
                aeo: dict = {}
                tier = classify_rebuild_tier(product_info.get('vendor'), product_info.get('product_type'))
                if tier:
                    aeo['rebuild_tier'] = tier
                # Phase 3.5b — canonical repair-intent categories derived from tier + product_type.
                repair_intents = derive_repair_intent(tier, product_info.get('product_type'))
                if repair_intents:
                    aeo['repair_intent'] = repair_intents
                if db_transmission_codes:
                    aeo['transmission_codes'] = db_transmission_codes
                if transmission_code:
                    aeo['primary_transmission_code'] = transmission_code
                if oem_refs:
                    aeo['oem_numbers'] = oem_refs
                    aeo['primary_oem'] = oem_refs[0]

                # related_product_gids (Phase 2.2) + fixes_fault_codes (Phase 3.1+3.1g)
                # share one DB session — both need the Product row.
                try:
                    from app.db.session import SessionLocal as _SL_aeo
                    from app.models.product import Product as _DBProduct_aeo
                    from app.services.fault_code_discovery_service import (
                        discover_fault_codes_for_product,
                        build_howto_entities,
                        to_compact_dicts,
                    )
                    from app.services.product_paa_gsc_service import (
                        enrich_with_paa_questions,
                        get_top_search_queries,
                        paa_to_faq_entities,
                        top_queries_to_compact_dicts,
                    )
                    _db_aeo = _SL_aeo()
                    try:
                        _p = _db_aeo.query(_DBProduct_aeo).filter(_DBProduct_aeo.id == product_id).first()
                        if _p and _p.top_companions:
                            gids = []
                            for c in _p.top_companions[:5]:
                                if isinstance(c, dict):
                                    sid = str(c.get('shopify_id') or '').strip()
                                    if sid.isdigit():
                                        gids.append(f"gid://shopify/Product/{sid}")
                            if gids:
                                aeo['related_product_gids'] = gids

                        # Phase 3.1+3.1g: KG match first, Grok fallback when KG empty.
                        # Service returns [] (not fabricated codes) when nothing fits.
                        if _p:
                            fault_codes = await discover_fault_codes_for_product(_p, _db_aeo)
                            if fault_codes:
                                aeo['fixes_fault_codes'] = to_compact_dicts(fault_codes)
                                product_title = result_dict.get('h1_title') or product_info.get('title', '')
                                howto_entities = build_howto_entities(fault_codes, product_title)
                                if howto_entities:
                                    result_dict['product_schema'].setdefault('@graph', []).extend(howto_entities)

                        # Phase 3.2: merge real PAA questions into the existing
                        # FAQPage (dedup against Grok FAQs), and surface top GSC
                        # queries for read-only display via store_aeo.
                        if _p:
                            graph = result_dict['product_schema'].setdefault('@graph', [])
                            faq_page = next((e for e in graph if e.get('@type') == 'FAQPage'), None)
                            existing_q_texts = [
                                (m.get('name') or '')
                                for m in (faq_page.get('mainEntity', []) if faq_page else [])
                            ]
                            paa = await enrich_with_paa_questions(
                                _p, _db_aeo,
                                existing_questions=existing_q_texts,
                                max_questions=5,
                            )
                            if paa:
                                paa_entities = paa_to_faq_entities(paa)
                                if faq_page:
                                    faq_page.setdefault('mainEntity', []).extend(paa_entities)
                                else:
                                    graph.insert(0, {
                                        "@type": "FAQPage",
                                        "name": f"Preguntas Frecuentes - {result_dict.get('h1_title') or product_info.get('title', '')}",
                                        "mainEntity": paa_entities,
                                    })
                                aeo['paa_questions_added'] = len(paa_entities)

                            top_q = await get_top_search_queries(_p, max_queries=8)
                            if top_q:
                                aeo['top_search_queries'] = top_queries_to_compact_dicts(top_q)

                        # Phase 3.5c: Grok-generated professional notes
                        # (common_failures / companion_parts / installation_tips).
                        # content_generator is the "regenerate everything" flow,
                        # so always fire Grok here — /generate-schema does
                        # smart-merge from existing blob to save Grok cost.
                        if _p:
                            try:
                                from app.services.product_professional_notes_service import (
                                    generate_professional_notes,
                                )
                                fc_codes = (
                                    [fc.code for fc in fault_codes]
                                    if fault_codes else None
                                )
                                pro_notes = await generate_professional_notes(
                                    _p, _db_aeo, fault_code_codes=fc_codes,
                                )
                                if pro_notes:
                                    aeo['professional_notes'] = pro_notes
                            except Exception as pn_err:
                                logger.warning(f"professional_notes skipped: {pn_err}")
                    finally:
                        _db_aeo.close()
                except Exception as _rel_err:
                    logger.warning(f"AEO enrichment (related/fault/paa/gsc/notes) skipped: {_rel_err}")

                # TL;DR: reuse short_description (aspirational marketing voice
                # per feedback_aspirational_copy.md).
                short_desc = (result_dict.get('short_description') or '').strip()
                if len(short_desc) >= 40:
                    aeo['tldr_summary'] = short_desc

                # Phase 3.3: prepend Organization (Example Store seller authority) to @graph.
                # Idempotent — skip if already present from a prior generation.
                try:
                    from app.services.eeat_generator import get_eeat_generator
                    org_entity = get_eeat_generator().build_organization_entity()
                    graph = result_dict['product_schema'].setdefault('@graph', [])
                    if not any(
                        isinstance(e, dict) and e.get('@id') == org_entity['@id']
                        for e in graph
                    ):
                        graph.insert(0, org_entity)
                except Exception as org_err:
                    print(f"[ContentGen] Organization entity skipped: {org_err}")

                if aeo:
                    result_dict['product_schema']['store_aeo'] = aeo
                    print(f"[ContentGen] Added store_aeo to product_schema: {sorted(aeo.keys())}")
            except Exception as e:
                print(f"[ContentGen] Warning: Could not extend product_schema with store_aeo: {e}")

        return result_dict

    # ────────────────────────────────────────────────────────────────────
    # TRANSMISSION CODE ALIASES — query coverage multiplier
    # ────────────────────────────────────────────────────────────────────
    # The same transmission gets sold under several names by different OEMs.
    # Toyota calls a part 03-72LE; Suzuki/Chevrolet call the exact same unit
    # A44DE. Mechanics search whichever name their service manual uses, so a
    # product that only mentions one code loses ~half its potential queries.
    # Each entry is a set of equivalent codes — any code in the product title
    # surfaces ALL the aliases into the generation prompt.
    TRANSMISSION_ALIASES: List[frozenset] = [
        frozenset({'A44DE', '03-72LE', '0372LE'}),              # Toyota / Suzuki / Chevy 4sp
        frozenset({'AX4N', '4F50N'}),                           # Ford transverse 4sp
        frozenset({'AXODE', 'AX4S', 'AOD-E'}),                  # Ford AOD-E family
        frozenset({'AOD', '4R70W', '4R75W'}),                   # Ford RWD 4sp family
        frozenset({'A604', '40TE', '41TE', '41AE'}),            # Chrysler Ultradrive
        frozenset({'A606', '42LE', '42RLE'}),                   # Chrysler 4sp RWD
        frozenset({'A618', '47RE', '47RH', '48RE'}),            # Chrysler diesel
        frozenset({'A500', '42RH', '42RE', '44RE'}),            # Chrysler rear-drive
        frozenset({'A545', '45RFE', '5-45RFE', '545RFE'}),      # Chrysler 5sp
        frozenset({'TH700', 'TH700-R4', '4L60', '4L60E'}),      # GM TH700 family
        frozenset({'4L65E', '4L70E'}),                          # GM heavy-duty variants
        frozenset({'4L80E', '4L85E'}),                          # GM 4L80 family
        frozenset({'6L80', '6L80E'}),                           # GM 6sp
        frozenset({'6L90', '6L90E'}),                           # GM heavy 6sp
        frozenset({'JF015E', 'RE0F11A'}),                       # Nissan CVT (small)
        frozenset({'JF016E', 'JF017E', 'RE0F10D'}),             # Nissan CVT (medium)
        frozenset({'JF011E', 'RE0F10A'}),                       # Nissan CVT (base)
        frozenset({'JF506E', '09A', 'VW09A'}),                  # VW/Audi 5sp (Jatco)
        frozenset({'01M', '096', '099'}),                       # VW 4sp family
        frozenset({'01N', '01P'}),                              # VW 4sp ATF
        frozenset({'01V', '5HP19'}),                            # ZF 5HP19 / VW01V
        frozenset({'5HP24', '5HP24A'}),                         # ZF 5sp
        frozenset({'ZF8HP', 'ZF8HP45', 'ZF8HP50', 'ZF8HP55', 'ZF8HP70', '845RE', '850RE', 'AL450'}),
        frozenset({'ZF9HP', 'ZF9HP48', '948TE'}),               # ZF/Chrysler 9sp
        frozenset({'6R80', 'ZF6HP28', '6HP28'}),                # Ford/ZF 6sp
        frozenset({'4F27E', 'FN4AEL'}),                         # Mazda/Ford 4sp
        frozenset({'5R55S', '5R55W', '5R55E', '5R55N'}),        # Ford 5sp family
        frozenset({'6F35', '6F15'}),                            # Ford/GM 6sp transverse
        frozenset({'DPS6', '6DCT250', '6DCT450'}),              # Ford Powershift DCT
        frozenset({'DQ200', '0AM', '7DCT'}),                    # VW DSG 7sp dry
        frozenset({'DQ250', '02E', '6DCT'}),                    # VW DSG 6sp wet
        frozenset({'10R80', 'ZF10HP'}),                         # Ford/ZF 10sp
        frozenset({'8L90', '8L45'}),                            # GM 8sp
        frozenset({'68RFE', '68RE'}),                           # Chrysler diesel 6sp
        frozenset({'U250E', 'AW80-40LE', 'AW80-40LS', 'U241E'}),# Aisin 4sp
        frozenset({'U760E', 'U760F', 'AW80-41LE'}),             # Aisin 6sp
    ]

    def _gather_keyword_intelligence(
        self, db_product, product_info: dict,
        transmission_code: Optional[str], part_type: Optional[str], brand: Optional[str],
    ) -> dict:
        """Gather real search queries from GSC for this product + siblings.

        Hierarchy: product_type → transmission → brand → OEM.
        For products with no GSC data, borrows queries from siblings that
        share the same transmission_code and product_type.
        """
        from app.db.session import SessionLocal
        from app.models.product import Product

        result: dict = {
            "own_queries": [],
            "sibling_queries": [],
            "top_performing_siblings": [],
            "oem_codes": [],
        }
        try:
            from app.services.google_api_service import GoogleApiService
            gsc = GoogleApiService()
        except Exception:
            return result

        handle = product_info.get("handle", "")
        if handle:
            try:
                own = gsc.get_product_gsc_queries(handle, days=90, limit=20)
                result["own_queries"] = own
            except Exception:
                pass

        if not result["own_queries"] and transmission_code:
            with SessionLocal() as db:
                siblings = (
                    db.query(Product.handle, Product.title, Product.gsc_impressions,
                             Product.gsc_clicks, Product.gsc_ctr, Product.product_type,
                             Product.vendor, Product.seo_score)
                    .filter(
                        Product.transmission_code == transmission_code,
                        Product.gsc_impressions > 5,
                    )
                    .order_by(Product.gsc_impressions.desc())
                    .limit(5)
                    .all()
                )
                if part_type:
                    typed = [s for s in siblings if s.product_type and part_type.lower() in s.product_type.lower()]
                    if typed:
                        siblings = typed

                result["top_performing_siblings"] = [
                    {"title": s.title, "impressions": s.gsc_impressions,
                     "clicks": s.gsc_clicks, "seo_score": s.seo_score}
                    for s in siblings[:3]
                ]
                for sib in siblings[:3]:
                    try:
                        sq = gsc.get_product_gsc_queries(sib.handle, days=90, limit=10)
                        for q in sq:
                            q["source_product"] = sib.title
                        result["sibling_queries"].extend(sq)
                    except Exception:
                        continue

            seen = set()
            deduped = []
            for q in sorted(result["sibling_queries"], key=lambda x: x.get("impressions", 0), reverse=True):
                if q["query"] not in seen:
                    seen.add(q["query"])
                    deduped.append(q)
            result["sibling_queries"] = deduped[:15]

        desc = product_info.get("description", "")
        title = product_info.get("title", "")
        oem_codes = self._extract_oem_from_text(f"{title} {desc}")
        result["oem_codes"] = oem_codes

        return result

    @staticmethod
    async def _analyze_product_images(
        image_urls: list[str], product_title: str, max_images: int = 5,
    ) -> list[dict]:
        """Send product images to Grok 4.3 vision for real descriptions."""
        if not image_urls:
            return []
        import httpx
        from app.core.config import settings

        if not settings.XAI_API_KEY:
            return []

        results: list[dict] = []
        urls_to_analyze = image_urls[:max_images]

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                for idx, url in enumerate(urls_to_analyze):
                    payload = {
                        "model": settings.XAI_MODEL,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": (
                                            f"Esta imagen es del producto: \"{product_title}\". "
                                            "Es una refacción para transmisiones automáticas. "
                                            "Describe en español qué se ve en la imagen en 1-2 oraciones. "
                                            "Sé específico: forma, color, material, número de dientes/estrías, "
                                            "marcas visibles, ángulo de la foto (vista frontal, lateral, detalle). "
                                            "NO repitas el título del producto. Responde SOLO la descripción."
                                        ),
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": url},
                                    },
                                ],
                            }
                        ],
                        "temperature": 0.3,
                        "max_tokens": 150,
                    }
                    resp = await client.post(
                        "https://api.x.ai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {settings.XAI_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    if resp.status_code == 200:
                        desc = resp.json()["choices"][0]["message"]["content"].strip()
                        results.append({"url": url, "description": desc, "index": idx})
                    else:
                        logger.warning(f"[ImageAnalysis] Image {idx} failed: {resp.status_code}")
        except Exception as e:
            logger.warning(f"[ImageAnalysis] Vision analysis failed: {e}")

        if results:
            print(f"[ContentGen] Analyzed {len(results)}/{len(urls_to_analyze)} images with vision")
        return results

    @staticmethod
    def _rank_transmission_codes(
        all_codes: list[str], primary_code: Optional[str],
    ) -> dict:
        """Rank transmission codes by GSC search demand.

        Returns a dict with 'title_codes' (top 3-5 for H1) and
        'body_codes' (remaining, for description/table only).
        """
        from app.db.session import SessionLocal
        from app.models.product import Product
        from sqlalchemy import func as sa_func

        if not all_codes:
            if primary_code:
                return {"title_codes": [primary_code], "body_codes": []}
            return {"title_codes": [], "body_codes": []}

        code_scores: dict[str, int] = {}
        try:
            with SessionLocal() as db:
                rows = (
                    db.query(
                        Product.transmission_code,
                        sa_func.sum(Product.gsc_impressions).label("imp"),
                    )
                    .filter(Product.transmission_code.in_(all_codes))
                    .group_by(Product.transmission_code)
                    .all()
                )
                for r in rows:
                    code_scores[r.transmission_code] = r.imp or 0
        except Exception:
            pass

        if primary_code and primary_code not in code_scores:
            code_scores[primary_code] = 0

        ranked = sorted(all_codes, key=lambda c: code_scores.get(c, 0), reverse=True)

        if primary_code and primary_code in ranked:
            ranked.remove(primary_code)
            ranked.insert(0, primary_code)

        # Keep important variants together with their parent in the title.
        # Mechanics search "TH700-R4" separately from "TH700".
        title_codes = ranked[:5]
        body_codes = ranked[5:]
        _promoted: list[str] = []
        for tc in list(body_codes):
            for ttc in title_codes:
                if (tc.startswith(ttc) or ttc.startswith(tc)) and tc != ttc:
                    _promoted.append(tc)
                    body_codes.remove(tc)
                    break
        title_codes.extend(_promoted)

        return {
            "title_codes": title_codes,
            "body_codes": body_codes,
            "scores": {c: code_scores.get(c, 0) for c in all_codes},
        }

    @staticmethod
    def _extract_oem_from_text(text: str) -> list[str]:
        """Pull OEM-style part numbers from title + description."""
        import re
        patterns = [
            r'\b(\d{5,8}[A-Z]?)\b',
            r'\b([A-Z]{1,3}\d{4,7}[A-Z]?)\b',
        ]
        codes: list[str] = []
        seen: set[str] = set()
        for pat in patterns:
            for m in re.finditer(pat, text):
                code = m.group(1)
                if code not in seen and not code.isdigit():
                    seen.add(code)
                    codes.append(code)
                elif code not in seen and len(code) >= 6:
                    seen.add(code)
                    codes.append(code)
        return codes[:10]

    def _extract_transmission_code(self, title: str) -> Optional[str]:
        """Extract transmission code from product title"""
        import re
        patterns = [
            r'(ZF\d+HP\d+)',
            r'(\d{1,2}[LR]\d{2}[EW]?)',
            r'([A-Z]{2}\d{3}[A-Z]*)',
            r'(\d{3}RE)',
        ]
        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        return None

    def _parse_existing_vehicle_table(self, description_html: str, kg) -> List[Dict]:
        """Parse the existing <h4>Vehiculos</h4> table from the current description.

        Returns one dict per row: {make, model, years, trans_code, motor}. The
        trans_code field is populated only when the Transmisión cell contains a
        recognised transmission code (e.g. "6L80", "ZF8HP55") — NOT when it only
        carries speed/drivetrain text like "6 SP 4WD" that earlier generations
        sometimes wrote there.

        Used as the highest-priority source for per-row transmission codes
        during regeneration: curator-verified data in the existing table is
        preserved, so the LLM is never asked to guess a code we already know.
        """
        import re
        if not description_html:
            return []
        h4_match = re.search(
            r'<h4[^>]*>\s*Veh[ií]culos[^<]*</h4>\s*(?:<div[^>]*>\s*)?(<table.*?</table>)',
            description_html,
            re.IGNORECASE | re.DOTALL,
        )
        if not h4_match:
            return []
        table_html = h4_match.group(1)
        # Prefer <tbody> if present so we skip the header row cleanly
        tbody_match = re.search(r'<tbody[^>]*>(.*?)</tbody>', table_html, re.IGNORECASE | re.DOTALL)
        rows_html = tbody_match.group(1) if tbody_match else table_html
        row_iter = re.findall(r'<tr[^>]*>(.*?)</tr>', rows_html, re.IGNORECASE | re.DOTALL)
        parsed: List[Dict] = []
        for row_html in row_iter:
            cells = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row_html, re.IGNORECASE | re.DOTALL)
            if len(cells) < 4:
                continue
            cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            # Skip header row if <thead> wasn't separated
            if cells[0].lower() in ('marca', 'make', 'brand'):
                continue
            marca = cells[0]
            modelo = cells[1] if len(cells) > 1 else ''
            years = cells[2] if len(cells) > 2 else ''
            trans_cell = cells[3] if len(cells) > 3 else ''
            motor = cells[4] if len(cells) > 4 else ''
            trans_code = ''
            try:
                codes = kg.extract_all_transmission_codes(trans_cell)
                if codes:
                    trans_code = codes[0]
            except Exception:
                pass
            parsed.append({
                'make': marca.upper().strip(),
                'model': modelo.upper().strip(),
                'years': years,
                'trans_code': trans_code,
                'motor': motor,
            })
        return parsed

    def _extract_compatibility_codes(self, description_html: str, kg) -> List[str]:
        """Parse transmission codes from the 'Compatibilidad:' line specifically.

        Narrower than Product.transmission_codes (which unions every code mentioned
        anywhere in title+description and over-includes for kit products). The
        Compatibilidad line is the curator's explicit fit declaration — for
        kit/juego products it excludes codes that only apply to sub-components
        (e.g. a universal 18-orifice filter mentioning 6L50/6L90 inside a kit
        that as a whole only fits 6L80).

        Returns codes found by the knowledge graph's pattern matcher applied to
        the Compatibilidad line only. Empty list if no line or no recognised codes.
        """
        import re
        if not description_html:
            return []
        # Preferred: structured list item <li><strong>Compatibilidad:</strong> ... </li>
        li_match = re.search(
            r'<li[^>]*>\s*<strong>\s*Compatibilidad\s*:?\s*</strong>\s*([^<]+)',
            description_html,
            re.IGNORECASE,
        )
        if li_match:
            line = li_match.group(1).strip()
        else:
            # Fallback: plain text after HTML strip
            text = re.sub(r'<[^>]+>', ' ', description_html)
            text_match = re.search(
                r'Compatibilidad\s*:\s*(.{1,300}?)(?=\s+(?:Lo\s+que\s+incluye|Env[ií]os|Tipo\s*:|SKU\s*:|N[uú]mero|Ubicaci[oó]n)|\Z)',
                text,
                re.IGNORECASE | re.DOTALL,
            )
            if not text_match:
                return []
            line = text_match.group(1).strip()
        try:
            return kg.extract_all_transmission_codes(line)
        except Exception:
            return []

    def _get_transmission_alternates(self, title: str) -> List[str]:
        """Find every known alias for any transmission code mentioned in the title.

        Mechanics cross-reference between OEM-specific names (Toyota 03-72LE) and
        the generic unit name (A44DE). Returning the full alias set lets the
        prompt expand query coverage without the LLM inventing wrong equivalents.
        """
        title_upper = (title or '').upper()
        found: set = set()
        for alias_set in self.TRANSMISSION_ALIASES:
            if any(code in title_upper for code in alias_set):
                found.update(alias_set)
        return sorted(found)

    def _extract_part_type(self, title: str) -> Optional[str]:
        """Extract part type from product title"""
        title_lower = title.lower()
        part_types = {
            'filtro': 'FILTRO',
            'cuerpo de valvulas': 'CUERPO_VALVULAS',
            'cuerpo valvulas': 'CUERPO_VALVULAS',
            'solenoide': 'SOLENOIDE',
            'sensor': 'SENSOR',
            'kit': 'KIT',
            'banda': 'BANDA',
            'bomba': 'BOMBA',
            'convertidor': 'CONVERTIDOR',
        }
        for key, value in part_types.items():
            if key in title_lower:
                return value
        return None

    def _extract_brand(self, title: str) -> Optional[str]:
        """Extract brand/vendor from product title"""
        title_lower = title.lower()
        brands = ['tss', 'dacco', 'sonna', 'allison', 'zf']
        for brand in brands:
            if brand in title_lower:
                return brand.upper()
        return None

    async def _get_embedding_ollama(self, text: str) -> List[float]:
        """Get embedding from local Ollama instance"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/embed",
                json={"model": settings.OLLAMA_EMBED_MODEL, "input": text}
            )
            response.raise_for_status()
            return response.json()["embeddings"][0]

    def _get_performance_data(self) -> Dict:
        """Get search performance data for optimization — no longer used as primary source.
        Live data is now fetched per-product in the analytics endpoint and passed via analysis_insights."""
        return {}

    def _format_analysis_insights(self, insights: Optional[Dict], product_info: Optional[Dict] = None) -> str:
        """
        Format Grok analysis insights into context for content generation.

        This injects the analysis recommendations directly into the prompt,
        making the generated content analysis-aware.
        """
        if not insights:
            return ""

        sections = []
        sections.append("## 🧠 GROK ANALYSIS INSIGHTS (Use these to enhance the content)")
        sections.append("Based on deep analysis of this product, follow these guidelines:")
        sections.append("")

        # Extract actual GSC/GA4 metrics from the analysis to inform the generator
        perf_vs_benchmark = insights.get("performance_vs_benchmark") or {}
        metrics = perf_vs_benchmark.get("metrics") or {}
        gsc_impressions = (metrics.get("impressions") or {}).get("product", 0)
        gsc_position = (metrics.get("position") or {}).get("product", 0)
        gsc_sessions = (metrics.get("sessions") or {}).get("product", 0)
        sold_30d = (metrics.get("sold_30d") or {}).get("product", 0)
        sold_90d = (metrics.get("sold_90d") or {}).get("product", 0)
        # performance_tier from backend-computed field (most reliable source)
        performance_tier = (
            insights.get("performance_tier")
            or (insights.get("primary_issue") or {}).get("performance_tier")
            or (insights.get("primary_issue_confirmed") or {}).get("performance_tier")
            or "DEVELOPING"
        )

        # ═════════════════════════════════════════════════════════════════════
        # HARD CONSTRAINT for HIGH tier — stops the LLM from even proposing a
        # title/meta/url change. The post-gen SEO Asset Lock reverts these as a
        # last line of defense, but the cheapest fix is to never let the model
        # waste cycles on rewriting a ranked asset in the first place.
        # ═════════════════════════════════════════════════════════════════════
        if performance_tier == "HIGH":
            _current_title = (product_info or {}).get("title", "") or ""
            _current_meta = (product_info or {}).get("meta_title", "") or ""
            _current_handle = (product_info or {}).get("handle", "") or ""
            sections.append("## 🚨 HARD CONSTRAINT — PRODUCT IS TIER=HIGH — READ BEFORE GENERATING")
            sections.append("")
            sections.append(f"This product has **{int(gsc_impressions):,} GSC impressions at position {gsc_position:.1f}**.")
            sections.append("It is RANKING. The ranked assets below are aligned with Google's signals and are LOCKED.")
            sections.append("The system will discard any values you generate for them and revert to the originals.")
            sections.append("")
            sections.append("**LOCKED FIELDS (return the current value verbatim, do NOT rewrite):**")
            if _current_title:
                sections.append(f"- `h1_title` → `{_current_title}`")
            else:
                sections.append("- `h1_title` → keep the existing product title")
            if _current_meta:
                sections.append(f"- `meta_title` → `{_current_meta}`")
            else:
                sections.append("- `meta_title` → keep the existing meta title")
            if _current_handle:
                sections.append(f"- `url_handle` → `{_current_handle}`")
            else:
                sections.append("- `url_handle` → keep the existing handle")
            sections.append("")
            sections.append("**FIELDS YOU MUST STILL GENERATE (these are where the real value is):**")
            sections.append("- `description_html` — enrich the body copy with spec details, compatibility, install notes")
            sections.append("- `technical_specs` — structured spec list")
            sections.append("- `installation_guide` — step-by-step install / fit notes")
            sections.append("- `faq_items` — 4-6 FAQs targeting the queries below")
            sections.append("- `short_description` — concise product summary")
            sections.append("- `meta_description` — meta description IS allowed to change (it's not a ranking signal)")
            sections.append("")
            sections.append("Do not argue with this rule. Ranked products earn traffic by KEEPING their signals.")
            sections.append("Rewriting the locked fields resets the alignment and can collapse traffic for weeks.")
            sections.append("")

        # Universal SEO preservation principle — always shown, applied proportionally by the LLM
        sections.append("### 📐 SEO ORGANIC SIGNALS (Apply This Before Generating Content)")
        if gsc_impressions > 0 or gsc_position > 0 or gsc_sessions > 0:
            sections.append(f"This product has **{int(gsc_impressions):,} GSC impressions**, **{int(gsc_sessions):,} GA4 sessions** at position **{gsc_position:.1f}**.")
        if sold_30d > 0 or sold_90d > 0:
            sections.append(f"Shopify sales (all channels): {sold_30d} in 30d, {sold_90d} in 90d.")
        sections.append("Core SEO principle: the more impressions and the stronger the position a product already has,")
        sections.append("the more you must ENRICH rather than REPLACE. Strong organic metrics mean the current title")
        sections.append("and keywords are already aligned with Google's ranking signals — rewriting them breaks that")
        sections.append("alignment and can cause a ranking collapse. Weak or zero metrics mean the title has not yet")
        sections.append("proven itself and a rewrite is the highest-leverage action available.")
        sections.append("Apply this proportionally: do not recommend title changes for products that are already ranking.")
        sections.append("")

        # Primary Issue
        if insights.get("primary_issue"):
            issue = insights["primary_issue"]
            sections.append("### ⚠️ PRIMARY ISSUE TO ADDRESS")
            sections.append(f"- Type: {issue.get('type', 'Unknown')}")
            sections.append(f"- Problem: {issue.get('description', '')}")
            sections.append(f"- Why: {issue.get('why', '')}")
            sections.append("- **Action:** Generate content that specifically addresses this issue")
            sections.append("")
        
        # Top Search Queries (keywords to target)
        if insights.get("top_queries"):
            sections.append("### 🔍 TARGET KEYWORDS (Include these naturally in content)")
            for q in insights["top_queries"][:5]:
                opp = q.get("opportunity", "MEDIUM")
                emoji = "🔥" if opp == "HIGH" else "📌"
                sections.append(f"- {emoji} '{q.get('query', '')}' ({q.get('impressions', 0):,} impressions, {opp} opportunity)")
            sections.append("")
        
        # Recommendations
        if insights.get("recommendations"):
            sections.append("### 📋 SPECIFIC RECOMMENDATIONS (Implement these)")
            for i, rec in enumerate(insights["recommendations"][:5], 1):
                priority = rec.get("priority", "medium").upper()
                emoji = "🔴" if priority == "HIGH" else "🟡" if priority == "MEDIUM" else "🟢"
                sections.append(f"{i}. {emoji} [{priority}] {rec.get('action', '')}")
                if rec.get("expected_impact"):
                    sections.append(f"   Expected impact: {rec.get('expected_impact')}")
            sections.append("")
        
        # Keyword opportunities
        if insights.get("keyword_opportunities"):
            sections.append("### 📈 SEO KEYWORD OPPORTUNITIES")
            for kw in insights["keyword_opportunities"][:5]:
                sections.append(f"- {kw}")
            sections.append("")
        
        # Question targets (for FAQ section)
        if insights.get("question_targets"):
            sections.append("### ❓ FAQ QUESTIONS (Include these in the FAQ section)")
            for q in insights["question_targets"][:5]:
                sections.append(f"- {q}")
            sections.append("")
        
        # Pre-generated content (meta tags, etc.)
        if insights.get("generated_content"):
            gc = insights["generated_content"]
            sections.append("### ✨ SUGGESTED CONTENT (Use or adapt these)")
            if gc.get("suggested_meta_title"):
                sections.append(f"- **Meta Title:** {gc['suggested_meta_title']}")
            if gc.get("suggested_meta_description"):
                sections.append(f"- **Meta Description:** {gc['suggested_meta_description']}")
            if gc.get("faq_questions"):
                sections.append("- **FAQ Questions to Include:**")
                for faq in gc["faq_questions"][:3]:
                    sections.append(f"  - {faq}")
            sections.append("")
        
        # Competitor snippets — what's currently ranking in the SERP for this
        # product's main queries. Goal: give the LLM explicit targets to DIFFERENTIATE
        # against instead of producing generic category-average copy.
        comp_snippets = insights.get('competitor_snippets') or []
        if comp_snippets:
            sections.append("### 🥇 COMPETIDORES EN SERP (páginas que hay que superar)")
            sections.append("Estas son las páginas que actualmente rankean para las queries principales de este producto.")
            sections.append("No copies su estructura — genera una descripción que OFREZCA ALGO QUE ELLOS NO TIENEN:")
            sections.append("más detalle técnico, FAQs más profundas, aplicaciones vehiculares más específicas, códigos OEM verificados.")
            for c in comp_snippets[:5]:
                kw = c.get('keyword', '')
                rank = c.get('rank', '?')
                title = c.get('title', '')
                snippet = c.get('snippet', '')
                domain = c.get('domain', '')
                sections.append(f"- **[{kw}] #{rank} {domain}**: \"{title[:80]}\" — {snippet[:150]}")
            sections.append("")

        # AI Visibility context
        if insights.get("visibility_score"):
            scores = insights["visibility_score"]
            sections.append("### 🤖 AI VISIBILITY (How visible this product is in AI responses)")
            for llm, score in scores.items():
                level = "High" if score >= 70 else "Medium" if score >= 40 else "Low"
                sections.append(f"- {llm.capitalize()}: {score}/100 ({level})")
            sections.append("- **Action:** If visibility is low, focus on unique differentiators and specific details")
            sections.append("")
        
        sections.append("### 📝 GENERATION INSTRUCTIONS")
        sections.append("Using the insights above, generate content that:")
        sections.append("1. Addresses the primary issue identified")
        sections.append("2. Naturally incorporates the target keywords")
        sections.append("3. Implements the specific recommendations")
        sections.append("4. Includes an FAQ section with the suggested questions")
        sections.append("5. Uses or adapts the suggested meta tags")
        sections.append("6. Respects the organic signals above — if this product already ranks, ENRICH the page,")
        sections.append("   do not rewrite the title or remove keywords that are responsible for the current position")

        return "\n".join(sections)


# Export for backward compatibility
content_generator_service = ContentGeneratorService()
