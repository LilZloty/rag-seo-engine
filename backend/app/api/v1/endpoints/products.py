from fastapi import APIRouter, Depends, HTTPException, Body, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import uuid

from app.db.session import get_db
from app.models.product import Product
from app.models.library import GenerationHistory
from app.services.shopify_service import shopify_service
from app.services.product_service import ProductService
from app.services.redis_service import cache
from app.core.config import settings
from app.core.rate_limiter import limiter, RATE_SYNC

router = APIRouter()


@router.get("/products")
async def get_products(
    needs_seo_only: bool = False,
    opportunity_level: Optional[str] = None,
    min_performance_score: Optional[int] = None,
    min_sessions: Optional[int] = None,
    segment: Optional[str] = None,  # Smart segment filter
    sales_period: Optional[str] = "90d",  # Sales time period: 30d, 90d, 365d, all_time
    search: Optional[str] = None,  # Search by title, SKU, or handle
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    # 5-min Redis cache keyed by query params. Eliminates the repeated Postgres
    # round-trip on dashboard navigation / segment switching. Acceptable
    # staleness window — sync endpoints can call cache.invalidate_pattern
    # later if instant refresh becomes a requirement.
    cache_key = (
        f"api:products:list:{needs_seo_only}:{opportunity_level}:"
        f"{min_performance_score}:{min_sessions}:{segment}:{sales_period}:"
        f"{search or ''}:{skip}:{limit}"
    )
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    from sqlalchemy import and_
    from datetime import datetime, timedelta

    query = db.query(Product)

    # Apply search filter (title, SKU, or handle)
    if search:
        from sqlalchemy import or_
        search_term = f"%{search}%"
        query = query.filter(or_(
            Product.title.ilike(search_term),
            Product.sku.ilike(search_term),
            Product.handle.ilike(search_term)
        ))

    if needs_seo_only:
        query = query.filter(Product.needs_seo == True)

    if opportunity_level:
        query = query.filter(Product.opportunity_level == opportunity_level)

    if min_performance_score is not None:
        query = query.filter(Product.performance_score >= min_performance_score)

    if min_sessions is not None:
        query = query.filter(Product.ga4_sessions >= min_sessions)

    # Apply segment filter
    if segment and segment != 'all':
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        if segment == 'quick-wins':
            query = query.filter(and_(
                Product.gsc_impressions > 100,
                Product.ga4_sessions > 10
            ))
        elif segment == 'revenue-at-risk':
            query = query.filter(and_(
                Product.ga4_sessions > 50,
                Product.total_sold < 5
            ))
        elif segment == 'new-products':
            query = query.filter(Product.created_at > thirty_days_ago)
        elif segment == 'zombie-products':
            query = query.filter(
                (Product.total_sold == 0) | (Product.total_sold == None)
            )
        elif segment == 'top-performers':
            query = query.filter(Product.total_revenue > 500)
        elif segment == 'high-opportunity':
            query = query.filter(Product.opportunity_level == 'high')
        elif segment == 'needs-seo':
            query = query.filter(Product.needs_seo == True)

    total = query.count()
    products = query.offset(skip).limit(limit).all()

    # Determine which sales fields to use based on sales_period
    sales_fields = {
        '30d': {'sold': 'sold_30d', 'revenue': 'revenue_30d'},
        '90d': {'sold': 'sold_90d', 'revenue': 'revenue_90d'},
        '365d': {'sold': 'sold_365d', 'revenue': 'revenue_365d'},
        'all_time': {'sold': 'sold_all_time', 'revenue': 'revenue_all_time'}
    }.get(sales_period, {'sold': 'sold_90d', 'revenue': 'revenue_90d'})

    result = {
        "total": total,
        "skip": skip,
        "limit": limit,
        "sales_period": sales_period,
        "products": [
            {
                "id": p.id,
                "shopify_id": p.shopify_id,
                "title": p.title,
                "sku": p.sku,
                "handle": p.handle,
                "needs_seo": p.needs_seo,
                "seo_score": p.seo_score or 0,
                "seo_status": p.seo_status,
                "description_length": p.description_length,
                "image_count": p.image_count,
                # Sales data based on selected period
                "total_sold": getattr(p, sales_fields['sold'], 0) or 0,
                "total_revenue": getattr(p, sales_fields['revenue'], 0.0) or 0.0,
                # Raw sales data for all periods (for flexibility)
                "sold_30d": p.sold_30d or 0,
                "revenue_30d": p.revenue_30d or 0.0,
                "sold_90d": p.sold_90d or 0,
                "revenue_90d": p.revenue_90d or 0.0,
                "sold_365d": p.sold_365d or 0,
                "revenue_365d": p.revenue_365d or 0.0,
                "sold_all_time": p.sold_all_time or 0,
                "revenue_all_time": p.revenue_all_time or 0.0,
                "created_at": p.shopify_created_at.isoformat() if p.shopify_created_at else p.created_at.isoformat() if p.created_at else None,
                "updated_at": p.shopify_updated_at.isoformat() if p.shopify_updated_at else p.updated_at.isoformat() if p.updated_at else None,
                "shopify_created_at": p.shopify_created_at.isoformat() if p.shopify_created_at else None,
                "shopify_updated_at": p.shopify_updated_at.isoformat() if p.shopify_updated_at else None,
                # GA4 Analytics Fields
                "ga4_sessions": p.ga4_sessions or 0,
                "ga4_engagement_time": p.ga4_engagement_time or 0.0,
                "ga4_bounce_rate": p.ga4_bounce_rate or 0.0,
                "ga4_revenue": p.ga4_revenue or 0.0,
                # Search Console Fields
                "gsc_impressions": p.gsc_impressions or 0,
                "gsc_clicks": p.gsc_clicks or 0,
                "gsc_ctr": p.gsc_ctr or 0.0,
                "gsc_position": p.gsc_position or 0.0,
                # Calculated Fields
                "performance_score": p.performance_score or 0,
                "opportunity_level": p.opportunity_level or 'low',
                "last_analytics_sync": p.last_analytics_sync.isoformat() if p.last_analytics_sync else None,
                # Inventory Fields
                "inventory_quantity": p.inventory_quantity,
                "inventory_status": p.inventory_status,
                "last_inventory_sync": p.last_inventory_sync.isoformat() if p.last_inventory_sync else None
            }
            for p in products
        ]
    }
    cache.set(cache_key, result, ttl=300)
    return result


# IMPORTANT: Static routes must be defined BEFORE dynamic routes like /products/{product_id}
@router.get("/products/segment-counts")
async def get_segment_counts(db: Session = Depends(get_db)):
    """
    Get accurate counts for all smart filter segments.
    This queries the full database, not just paginated results.
    """
    # Check cache (5 min TTL)
    cached = cache.get("products:segment_counts")
    if cached:
        return cached

    from sqlalchemy import and_
    from datetime import datetime, timedelta

    try:
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        # Total products
        total = db.query(Product).count()
        
        # Quick Wins: GSC impressions > 100 AND GA4 sessions > 10
        quick_wins = db.query(Product).filter(
            and_(
                Product.gsc_impressions > 100,
                Product.ga4_sessions > 10
            )
        ).count()
        
        # Revenue at Risk: High traffic but low sales
        revenue_at_risk = db.query(Product).filter(
            and_(
                Product.ga4_sessions > 50,
                Product.total_sold < 5
            )
        ).count()
        
        # New Products: Created in last 30 days
        new_products = db.query(Product).filter(
            Product.created_at > thirty_days_ago
        ).count()
        
        # Zombie Products: No sales
        zombie_products = db.query(Product).filter(
            (Product.total_sold == 0) | (Product.total_sold == None)
        ).count()
        
        # Top Performers: High revenue > $500
        top_performers = db.query(Product).filter(
            Product.total_revenue > 500
        ).count()
        
        # High Opportunity: Backend-calculated
        high_opportunity = db.query(Product).filter(
            Product.opportunity_level == 'high'
        ).count()
        
        # Needs SEO
        needs_seo = db.query(Product).filter(
            Product.needs_seo == True
        ).count()
        
        result = {
            "all": total,
            "quick-wins": quick_wins,
            "revenue-at-risk": revenue_at_risk,
            "new-products": new_products,
            "zombie-products": zombie_products,
            "top-performers": top_performers,
            "high-opportunity": high_opportunity,
            "needs-seo": needs_seo
        }
        cache.set("products:segment_counts", result, ttl=300)
        return result
    except Exception as e:
        import traceback
        print(f"❌ Segment counts error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/test-shopify")
async def test_shopify_connection():
    """Test endpoint - fetches just ONE product to verify Shopify connection works"""
    try:
        import shopify
        from app.core.config import settings
        
        # Initialize session
        session = shopify.Session(
            settings.SHOPIFY_STORE, 
            settings.SHOPIFY_API_VERSION, 
            settings.SHOPIFY_ACCESS_TOKEN
        )
        shopify.ShopifyResource.activate_session(session)
        
        # Fetch just 1 product
        products = shopify.Product.find(limit=1)
        
        if products:
            p = products[0]
            return {
                "success": True,
                "message": "Shopify connection works!",
                "sample_product": {
                    "id": p.id,
                    "title": p.title,
                    "handle": p.handle,
                    "sku": p.variants[0].sku if p.variants else None
                }
            }
        else:
            return {"success": True, "message": "Connected but no products found"}
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


# IMPORTANT: Add new static routes HERE, before dynamic routes like /products/{product_id}

@router.get("/products/opportunity-analysis")
async def get_opportunity_analysis(db: Session = Depends(get_db)):
    """
    Analyze the distribution of products by sessions and SEO score
    to help understand why only a few products show as High Opportunity.
    """
    try:
        products = db.query(Product).all()

        # Use pre-calculated SEO scores from DB
        products_with_scores = []
        for p in products:
            products_with_scores.append({
                'id': p.id,
                'title': p.title,
                'ga4_sessions': p.ga4_sessions or 0,
                'seo_score': p.seo_score or 0,
                'opportunity_level': p.opportunity_level or 'low',
                'needs_seo': p.needs_seo
            })

        # Distribution analysis
        sessions_buckets = {
            '0': 0,
            '1-10': 0,
            '11-50': 0,
            '51-100': 0,
            '101-500': 0,
            '500+': 0
        }

        seo_buckets = {
            '0-25': 0,
            '26-50': 0,
            '51-70': 0,
            '71-100': 0
        }

        high_opportunity_candidates = []

        for p in products_with_scores:
            # Sessions buckets
            sessions = p['ga4_sessions']
            if sessions == 0:
                sessions_buckets['0'] += 1
            elif sessions <= 10:
                sessions_buckets['1-10'] += 1
            elif sessions <= 50:
                sessions_buckets['11-50'] += 1
            elif sessions <= 100:
                sessions_buckets['51-100'] += 1
            elif sessions <= 500:
                sessions_buckets['101-500'] += 1
            else:
                sessions_buckets['500+'] += 1

            # SEO buckets
            seo = p['seo_score']
            if seo <= 25:
                seo_buckets['0-25'] += 1
            elif seo <= 50:
                seo_buckets['26-50'] += 1
            elif seo <= 70:
                seo_buckets['51-70'] += 1
            else:
                seo_buckets['71-100'] += 1

            # High opportunity candidates (>100 sessions, <50 SEO)
            if sessions > 100 and seo < 50:
                high_opportunity_candidates.append(p)

        # Opportunity level distribution
        opportunity_counts = {
            'high': sum(1 for p in products_with_scores if p['opportunity_level'] == 'high'),
            'medium': sum(1 for p in products_with_scores if p['opportunity_level'] == 'medium'),
            'low': sum(1 for p in products_with_scores if p['opportunity_level'] == 'low')
        }

        return {
            "total_products": len(products),
            "products_with_ga4_data": sum(1 for p in products_with_scores if p['ga4_sessions'] > 0),
            "sessions_distribution": sessions_buckets,
            "seo_score_distribution": seo_buckets,
            "opportunity_level_counts": opportunity_counts,
            "high_opportunity_candidates": {
                "count": len(high_opportunity_candidates),
                "products": sorted(high_opportunity_candidates, key=lambda x: x['ga4_sessions'], reverse=True)[:10]
            },
            "analysis": {
                "high_opportunity_threshold": {
                    "sessions_required": "> 100",
                    "seo_score_required": "< 50"
                },
                "why_so_few": "High Opportunity requires BOTH high traffic (>100 sessions) AND poor content (<50 SEO score). Most products either have low traffic OR already have decent SEO.",
                "recommendations": [
                    "Check if GA4 is tracking all product pages correctly",
                    "Verify that product handles in database match URL paths in GA4",
                    "If many products have 0 sessions, run the Analytics Sync again",
                    "Consider lowering the threshold if you want more 'High Opportunity' products (e.g., >50 sessions instead of >100)"
                ]
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{product_id}/shopify")
async def get_product_shopify_details(product_id: str, db: Session = Depends(get_db)):
    """Get full product details directly from Shopify (including current description, images, metafields)"""
    # First get local product to get shopify_id
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found in local database")
    
    # Fetch full details from Shopify
    shopify_data = shopify_service.get_product_full_details(product.shopify_id)
    if not shopify_data:
        raise HTTPException(status_code=404, detail="Product not found in Shopify")
    
    # Use cached vehicle fitments if available (much faster than Shopify API)
    if product.cached_vehicle_fitments:
        print(f"[API] Using cached vehicle fitments ({len(product.cached_vehicle_fitments)} items)")
        shopify_data['vehicle_fitments'] = product.cached_vehicle_fitments
    
    return {
        "local_id": product.id,
        **shopify_data
    }


@router.post("/products/{product_id}/generate-schema")
async def generate_product_schema_endpoint(
    product_id: str,
    data: dict = None,
    dry_run: bool = False,
    db: Session = Depends(get_db),
):
    """
    Phase 2.10 — consolidated AEO metafield blob.

    Composes ALL AEO data into a single `custom.product_schema_json` metafield:

        {
          "@context": "https://schema.org",
          "@graph": [
            {"@type": "FAQPage", "mainEntity": [...]},
            {"@type": "HowTo", "step": [...]}
          ],
          "store_aeo": {
            "rebuild_tier": "...",
            "transmission_codes": [...],
            "primary_transmission_code": "...",
            "oem_numbers": [...],
            "primary_oem": "...",
            "related_product_gids": [...],
            "tldr_summary": "..." (when available — typically from short_description)
          }
        }

    Single Shopify round-trip. The theme reads store_aeo for inline
    additionalProperty / disambiguatingDescription / isRelatedTo emission
    inside the Product schema; @graph entities (FAQPage, HowTo) emit as
    sibling <script> blocks via product.json custom_liquid.

    DUAL-WRITE during transition: also writes the legacy individual
    metafields so the existing theme readers (Phase 1.x-2.5) keep working
    until Phase 2.10 theme refactor lands.

    Set ?dry_run=true to compose and return the blob WITHOUT writing to
    Shopify. Use this to preview the structure before publishing.

    Accepts description_html in the request body (from the editor) so the
    user can preview against unsaved content; otherwise fetches from Shopify
    (with local DB fallback).
    """
    from app.services.aeo.schema_generator import (
        generate_schema_from_product_page,
        extract_faq_from_html,
        extract_oem_references_from_html,
    )
    from app.services.rebuild_tier import classify_rebuild_tier, derive_repair_intent

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Phase 2.10b: ALWAYS fetch shopify_data so we have access to existing legacy
    # metafields for smart-merge (custom.product_faqs, custom.product_tldr_summary).
    # Description can still be overridden by request body for unsaved-preview flow.
    shopify_data = shopify_service.get_product_full_details(product.shopify_id)

    description_html = ''
    vehicle_fitments = []

    if data and data.get('description_html'):
        description_html = data['description_html']
    elif shopify_data:
        description_html = shopify_data.get('body_html', '')
    elif product.current_description_html:
        description_html = product.current_description_html

    # Get vehicle fitments
    if product.cached_vehicle_fitments:
        vehicle_fitments = product.cached_vehicle_fitments
    elif shopify_data:
        vehicle_fitments = shopify_data.get('vehicle_fitments', [])

    # Get image URL
    image_url = ''
    try:
        images = shopify_service.get_product_images(str(product.shopify_id))
        if images:
            image_url = images[0].get('src', '')
    except Exception:
        pass

    product_data = {
        'title': data.get('h1_title', product.title) if data else product.title,
        'sku': product.sku or '',
        'price': str(product.price or '0.00'),
        'vendor': product.vendor or '',
        'handle': product.handle or '',
        'product_type': product.product_type or '',
        'image_url': image_url,
    }

    schema = generate_schema_from_product_page(
        product_data=product_data,
        description_html=description_html,
        vehicle_fitments=vehicle_fitments,
    )

    # ─────────────────────────────────────────────────────────────────
    # Phase 2.10 — compose a single consolidated blob for product_schema_json
    # ─────────────────────────────────────────────────────────────────
    extracted_faqs = extract_faq_from_html(description_html) or []
    extracted_oems = extract_oem_references_from_html(description_html) or []
    classified_tier = classify_rebuild_tier(product.vendor, product.product_type)

    # Phase 2.10b — smart-merge legacy metafields so running Section 9 doesn't
    # destroy Grok-generated content (TL;DR + FAQs from product_enrichment).
    # Fresh extracts WIN; legacy values fill gaps.
    import json as _json_merge
    existing_metas = (shopify_data or {}).get('metafields', {}) or {}

    if not extracted_faqs and existing_metas.get('custom.product_faqs'):
        try:
            raw = existing_metas['custom.product_faqs']
            legacy_faqs = _json_merge.loads(raw) if isinstance(raw, str) else raw
            if isinstance(legacy_faqs, list):
                extracted_faqs = [
                    {
                        'question': (f.get('q') or f.get('question') or '').strip(),
                        'answer': (f.get('a') or f.get('answer') or '').strip(),
                    }
                    for f in legacy_faqs
                    if isinstance(f, dict)
                ]
                extracted_faqs = [f for f in extracted_faqs if f['question'] and f['answer']]
        except Exception:
            pass

    if not extracted_oems and existing_metas.get('custom.oem_numbers'):
        try:
            raw = existing_metas['custom.oem_numbers']
            legacy_oems = _json_merge.loads(raw) if isinstance(raw, str) else raw
            if isinstance(legacy_oems, list):
                extracted_oems = [str(o).strip() for o in legacy_oems if o]
        except Exception:
            pass

    # Inline FAQs back into @graph (Phase 2.10 reverses the Phase 2.9 dedupe —
    # FAQs live INSIDE the consolidated blob now, so re-emitting them in @graph
    # alongside HowTo is correct. The Phase 2.4 separate custom.product_faqs
    # metafield is being deprecated by this consolidation).
    if extracted_faqs:
        faq_entities = []
        for f in extracted_faqs:
            q = (f.get('question') or '').strip()
            a = (f.get('answer') or '').strip()
            if q and a:
                faq_entities.append({
                    "@type": "Question",
                    "name": q,
                    "acceptedAnswer": {"@type": "Answer", "text": a},
                })
        if faq_entities:
            schema.setdefault('@graph', []).insert(0, {
                "@type": "FAQPage",
                "name": f"Preguntas Frecuentes - {product.title or ''}",
                "mainEntity": faq_entities,
            })

    # Build the store_aeo extension section (non-standard schema.org keys
    # but tolerated by JSON-LD parsers; theme reads them for inline emission).
    transmission_codes = list(product.transmission_codes or [])
    primary_tcode = product.transmission_code or (transmission_codes[0] if transmission_codes else None)
    related_gids: list = []
    if product.top_companions:
        for c in product.top_companions[:5]:
            if isinstance(c, dict):
                sid = str(c.get('shopify_id') or '').strip()
                if sid.isdigit():
                    related_gids.append(f"gid://shopify/Product/{sid}")
    primary_oem = extracted_oems[0] if extracted_oems else None

    # TL;DR: prefer request-body short_description (unsaved preview), then
    # legacy product_tldr_summary metafield (Grok-generated by enrichment
    # service), then fall back to nothing (don't fabricate from short text).
    tldr_summary = ''
    if data and data.get('short_description'):
        tldr_summary = str(data.get('short_description') or '').strip()
    if not tldr_summary:
        legacy_tldr = existing_metas.get('custom.product_tldr_summary')
        if legacy_tldr:
            tldr_summary = str(legacy_tldr).strip()

    aeo: dict = {}
    if classified_tier:
        aeo['rebuild_tier'] = classified_tier
    # Phase 3.5b — canonical repair-intent categories.
    repair_intents = derive_repair_intent(classified_tier, product.product_type)
    if repair_intents:
        aeo['repair_intent'] = repair_intents
    if transmission_codes:
        aeo['transmission_codes'] = transmission_codes
    if primary_tcode:
        aeo['primary_transmission_code'] = primary_tcode
    if extracted_oems:
        aeo['oem_numbers'] = extracted_oems
    if primary_oem:
        aeo['primary_oem'] = primary_oem
    if related_gids:
        aeo['related_product_gids'] = related_gids
    if tldr_summary and len(tldr_summary) >= 40:
        aeo['tldr_summary'] = tldr_summary

    # Phase 3.1+3.1g — fault codes via KG-first / Grok-fallback.
    try:
        from app.services.fault_code_discovery_service import (
            discover_fault_codes_for_product,
            build_howto_entities,
            to_compact_dicts,
        )
        fault_codes = await discover_fault_codes_for_product(product, db)
        if fault_codes:
            aeo['fixes_fault_codes'] = to_compact_dicts(fault_codes)
            howto_entities = build_howto_entities(fault_codes, product.title or '')
            if howto_entities:
                schema.setdefault('@graph', []).extend(howto_entities)
    except Exception as fc_err:
        print(f"[generate-schema] fixes_fault_codes skipped for {product.id}: {fc_err}")

    # Phase 3.2 — PAA questions into FAQPage + top GSC queries into aeo.
    try:
        from app.services.product_paa_gsc_service import (
            enrich_with_paa_questions,
            get_top_search_queries,
            paa_to_faq_entities,
            top_queries_to_compact_dicts,
        )
        graph = schema.setdefault('@graph', [])
        faq_page = next((e for e in graph if e.get('@type') == 'FAQPage'), None)
        existing_q_texts = [
            (m.get('name') or '')
            for m in (faq_page.get('mainEntity', []) if faq_page else [])
        ]
        paa = await enrich_with_paa_questions(
            product, db,
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
                    "name": f"Preguntas Frecuentes - {product.title or ''}",
                    "mainEntity": paa_entities,
                })
            aeo['paa_questions_added'] = len(paa_entities)

        top_q = await get_top_search_queries(product, max_queries=8)
        if top_q:
            aeo['top_search_queries'] = top_queries_to_compact_dicts(top_q)
    except Exception as paa_err:
        print(f"[generate-schema] PAA/GSC enrichment skipped for {product.id}: {paa_err}")

    # Phase 3.5c — professional notes via Grok. Smart-merge: preserve
    # existing notes from the consolidated blob rather than re-firing Grok
    # on every re-compose (notes are stable per product; costs add up).
    try:
        existing_notes = None
        existing_blob_raw = existing_metas.get('custom.product_schema_json')
        if existing_blob_raw:
            try:
                existing_blob = (
                    _json_merge.loads(existing_blob_raw)
                    if isinstance(existing_blob_raw, str) else existing_blob_raw
                )
                existing_aeo_blob = (existing_blob or {}).get('store_aeo') or {}
                existing_notes = existing_aeo_blob.get('professional_notes')
            except Exception:
                existing_notes = None

        if existing_notes:
            aeo['professional_notes'] = existing_notes
        else:
            from app.services.product_professional_notes_service import (
                generate_professional_notes,
            )
            fc_codes = [fc.get('code') for fc in (aeo.get('fixes_fault_codes') or []) if fc.get('code')]
            pro_notes = await generate_professional_notes(
                product, db, fault_code_codes=fc_codes or None,
            )
            if pro_notes:
                aeo['professional_notes'] = pro_notes
    except Exception as pn_err:
        print(f"[generate-schema] professional_notes skipped for {product.id}: {pn_err}")

    # Phase 3.3: prepend Organization (Example Store seller authority) to @graph.
    # Idempotent so re-running generation doesn't duplicate.
    try:
        from app.services.eeat_generator import get_eeat_generator
        org_entity = get_eeat_generator().build_organization_entity()
        graph = schema.setdefault('@graph', [])
        if not any(
            isinstance(e, dict) and e.get('@id') == org_entity['@id']
            for e in graph
        ):
            graph.insert(0, org_entity)
    except Exception as org_err:
        print(f"[generate-schema] Organization entity skipped for {product.id}: {org_err}")

    if aeo:
        schema['store_aeo'] = aeo

    import json as _json
    schema_value = _json.dumps(schema, ensure_ascii=False)

    # ─────────────────────────────────────────────────────────────────
    # Dry-run: return composed blob without writing. Lets caller preview
    # the structure before any Shopify metafield write.
    # ─────────────────────────────────────────────────────────────────
    if dry_run:
        return {
            "product_id": str(product_id),
            "dry_run": True,
            "schema": schema,
            "entities_count": len(schema.get('@graph', [])),
            "has_faq": any(e.get('@type') == 'FAQPage' for e in schema.get('@graph', [])),
            "has_howto": any(e.get('@type') == 'HowTo' for e in schema.get('@graph', [])),
            "aeo_fields_set": sorted(aeo.keys()),
            "blob_size_chars": len(schema_value),
        }

    # ─────────────────────────────────────────────────────────────────
    # Live write — Phase 2.10g cleanup:
    # ONE Shopify call writes only custom.product_schema_json. The 6 legacy
    # individual metafields (transmission_code(s), oem_number(s),
    # related_products, rebuild_tier, product_tldr_summary, product_faqs)
    # were created in error — Phase 1.2/2.2/2.3/2.4/2.5 should have put
    # everything in product_schema_json from the start. The theme is being
    # refactored to read AEO data from the blob's store_aeo extension.
    # Existing legacy metafields on K79900/K119AF/top-25 will be cleaned up
    # via the cleanup_individual_metafields.py script when Theo runs it.
    # ─────────────────────────────────────────────────────────────────
    schema_write_result = shopify_service.update_product(
        product.shopify_id,
        {'metafields': {'custom.product_schema_json': schema_value}},
    )

    return {
        "product_id": str(product_id),
        "dry_run": False,
        "schema": schema,
        "entities_count": len(schema.get('@graph', [])),
        "has_faq": any(e.get('@type') == 'FAQPage' for e in schema.get('@graph', [])),
        "has_howto": any(e.get('@type') == 'HowTo' for e in schema.get('@graph', [])),
        "aeo_fields_set": sorted(aeo.keys()),
        "blob_size_chars": len(schema_value),
        "consolidated_blob_written": bool(schema_write_result),
    }


@router.post("/products/fitments/activate-all")
async def activate_draft_fitments():
    """
    Activate all DRAFT vehicle_fitment metaobjects in Shopify.
    Only affects metaobjects of type 'vehicle_fitment' that are in DRAFT status.
    """
    result = shopify_service.activate_draft_vehicle_fitments()
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.post("/products/{product_id}/refresh-fitments")
async def refresh_vehicle_fitments(product_id: str, db: Session = Depends(get_db)):
    """
    Force refresh vehicle fitments from Shopify.
    Use this if fitments were edited directly in Shopify.
    Updates the local cache with fresh data from Shopify.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    print(f"[API] Refreshing fitments from Shopify for product {product_id}...")
    
    # Fetch fresh data from Shopify (this will call the slow metaobjects API)
    shopify_data = shopify_service.get_product_full_details(product.shopify_id)
    if not shopify_data:
        raise HTTPException(status_code=404, detail="Product not found in Shopify")
    
    # Get the fresh fitments (this came from Shopify metaobjects)
    fresh_fitments = shopify_data.get('vehicle_fitments', [])
    
    # Update local cache
    product.cached_vehicle_fitments = fresh_fitments
    db.commit()
    
    print(f"[API] Refreshed and cached {len(fresh_fitments)} fitments from Shopify")
    
    return {
        "success": True,
        "message": f"Refreshed {len(fresh_fitments)} fitments from Shopify",
        "fitment_count": len(fresh_fitments),
        "vehicle_fitments": fresh_fitments
    }

@router.post("/products/sync-shopify")
@limiter.limit(RATE_SYNC)
async def sync_products_from_shopify(
    request: Request,
    min_description_length: int = 300,  # Products with less than this are "needs SEO"
    db: Session = Depends(get_db)
):
    """
    Sync products from Shopify. Only saves products that need SEO work:
    - Empty or very short descriptions (< min_description_length chars)
    - Missing proper SEO structure (H2, H3, lists)
    
    Products with good content are NOT saved to keep the database focused.
    """
    if settings.USE_CELERY:
        from app.tasks.sync_tasks import sync_shopify_products as sync_task
        task = sync_task.delay(min_description_length)
        return {"task_id": task.id, "status": "queued"}

    try:
        from datetime import datetime as dt

        print("🔄 Starting Shopify sync...")
        shopify_products = shopify_service.get_all_products()
        print(f"📦 Fetched {len(shopify_products)} products from Shopify")

        # Pre-load ALL existing products in one query (avoids N+1 problem)
        existing_map = {
            p.shopify_id: p
            for p in db.query(Product).all()
        }
        print(f"📂 {len(existing_map)} products already in database")

        synced_count = 0
        updated_count = 0

        for sp in shopify_products:
            shopify_id = str(sp.id)
            desc_html = sp.body_html or ''
            desc_length = len(desc_html)
            has_structure = shopify_service._has_seo_structure(desc_html)
            needs_seo = desc_length < min_description_length or not has_structure

            # Collect ALL variant SKUs (not just the first one)
            all_skus = []
            if hasattr(sp, 'variants') and sp.variants:
                for v in sp.variants:
                    if v.sku:
                        all_skus.append(v.sku)
            primary_sku = all_skus[0] if all_skus else ''

            # Parse Shopify timestamps
            shopify_created_at = None
            shopify_updated_at = None
            if hasattr(sp, 'created_at') and sp.created_at:
                try:
                    shopify_created_at = dt.fromisoformat(sp.created_at.replace('Z', '+00:00'))
                except Exception:
                    pass
            if hasattr(sp, 'updated_at') and sp.updated_at:
                try:
                    shopify_updated_at = dt.fromisoformat(sp.updated_at.replace('Z', '+00:00'))
                except Exception:
                    pass

            # Get price from first variant
            price = None
            if hasattr(sp, 'variants') and sp.variants:
                try:
                    price = float(sp.variants[0].price)
                except (ValueError, TypeError):
                    pass

            existing = existing_map.get(shopify_id)

            if existing:
                existing.title = sp.title
                existing.handle = sp.handle
                existing.current_description_html = desc_html
                existing.product_type = sp.product_type
                existing.vendor = getattr(sp, 'vendor', None)
                existing.image_count = len(sp.images) if hasattr(sp, 'images') else 0
                existing.needs_seo = needs_seo
                existing.seo_status = 'needs_seo' if needs_seo else 'published'
                existing.shopify_created_at = shopify_created_at
                existing.shopify_updated_at = shopify_updated_at
                existing.sku = primary_sku
                if price is not None:
                    existing.price = price
                updated_count += 1
            else:
                product = Product(
                    id=shopify_id,
                    shopify_id=shopify_id,
                    sku=primary_sku,
                    title=sp.title,
                    handle=sp.handle,
                    product_type=sp.product_type,
                    vendor=getattr(sp, 'vendor', None),
                    current_description_html=desc_html,
                    image_count=len(sp.images) if hasattr(sp, 'images') else 0,
                    needs_seo=needs_seo,
                    seo_status='needs_seo' if needs_seo else 'published',
                    shopify_created_at=shopify_created_at,
                    shopify_updated_at=shopify_updated_at,
                    price=price,
                )
                db.add(product)
                synced_count += 1

        db.commit()

        # Phase 1.5: refresh transmission_codes after sync so freshly imported
        # or title-edited products immediately have correct codes. After commit
        # so a refresh failure can't roll back the sync.
        try:
            from app.services.aeo.knowledge_graph import create_knowledge_graph_manager
            _kg = create_knowledge_graph_manager(db)
            _refreshed = _kg.update_product_transmission_codes(force_recompute=True)
            print(f"[sync_products_from_shopify] Refreshed transmission_codes on {_refreshed} products")
        except Exception as _kg_err:
            print(f"[sync_products_from_shopify] transmission_codes refresh failed: {_kg_err}")

        total_in_db = db.query(Product).count()
        needs_seo_count = db.query(Product).filter(Product.needs_seo == True).count()

        print(f"📊 Sync Results:")
        print(f"   New products added: {synced_count}")
        print(f"   Existing updated: {updated_count}")
        print(f"   Total in database: {total_in_db}")
        print(f"   Needs SEO work: {needs_seo_count}")

        cache.invalidate_pattern("api:products:list:*")
        cache.invalidate("products:segment_counts")

        return {
            "message": f"Sync complete — {synced_count} new, {updated_count} updated",
            "new_products": synced_count,
            "updated_products": updated_count,
            "total_in_database": total_in_db,
            "total_in_shopify": len(shopify_products),
            "needs_seo": needs_seo_count
        }

    except Exception as e:
        import traceback
        print(f"❌ Shopify sync error: {e}")
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/products/check-new")
async def check_new_products(
    min_description_length: int = 300,
    db: Session = Depends(get_db)
):
    """
    Quick check for new products only - much faster than full sync.
    Only adds products that don't exist in the database yet.
    Does NOT update existing products.
    """
    try:
        print("🔍 Checking for new products in Shopify...")
        shopify_products = shopify_service.get_all_products()
        
        # Get all existing shopify_ids from database
        existing_ids = {p.shopify_id for p in db.query(Product.shopify_id).all()}
        
        new_count = 0
        
        for sp in shopify_products:
            shopify_id = str(sp.id)
            
            # Skip if already exists
            if shopify_id in existing_ids:
                continue
            
            # This is a new product - add it
            desc_html = sp.body_html or ''
            desc_length = len(desc_html)
            has_structure = shopify_service._has_seo_structure(desc_html)
            needs_seo = desc_length < min_description_length or not has_structure
            
            product = Product(
                id=shopify_id,
                shopify_id=shopify_id,
                sku=sp.variants[0].sku if sp.variants else '',
                title=sp.title,
                handle=sp.handle,
                product_type=sp.product_type,
                current_description_html=desc_html,
                image_count=len(sp.images) if hasattr(sp, 'images') else 0,
                needs_seo=needs_seo,
                seo_status='needs_seo' if needs_seo else 'published'
            )
            db.add(product)
            new_count += 1
            print(f"   ✅ New product: {sp.title[:50]}...")
        
        db.commit()

        # Phase 1.5: refresh transmission_codes for the freshly added products.
        # force_recompute=False is enough — new products have NULL columns and
        # the default filter catches them.
        try:
            from app.services.aeo.knowledge_graph import create_knowledge_graph_manager
            _kg = create_knowledge_graph_manager(db)
            _refreshed = _kg.update_product_transmission_codes(force_recompute=False)
            print(f"[check_new_products] Refreshed transmission_codes on {_refreshed} products")
        except Exception as _kg_err:
            print(f"[check_new_products] transmission_codes refresh failed: {_kg_err}")

        total_in_db = db.query(Product).count()
        total_in_shopify = len(shopify_products)
        
        print(f"📊 Check New Results:")
        print(f"   New products added: {new_count}")
        print(f"   Total in database: {total_in_db}")
        print(f"   Total in Shopify: {total_in_shopify}")
        
        return {
            "message": f"Found {new_count} new product(s)" if new_count > 0 else "No new products found",
            "new_products": new_count,
            "total_in_database": total_in_db,
            "total_in_shopify": total_in_shopify,
            "in_sync": total_in_db == total_in_shopify
        }
        
    except Exception as e:
        import traceback
        print(f"❌ Check new products error: {e}")
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/products/sync-sales")
@limiter.limit(RATE_SYNC)
async def sync_sales_data(request: Request, db: Session = Depends(get_db)):
    """
    Sync sales data from Shopify orders.
    Fetches orders and aggregates sales data for 30d, 90d, 365d, and all-time periods.
    This can take a while if you have many orders.
    """
    if settings.USE_CELERY:
        from app.tasks.sync_tasks import sync_sales_data as sync_task
        task = sync_task.delay()
        return {"task_id": task.id, "status": "queued"}

    try:
        print("[API] Starting sales data sync...")

        # Fetch sales data for all time periods
        sales_data = shopify_service.get_product_sales_all_periods()

        if not sales_data:
            return {
                "message": "No sales data found or error fetching",
                "products_updated": 0
            }

        # Bulk-load products by shopify_id in one query instead of N separate
        # lookups inside the loop (5,000+ products × ~2 ms each was adding
        # ~9 s of pure DB roundtrip cost).
        shopify_ids = [str(sid) for sid in sales_data.keys()]
        products_by_shopify_id = {
            p.shopify_id: p
            for p in db.query(Product).filter(Product.shopify_id.in_(shopify_ids)).all()
        }

        # Update products in database
        updated_count = 0
        for product_shopify_id, periods in sales_data.items():
            product = products_by_shopify_id.get(str(product_shopify_id))

            if product:
                # Update legacy fields (90d for backward compatibility)
                product.total_sold = periods['90d']['total_sold']
                product.total_revenue = periods['90d']['total_revenue']
                
                # Update new time-period fields
                product.sold_30d = periods['30d']['total_sold']
                product.revenue_30d = periods['30d']['total_revenue']
                product.sold_90d = periods['90d']['total_sold']
                product.revenue_90d = periods['90d']['total_revenue']
                product.sold_365d = periods['365d']['total_sold']
                product.revenue_365d = periods['365d']['total_revenue']
                product.sold_all_time = periods['all_time']['total_sold']
                product.revenue_all_time = periods['all_time']['total_revenue']
                
                updated_count += 1

        db.commit()

        print(f"[API] Sales sync complete: {updated_count} products updated")
        print(f"[API] Time periods: 30d, 90d, 365d, all_time")

        cache.invalidate_pattern("api:products:list:*")
        cache.invalidate("products:segment_counts")

        return {
            "message": "Sales data synced successfully",
            "products_with_sales": len(sales_data),
            "products_updated": updated_count,
            "periods": ["30d", "90d", "365d", "all_time"]
        }

    except Exception as e:
        import traceback
        print(f"❌ Sales sync error: {e}")
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/products/sync-analytics")
@limiter.limit(RATE_SYNC)
async def sync_product_analytics_endpoint(request: Request, db: Session = Depends(get_db)):
    """Sync GA4 and Search Console data to products"""
    if settings.USE_CELERY:
        from app.tasks.sync_tasks import sync_product_analytics as sync_task
        task = sync_task.delay()
        return {"task_id": task.id, "status": "queued"}

    try:
        service = ProductService(db)
        result = await service.sync_product_analytics()
        cache.invalidate_pattern("api:products:list:*")
        cache.invalidate("products:segment_counts")
        return result
    except Exception as e:
        import traceback
        print(f"❌ Analytics sync error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/products/sync-inventory")
async def sync_inventory_from_shopify(
    data: dict = Body(default={}),  # JSON body with product_ids
    db: Session = Depends(get_db)
):
    """
    Sync inventory data from Shopify for specific products.
    Only fetches inventory for the provided product IDs (paginated approach).
    Supports TTL-based caching: products synced within max_age_minutes are skipped.
    
    Body params:
        product_ids: list of product IDs to sync
        max_age_minutes: TTL in minutes (default 60) - skip products synced within this window
        force: bool (default False) - bypass TTL and force re-sync all
    """
    try:
        product_ids = data.get('product_ids', [])
        max_age_minutes = data.get('max_age_minutes', 60)
        force = data.get('force', False)
        
        if not product_ids:
            return {
                "message": "No product IDs provided",
                "products_synced": 0,
                "products_updated": 0,
                "skipped": 0
            }
        
        print(f"[API] Starting inventory sync for {len(product_ids)} products (TTL={max_age_minutes}min, force={force})...")
        
        # Get only the requested products
        products = db.query(Product).filter(Product.id.in_(product_ids)).all()
        
        if not products:
            return {
                "message": "No products found",
                "products_synced": 0,
                "products_updated": 0,
                "skipped": 0
            }
        
        # TTL-based filtering: skip products with fresh inventory data
        if not force:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
            needs_sync = [
                p for p in products
                if not p.last_inventory_sync or p.last_inventory_sync.replace(tzinfo=p.last_inventory_sync.tzinfo or timezone.utc) < cutoff
            ]
            skipped = len(products) - len(needs_sync)
        else:
            needs_sync = list(products)
            skipped = 0
        
        if not needs_sync:
            print(f"[API] All {len(products)} products have fresh inventory data (synced within {max_age_minutes}min), skipping")
            return {
                "message": "All inventory data is fresh",
                "products_synced": 0,
                "products_updated": 0,
                "skipped": skipped,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        print(f"[API] {len(needs_sync)} products need sync, {skipped} skipped (fresh cache)")
        
        # Fetch inventory in bulk (more efficient)
        # Use shopify_id (numeric) not id (UUID) for GraphQL queries
        shopify_product_ids = [p.shopify_id for p in needs_sync]
        
        print(f"[API] Shopify IDs to sync: {shopify_product_ids[:5]}...")  # DEBUG
        
        # Get inventory for these products (max 50 per call)
        inventory_data = shopify_service.get_inventory_bulk(shopify_product_ids)
        
        # Update products with inventory data
        updated_count = 0
        for product in needs_sync:
            if product.shopify_id in inventory_data:
                inv = inventory_data[product.shopify_id]
                product.inventory_quantity = inv["quantity"]
                product.inventory_status = inv["status"]
                product.last_inventory_sync = datetime.now(timezone.utc)
                updated_count += 1
        
        db.commit()
        
        print(f"[API] Inventory sync complete: {updated_count}/{len(needs_sync)} products updated, {skipped} skipped")
        
        return {
            "message": "Inventory sync completed successfully",
            "products_synced": len(needs_sync),
            "products_updated": updated_count,
            "skipped": skipped,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        import traceback
        print(f"❌ Inventory sync error: {e}")
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/analytics/diagnostics")
async def get_analytics_diagnostics(db: Session = Depends(get_db)):
    """
    Diagnostic endpoint to check why analytics data might not be syncing.
    Returns configuration status and sample data from GA4/GSC.
    """
    import os
    from app.services.google_api_service import GoogleApiService
    
    try:
        # Check environment variables
        config = {
            "ga4_property_id": os.getenv('GOOGLE_GA4_PROPERTY_ID', 'NOT SET'),
            "gsc_site_url": os.getenv('GOOGLE_SEARCH_CONSOLE_SITE_URL', 'NOT SET'),
            "credentials_path": os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'NOT SET'),
            "credentials_exists": os.path.exists(os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')) if os.getenv('GOOGLE_APPLICATION_CREDENTIALS') else False
        }
        
        # Initialize service and check credentials
        google_service = GoogleApiService()
        
        # Test GA4 connection
        print("\n🔍 Testing GA4 connection...")
        ga4_test = google_service.get_ga4_engagement_data(days=7)
        ga4_working = len(ga4_test) > 0
        
        # Test GSC connection  
        print("🔍 Testing Search Console connection...")
        gsc_test = google_service.get_search_console_product_data(days=7)
        gsc_working = len(gsc_test) > 0
        
        # Get product stats
        products = db.query(Product).all()
        total_products = len(products)
        with_ga4 = sum(1 for p in products if p.ga4_sessions and p.ga4_sessions > 0)
        with_gsc = sum(1 for p in products if p.gsc_impressions and p.gsc_impressions > 0)
        with_handles = sum(1 for p in products if p.handle)
        
        # Show sample product handles
        sample_handles = [p.handle for p in products[:5] if p.handle]
        
        return {
            "configuration": config,
            "connections": {
                "ga4_working": ga4_working,
                "gsc_working": gsc_working,
                "credentials_loaded": google_service.credentials is not None
            },
            "sample_data": {
                "ga4_pages": [d.get('page_path', 'N/A') for d in ga4_test[:5]],
                "gsc_pages": [d.get('page', 'N/A') for d in gsc_test[:5]]
            },
            "product_stats": {
                "total": total_products,
                "with_handles": with_handles,
                "with_ga4_data": with_ga4,
                "with_gsc_data": with_gsc,
                "sample_handles": sample_handles
            },
            "recommendations": [
                "If GA4 is not working: Check GOOGLE_GA4_PROPERTY_ID is set correctly (just the numeric ID, not the full property string)",
                "If GSC is not working: Check GOOGLE_SEARCH_CONSOLE_SITE_URL includes https:// and trailing slash (e.g., https://example.com/)",
                "If credentials fail: Ensure service account has access to both GA4 property and Search Console property",
                "If no products match: Compare sample product handles with GA4/GSC page paths to ensure URL format matches"
            ]
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "error": str(e),
            "configuration": {
                "ga4_property_id": os.getenv('GOOGLE_GA4_PROPERTY_ID', 'NOT SET'),
                "gsc_site_url": os.getenv('GOOGLE_SEARCH_CONSOLE_SITE_URL', 'NOT SET'),
            }
        }


@router.get("/products/analytics/summary")
async def get_analytics_summary(db: Session = Depends(get_db)):
    """Get summary of product analytics data"""
    try:
        service = ProductService(db)
        summary = await service.get_product_analytics_summary()
        return summary
    except Exception as e:
        import traceback
        print(f"❌ Analytics summary error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{product_id}")
async def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    sp = shopify_service.get_product_by_id(product.shopify_id)
    
    return {
        "id": product.id,
        "shopify_id": product.shopify_id,
        "title": product.title,
        "sku": product.sku,
        "handle": product.handle,
        "current_description_html": product.current_description_html,
        "needs_seo": product.needs_seo,
        "seo_status": product.seo_status,
        "shopify_data": {
            "title": sp.title if sp else product.title,
            "body_html": sp.body_html if sp else product.current_description_html,
            "images": shopify_service.get_product_images(product.shopify_id) if sp else []
        }
    }


_YEAR_RANGE_RE = __import__('re').compile(
    # 4-digit alternatives come first so "2010-2015" doesn't get parsed as
    # "20" → year_start=2020 (the regex would prefer the 2-digit branch otherwise).
    r'(\d{4}|\d{2})\s*[-–—a]+\s*(\d{4}|\d{2})|(\d{4})|(\d{2})',
    __import__('re').IGNORECASE,
)


def _expand_2digit_year(yr: str) -> Optional[int]:
    """'21' → 2021, '95' → 1995. Cutoff at 30 for 21st century."""
    if not yr:
        return None
    if len(yr) == 4:
        try:
            return int(yr)
        except ValueError:
            return None
    if len(yr) == 2:
        try:
            n = int(yr)
            return 2000 + n if n < 30 else 1900 + n
        except ValueError:
            return None
    return None


def _parse_vehicle_fitments_from_html(description_html: str) -> List[dict]:
    """Gap #8 — extract vehicle fitments from a product description's H4 table.

    Produces the same shape Product.cached_vehicle_fitments holds (the FE+metaobject
    format): id/make/modelo/year_start/year_end/transmission_type/transmission_model/engine.

    Used by update_product_details to keep cached_vehicle_fitments in sync with
    what the description actually shows when the FE didn't send an explicit
    fitments payload. Does NOT push to Shopify metaobjects — curator-edited
    metaobjects remain the source of truth; this only updates the local cache
    so the UI doesn't show stale counts after a description-only edit.
    """
    import re
    if not description_html:
        return []

    # Locate <h4>Vehiculos</h4> (or variants) followed by a <table>, optionally
    # wrapped in a <div>.
    h4_match = re.search(
        r'<h4[^>]*>\s*(?:Veh[ií]culos?|Compatibilidad|Aplicaci[oó]n(?:es)?|Fitment|Modelos)[^<]*</h4>'
        r'\s*(?:<div[^>]*>\s*)?(<table.*?</table>)',
        description_html,
        re.IGNORECASE | re.DOTALL,
    )
    if not h4_match:
        return []
    table_html = h4_match.group(1)

    tbody_match = re.search(r'<tbody[^>]*>(.*?)</tbody>', table_html, re.IGNORECASE | re.DOTALL)
    rows_html = tbody_match.group(1) if tbody_match else table_html
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', rows_html, re.IGNORECASE | re.DOTALL)

    fitments: List[dict] = []
    next_id = 1
    for row_html in rows:
        cells = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row_html, re.IGNORECASE | re.DOTALL)
        if len(cells) < 3:
            continue
        cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
        # Skip header row when <thead> wasn't separated
        if cells[0].lower() in ('marca', 'make', 'brand'):
            continue

        marca = cells[0].upper().strip()
        modelo = cells[1].upper().strip() if len(cells) > 1 else ''
        years_cell = cells[2] if len(cells) > 2 else ''
        trans_cell = cells[3] if len(cells) > 3 else ''
        motor_cell = cells[4] if len(cells) > 4 else ''

        # Years range: "2010-2015" / "2010 - 2015" / "2010 a 2015" / "2010" / "10-15"
        year_start: Optional[int] = None
        year_end: Optional[int] = None
        ym = _YEAR_RANGE_RE.search(years_cell)
        if ym:
            if ym.group(1) and ym.group(2):
                year_start = _expand_2digit_year(ym.group(1))
                year_end = _expand_2digit_year(ym.group(2))
            elif ym.group(3):
                yr = _expand_2digit_year(ym.group(3))
                year_start = year_end = yr
            elif ym.group(4):
                yr = _expand_2digit_year(ym.group(4))
                year_start = year_end = yr

        if not marca and not modelo:
            continue

        fitments.append({
            'id': next_id,
            'make': [marca] if marca else [],
            'modelo': [modelo] if modelo else [],
            'year_start': year_start,
            'year_end': year_end,
            'transmission_type': '',
            'transmission_model': trans_cell or '',
            'engine': motor_cell or '',
        })
        next_id += 1
    return fitments


def _save_content_history(
    db: Session,
    product_id: str,
    status: str,
    h1_title: str = None,
    description_html: str = None,
    meta_title: str = None,
    meta_description: str = None,
    url_handle: str = None,
    short_description: str = None,
    libraries_used: list = None,
    llm_used: str = None
) -> GenerationHistory:
    """Save a content version to generation history for rollback capability."""
    history = GenerationHistory(
        id=str(uuid.uuid4()),
        product_id=str(product_id),
        status=status,
        h1_title=h1_title,
        description_html=description_html,
        meta_title=meta_title,
        meta_description=meta_description,
        url_handle=url_handle,
        short_description=short_description,
        libraries_used=libraries_used or [],
        llm_used=llm_used
    )
    db.add(history)
    return history


@router.put("/products/{product_id}")
async def update_product_details(product_id: str, data: dict, db: Session = Depends(get_db)):
    """Update product content locally and in Shopify. Saves version history for rollback."""
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # === SAVE CURRENT STATE AS BACKUP (before updating) ===
        # Fetch current Shopify data for complete backup
        current_shopify = shopify_service.get_product_full_details(product.shopify_id)
        if current_shopify:
            _save_content_history(
                db=db,
                product_id=product.id,
                status='previous',
                h1_title=current_shopify.get('title'),
                description_html=current_shopify.get('body_html'),
                meta_title=current_shopify.get('metafields', {}).get('metafields_global_title_tag'),
                meta_description=current_shopify.get('metafields', {}).get('metafields_global_description_tag'),
                url_handle=current_shopify.get('handle')
            )
        
        # Handle vehicle fitments separately - they go to metaobjects
        vehicle_fitments = data.get('vehicle_fitments')
        if vehicle_fitments and len(vehicle_fitments) > 0:
            print(f"[API] Saving {len(vehicle_fitments)} vehicle fitments to metaobjects...")
            fitment_result = shopify_service.save_vehicle_fitments_to_metaobjects(
                product.shopify_id,
                vehicle_fitments
            )
            if not fitment_result:
                print("[API] Warning: Failed to save vehicle fitments to metaobjects")

            # Cache fitments locally for fast loading
            product.cached_vehicle_fitments = vehicle_fitments
            print(f"[API] Cached {len(vehicle_fitments)} fitments locally")
        elif data.get('description_html') is not None:
            # Gap #8 — description-only save: the FE didn't send an explicit
            # vehicle_fitments payload (no "Auto-Detectar" click), but the
            # description_html that was just persisted may have a fresh
            # <h4>Vehiculos</h4> table. Re-parse it into the cache shape so
            # subsequent reads from Product.cached_vehicle_fitments match what
            # the user can see in the description. Shopify metaobjects are
            # intentionally NOT updated here — those remain curator-controlled
            # and a /refresh-fitments call will still overwrite this cache.
            try:
                parsed = _parse_vehicle_fitments_from_html(data.get('description_html') or '')
                if parsed:
                    product.cached_vehicle_fitments = parsed
                    print(f"[API] Gap #8: re-parsed {len(parsed)} fitment(s) "
                          f"from description and refreshed cached_vehicle_fitments "
                          f"(metaobjects untouched)")
            except Exception as e:
                print(f"[API] Gap #8: description fitment re-parse failed (non-blocking): {e}")

        # Convert alt_tags array to image_alts dict if provided
        image_alts = data.get('image_alts', {})
        if not image_alts and data.get('alt_tags'):
            # Convert alt_tags format to image_alts format
            image_alts = shopify_service.convert_alt_tags_to_image_alts(
                product.shopify_id, 
                data.get('alt_tags', [])
            )
            print(f"[API] Converted {len(data.get('alt_tags', []))} alt_tags to image_alts")
        
        # Debug: Log the data being received
        print(f"[API] Received short_description: {data.get('short_description', 'MISSING')[:100] if data.get('short_description') else 'NONE'}")
        print(f"[API] Received compatible_vehicles: {data.get('compatible_vehicles', 'MISSING')[:100] if data.get('compatible_vehicles') else 'NONE'}")
        
        # Prepare Shopify update data (without vehicle_fitments - handled above)
        shopify_update = {
            'title': data.get('h1_title'),
            'body_html': data.get('description_html'),
            'handle': data.get('url_handle'),
            'metafields_global_title_tag': data.get('meta_title'),
            'metafields_global_description_tag': data.get('meta_description'),
            'metafields': {},
            'image_alts': image_alts
        }
        
        # Add metafields only if they have values (including empty string)
        if data.get('short_description') is not None:
            shopify_update['metafields']['standard.product_description'] = data.get('short_description')
        if data.get('compatible_vehicles') is not None:
            shopify_update['metafields']['custom.custom_compatible_vehicles'] = data.get('compatible_vehicles')
        if data.get('resumen') is not None:
            shopify_update['metafields']['custom.resumen'] = data.get('resumen')
        
        # JSON-LD Product Schema metafield
        if data.get('product_schema') is not None:
            import json as _json
            schema_value = data.get('product_schema')
            # Ensure it's a JSON string for storage
            if isinstance(schema_value, dict):
                schema_value = _json.dumps(schema_value, ensure_ascii=False)
            shopify_update['metafields']['custom.product_schema_json'] = schema_value
            print(f"[API] Saving product_schema to custom.product_schema_json ({len(schema_value)} chars)")
        elif data.get('description_html') is not None:
            # Gap #9 — description changed but the FE didn't include a freshly
            # composed schema (no "Generar Schema" click). Auto-build the same
            # consolidated blob the explicit endpoint produces and fold it into
            # this single Shopify update call, so the schema never drifts behind
            # the description. Re-uses generate_product_schema_endpoint in
            # dry_run mode for full reuse — including its smart-merge that
            # preserves Grok-generated professional_notes between calls so we
            # don't re-bill Grok on every save.
            try:
                schema_input = {
                    'description_html': data.get('description_html') or '',
                    'h1_title': data.get('h1_title') or '',
                    'short_description': data.get('short_description') or '',
                }
                schema_resp = await generate_product_schema_endpoint(
                    product_id=product_id,
                    data=schema_input,
                    dry_run=True,
                    db=db,
                )
                composed_schema = schema_resp.get('schema') if isinstance(schema_resp, dict) else None
                if composed_schema:
                    import json as _json
                    composed_value = _json.dumps(composed_schema, ensure_ascii=False)
                    shopify_update['metafields']['custom.product_schema_json'] = composed_value
                    print(f"[API] Gap #9: auto-composed product_schema_json "
                          f"({schema_resp.get('blob_size_chars', len(composed_value))} chars, "
                          f"{schema_resp.get('entities_count', 0)} @graph entities, "
                          f"aeo_fields={schema_resp.get('aeo_fields_set', [])})")
            except Exception as e:
                # Non-blocking: if schema composition fails (Grok down, PAA
                # timeout, …) the save still proceeds without the auto-schema.
                # The user can hit "Generar Schema" manually to retry.
                print(f"[API] Gap #9: auto-schema composition failed (non-blocking): {e}")


        # Remove None values
        shopify_update = {k: v for k, v in shopify_update.items() if v is not None}
        if 'metafields' in shopify_update:
            shopify_update['metafields'] = {k: v for k, v in shopify_update['metafields'].items() if v is not None}
            print(f"[API] Metafields to save: {list(shopify_update['metafields'].keys())}")
        
        # Update Shopify (basic fields)
        result = shopify_service.update_product(product.shopify_id, shopify_update)
        
        # Update image alt texts via GraphQL (more reliable than REST)
        if data.get('alt_tags'):
            print(f"[API] Updating image alt texts via GraphQL...")
            shopify_service.update_product_images_graphql(product.shopify_id, data.get('alt_tags', []))
        
        # === SAVE NEW STATE AS PUBLISHED ===
        _save_content_history(
            db=db,
            product_id=product.id,
            status='published',
            h1_title=data.get('h1_title'),
            description_html=data.get('description_html'),
            meta_title=data.get('meta_title'),
            meta_description=data.get('meta_description'),
            url_handle=data.get('url_handle'),
            short_description=data.get('short_description'),
            libraries_used=data.get('libraries_used', [])
        )
        
        # Update local database
        if 'h1_title' in data: product.title = data['h1_title']
        if 'description_html' in data: product.current_description_html = data['description_html']
        if 'url_handle' in data: product.handle = data['url_handle']
        
        db.commit()
        
        return {
            "success": True,
            "message": "Product updated successfully",
            "shopify_id": product.shopify_id,
            "history_saved": True
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def _compute_performance_tier(impressions: int, position: float) -> str:
    """Same tier logic as content_analyzer.py — HIGH for strong organic performers
    that should not be disturbed without explicit override."""
    if impressions >= 1000 and 0 < position < 10:
        return "HIGH"
    if impressions >= 200:
        return "ESTABLISHED"
    return "DEVELOPING"


@router.post("/products/{product_id}/publish")
async def publish_product_content(
    product_id: str,
    content: dict,
    force: bool = False,
    db: Session = Depends(get_db)
):
    """Publish SEO content to Shopify. Saves version history for rollback.

    SEO Guardrail: this endpoint re-checks live GSC metrics and refuses to change
    h1_title / meta_title / url_handle on HIGH-tier products (>=1000 impressions,
    position 1-9). Strong rankings align with Google's signals; rewriting the
    ranked assets resets that alignment and can collapse traffic. Pass `force=true`
    as a query param to override — use only when you know what you're doing.
    """
    try:
        product = db.query(Product).filter(Product.id == product_id).first()

        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        # === SEO GUARDRAIL — fail loudly before touching Shopify ===
        tier = _compute_performance_tier(
            product.gsc_impressions or 0,
            product.gsc_position or 0.0,
        )
        if tier == "HIGH" and not force:
            # Compare proposed content against current Shopify state
            _current_shopify_peek = shopify_service.get_product_full_details(product.shopify_id)
            _current_title = (_current_shopify_peek or {}).get('title') or product.title or ""
            _current_handle = (_current_shopify_peek or {}).get('handle') or product.handle or ""
            _current_meta = (
                (_current_shopify_peek or {}).get('metafields', {}).get('metafields_global_title_tag')
                or ""
            )

            proposed_title = content.get('h1_title') or ""
            proposed_handle = content.get('url_handle') or ""
            proposed_meta = content.get('meta_title') or ""

            blocked: list[str] = []
            if proposed_title and proposed_title != _current_title:
                blocked.append(f"h1_title ({_current_title!r} → {proposed_title!r})")
            if proposed_handle and proposed_handle != _current_handle:
                blocked.append(f"url_handle ({_current_handle!r} → {proposed_handle!r})")
            if proposed_meta and proposed_meta != _current_meta:
                blocked.append(f"meta_title ({_current_meta!r} → {proposed_meta!r})")

            if blocked:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "seo_guardrail_blocked",
                        "message": (
                            f"Product is HIGH tier ({product.gsc_impressions} impressions, "
                            f"position {product.gsc_position:.1f}). Refusing to change ranked "
                            f"assets that Google already rewards. Pass ?force=true to override."
                        ),
                        "performance_tier": tier,
                        "gsc_impressions": product.gsc_impressions,
                        "gsc_position": product.gsc_position,
                        "blocked_changes": blocked,
                    },
                )

        # === SAVE CURRENT STATE AS BACKUP (before publishing) ===
        current_shopify = shopify_service.get_product_full_details(product.shopify_id)
        if current_shopify:
            _save_content_history(
                db=db,
                product_id=product.id,
                status='previous',
                h1_title=current_shopify.get('title'),
                description_html=current_shopify.get('body_html'),
                meta_title=current_shopify.get('metafields', {}).get('metafields_global_title_tag'),
                meta_description=current_shopify.get('metafields', {}).get('metafields_global_description_tag'),
                url_handle=current_shopify.get('handle')
            )

        body_html = f"<h1>{content.get('h1_title', product.title)}</h1>\n"
        body_html += content.get('hook_html', '')
        
        if content.get('technical_specs'):
            body_html += "<ul>\n"
            for spec in content['technical_specs']:
                body_html += f"<li>{spec}</li>\n"
            body_html += "</ul>\n"
        
        body_html += f"<h3>Guía de Instalación</h3>\n{content.get('installation_guide', '')}\n"
        
        if content.get('faq_items'):
            body_html += "<h3>Preguntas Frecuentes</h3>\n<ul>\n"
            for faq in content['faq_items']:
                body_html += f"<li><strong>{faq['question']}</strong> {faq['answer']}</li>\n"
            body_html += "</ul>\n"
        
        update_data = {
            'title': content.get('h1_title', product.title),
            'body_html': body_html,
            'handle': content.get('url_handle', product.handle),
            'metafields_global_title_tag': content.get('meta_title'),
            'metafields_global_description_tag': content.get('meta_description')
        }
        
        result = shopify_service.update_product(product.shopify_id, update_data)
        
        # === SAVE NEW STATE AS PUBLISHED ===
        _save_content_history(
            db=db,
            product_id=product.id,
            status='published',
            h1_title=content.get('h1_title', product.title),
            description_html=body_html,
            meta_title=content.get('meta_title'),
            meta_description=content.get('meta_description'),
            url_handle=content.get('url_handle', product.handle)
        )
        
        product.seo_status = 'published'
        product.current_description_html = body_html
        product.needs_seo = False
        product.updated_at = None

        # Invalidate any cached deep-analysis result — the content the cache was
        # based on just changed. Without this, the next analysis call can return
        # recommendations about the OLD title/meta, causing hallucinations like
        # "Meta title contiene prefijo irrelevante 'Frmtoyta52'" for a product
        # whose meta was already rewritten.
        try:
            from app.models.product import AIAnalysisCache
            ai_cache = db.query(AIAnalysisCache).filter(
                AIAnalysisCache.product_id == product.id
            ).first()
            if ai_cache:
                ai_cache.is_stale = True
        except Exception as _cache_err:
            import logging
            logging.getLogger(__name__).warning(f"Failed to invalidate AI analysis cache for {product.id}: {_cache_err}")

        # === CALCULATE & PERSIST SEO SCORE ===
        product.seo_score = shopify_service.get_seo_score(body_html)
        
        db.commit()
        
        # === AUTO-CREATE ANALYTICS SNAPSHOT (captures "before" metrics at optimization time) ===
        snapshot_result = {"created": 0}
        try:
            from app.jobs.analytics_snapshot import create_daily_snapshot
            snapshot_result = create_daily_snapshot(db=db, product_ids=[str(product.id)])
        except Exception as snap_err:
            # Non-blocking: don't fail the publish if snapshot fails
            import logging
            logging.getLogger(__name__).warning(f"Snapshot creation failed for product {product.id}: {snap_err}")
        
        return {
            "message": "Product published successfully",
            "shopify_id": product.shopify_id,
            "history_saved": True,
            "snapshot_created": snapshot_result.get("created", 0) > 0,
            "performance_tier": tier,
            "forced": force,
        }

    except HTTPException:
        # Let guardrail 409s and 404s propagate unchanged
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ========== CONTENT VERSIONING ENDPOINTS ==========

@router.get("/products/{product_id}/history")
async def get_product_history(product_id: str, limit: int = 20, db: Session = Depends(get_db)):
    """
    Get content version history for a product.
    Returns list of previous versions ordered by date (newest first).
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    history = db.query(GenerationHistory)\
        .filter(GenerationHistory.product_id == str(product_id))\
        .order_by(GenerationHistory.generated_at.desc())\
        .limit(limit).all()
    
    return {
        "product_id": product_id,
        "product_title": product.title,
        "version_count": len(history),
        "versions": [
            {
                "id": h.id,
                "status": h.status,
                "h1_title": h.h1_title,
                "description_preview": (h.description_html or "")[:200] + "..." if h.description_html and len(h.description_html) > 200 else h.description_html,
                "meta_title": h.meta_title,
                # Shopify falls back to the H1 when no custom metafields_global_title_tag
                # is set. effective_meta_title is what Google actually sees in the SERP —
                # crucial for diffs so "empty meta" doesn't look like a void when the H1
                # was doing the job. meta_title_inherited=True means the empty custom
                # metafield was inheriting from the product title.
                "effective_meta_title": h.meta_title or h.h1_title,
                "meta_title_inherited": not h.meta_title and bool(h.h1_title),
                "meta_description": h.meta_description,
                "url_handle": h.url_handle,
                "libraries_used": h.libraries_used or [],
                "llm_used": h.llm_used,
                "generated_at": h.generated_at.isoformat() if h.generated_at else None
            }
            for h in history
        ]
    }


@router.get("/products/{product_id}/history/{history_id}")
async def get_history_detail(product_id: str, history_id: str, db: Session = Depends(get_db)):
    """Get full details of a specific history version."""
    history = db.query(GenerationHistory)\
        .filter(GenerationHistory.id == history_id)\
        .filter(GenerationHistory.product_id == str(product_id))\
        .first()
    
    if not history:
        raise HTTPException(status_code=404, detail="History version not found")
    
    return {
        "id": history.id,
        "product_id": history.product_id,
        "status": history.status,
        "h1_title": history.h1_title,
        "description_html": history.description_html,
        "meta_title": history.meta_title,
        "effective_meta_title": history.meta_title or history.h1_title,
        "meta_title_inherited": not history.meta_title and bool(history.h1_title),
        "meta_description": history.meta_description,
        "url_handle": history.url_handle,
        "short_description": history.short_description,
        "libraries_used": history.libraries_used or [],
        "llm_used": history.llm_used,
        "generated_at": history.generated_at.isoformat() if history.generated_at else None
    }


@router.post("/products/{product_id}/rollback/{history_id}")
async def rollback_to_version(product_id: str, history_id: str, db: Session = Depends(get_db)):
    """
    Rollback product content to a previous version.
    Restores the content from the specified history record to Shopify.
    """
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Get the history version to restore
        history = db.query(GenerationHistory)\
            .filter(GenerationHistory.id == history_id)\
            .filter(GenerationHistory.product_id == str(product_id))\
            .first()
        
        if not history:
            raise HTTPException(status_code=404, detail="History version not found")
        
        # === SAVE CURRENT STATE BEFORE ROLLBACK ===
        current_shopify = shopify_service.get_product_full_details(product.shopify_id)
        if current_shopify:
            _save_content_history(
                db=db,
                product_id=product.id,
                status='previous',
                h1_title=current_shopify.get('title'),
                description_html=current_shopify.get('body_html'),
                meta_title=current_shopify.get('metafields', {}).get('metafields_global_title_tag'),
                meta_description=current_shopify.get('metafields', {}).get('metafields_global_description_tag'),
                url_handle=current_shopify.get('handle')
            )
        
        # Prepare update data from history
        update_data = {
            'title': history.h1_title,
            'body_html': history.description_html,
            'handle': history.url_handle,
            'metafields_global_title_tag': history.meta_title,
            'metafields_global_description_tag': history.meta_description
        }
        # Remove None values
        update_data = {k: v for k, v in update_data.items() if v is not None}
        
        # Update Shopify with the old version
        result = shopify_service.update_product(product.shopify_id, update_data)
        
        # === SAVE ROLLBACK AS NEW PUBLISHED VERSION ===
        _save_content_history(
            db=db,
            product_id=product.id,
            status='rollback',
            h1_title=history.h1_title,
            description_html=history.description_html,
            meta_title=history.meta_title,
            meta_description=history.meta_description,
            url_handle=history.url_handle,
            short_description=history.short_description
        )
        
        # Update local database
        if history.h1_title:
            product.title = history.h1_title
        if history.description_html:
            product.current_description_html = history.description_html
        if history.url_handle:
            product.handle = history.url_handle
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Rolled back to version from {history.generated_at}",
            "rollback_from_id": history_id,
            "shopify_id": product.shopify_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

