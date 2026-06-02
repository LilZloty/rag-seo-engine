"""
Collection Optimizer Service
Main service for analyzing, generating, and deploying collection content
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from app.core.logging import get_logger
from app.core.config import settings, apply_store_profile
from app.models.collection_optimizer_models import (
    CollectionOptimizer, 
    CollectionSearchQuery, 
    CollectionOptimizationHistory
)
from app.services.google_api_service import GoogleApiService
from app.services.llm_service import LLMService
from app.services.shopify_service import ShopifyService
from app.services.llm_providers import LLMProviderFactory
from app.models.aeo_models import CacheEntry
from app.models.collection_intelligence_models import CollectionContentDraft
from app.services.collection_cannibalization_guard import CollectionCannibalizationGuard

logger = get_logger(__name__)


class CollectionOptimizerService:
    """
    Main service for collection optimization workflow
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.google_service = GoogleApiService()
        self.llm_service = LLMService()
        self.shopify_service = ShopifyService()
    
    def _get_active_llm_provider(self) -> str:
        """Get the currently active LLM provider from settings"""
        try:
            cached = CacheEntry.get(self.db, "app_settings:llm_provider")
            if cached and cached.data:
                return cached.data.get("provider", "grok")
        except Exception as e:
            logger.warning(f"Failed to get active provider from cache: {e}")
        return "grok"  # Default fallback
    
    # =========================================================================
    # PHASE 1: DISCOVER - Sync collections from Shopify
    # =========================================================================
    
    async def sync_collections(self) -> Dict:
        """
        Sync all Shopify collections to the optimizer database
        """
        logger.info("Starting collection sync from Shopify...")
        
        try:
            # Fetch collections from Shopify (not async)
            collections = self.shopify_service.get_collections()
            
            synced_count = 0
            updated_count = 0
            
            for collection in collections:
                # Check if collection already exists
                existing = self.db.query(CollectionOptimizer).filter(
                    CollectionOptimizer.shopify_collection_id == collection['id']
                ).first()
                
                if existing:
                    # Update existing
                    existing.collection_title = collection['title']
                    existing.collection_handle = collection['handle']
                    existing.collection_url = f"{settings.store_url}/collections/{collection['handle']}"
                    existing.updated_at = datetime.utcnow()
                    updated_count += 1
                else:
                    # Create new
                    new_collection = CollectionOptimizer(
                        shopify_collection_id=collection['id'],
                        collection_handle=collection['handle'],
                        collection_title=collection['title'],
                        collection_url=f"{settings.store_url}/collections/{collection['handle']}",
                        category=self._categorize_collection(collection['title']),
                        optimization_status="pending"
                    )
                    self.db.add(new_collection)
                    synced_count += 1
            
            self.db.commit()
            
            # Log history
            self._log_history(
                collection_id=None,
                action_type="sync",
                action_status="success",
                action_details={"synced": synced_count, "updated": updated_count}
            )
            
            logger.info(f"Collection sync complete: {synced_count} new, {updated_count} updated")
            
            return {
                "status": "success",
                "synced": synced_count,
                "updated": updated_count,
                "total": synced_count + updated_count
            }
            
        except Exception as e:
            logger.error(f"Collection sync failed: {e}")
            self._log_history(
                collection_id=None,
                action_type="sync",
                action_status="failed",
                action_details={"error": str(e)}
            )
            self.db.commit()
            raise
    
    def _categorize_collection(self, title: str) -> str:
        """
        Auto-categorize collection based on title
        """
        title_lower = title.lower()
        
        if any(word in title_lower for word in ['cremallera', 'direccion', 'bomba']):
            return 'direccion'
        elif any(word in title_lower for word in ['transmision', '4l60e', 'jf011e', 'cvt']):
            return 'transmission'
        elif any(word in title_lower for word in ['freno', 'brake']):
            return 'frenos'
        elif any(word in title_lower for word in ['motor', 'engine']):
            return 'motor'
        else:
            return 'general'
    
    # =========================================================================
    # PHASE 2: ANALYZE - Fetch and analyze Search Console data
    # =========================================================================
    
    async def analyze_collection_performance(self, collection_id: int) -> Dict:
        """
        Analyze Search Console data for a specific collection
        """
        collection = self.db.query(CollectionOptimizer).get(collection_id)
        if not collection:
            raise ValueError(f"Collection {collection_id} not found")
        
        logger.info(f"Analyzing performance for: {collection.collection_title}")
        
        try:
            # Get Search Console data
            queries = self.google_service.get_search_console_data(days=30)
            
            # Filter queries relevant to this collection
            relevant_queries = self._filter_relevant_queries(
                queries, 
                collection.collection_title,
                collection.category
            )
            
            # Calculate priority score
            priority_score = self._calculate_priority_score(relevant_queries)
            
            # Store queries
            for query_data in relevant_queries:
                existing_query = self.db.query(CollectionSearchQuery).filter(
                    CollectionSearchQuery.collection_id == collection_id,
                    CollectionSearchQuery.query == query_data['query']
                ).first()
                
                if existing_query:
                    # Update
                    existing_query.clicks = query_data['clicks']
                    existing_query.impressions = query_data['impressions']
                    existing_query.ctr = query_data['ctr']
                    existing_query.position = query_data['position']
                    existing_query.priority_score = query_data.get('priority_score', 0)
                else:
                    # Create new
                    new_query = CollectionSearchQuery(
                        collection_id=collection_id,
                        query=query_data['query'],
                        clicks=query_data['clicks'],
                        impressions=query_data['impressions'],
                        ctr=query_data['ctr'],
                        position=query_data['position'],
                        query_type=query_data.get('type', 'unknown'),
                        intent=query_data.get('intent', 'unknown'),
                        priority_score=query_data.get('priority_score', 0)
                    )
                    self.db.add(new_query)
            
            # Update collection with baseline metrics
            if relevant_queries:
                total_impressions = sum(q['impressions'] for q in relevant_queries)
                total_clicks = sum(q['clicks'] for q in relevant_queries)
                avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
                avg_position = sum(q['position'] for q in relevant_queries) / len(relevant_queries)
                
                # Store baseline if not set
                if not collection.baseline_date:
                    collection.baseline_impressions = total_impressions
                    collection.baseline_clicks = total_clicks
                    collection.baseline_ctr = avg_ctr
                    collection.baseline_position = avg_position
                    collection.baseline_date = datetime.utcnow()
                
                # Update current metrics
                collection.current_impressions = total_impressions
                collection.current_clicks = total_clicks
                collection.current_ctr = avg_ctr
                collection.current_position = avg_position
                collection.optimization_priority = priority_score
                collection.optimization_status = "analyzed"
                collection.last_analytics_sync = datetime.utcnow()
            
            self.db.commit()
            
            # Log history
            self._log_history(
                collection_id=collection_id,
                action_type="analyze",
                action_status="success",
                action_details={
                    "queries_found": len(relevant_queries),
                    "priority_score": priority_score
                }
            )
            
            return {
                "status": "success",
                "collection": collection.collection_title,
                "queries_analyzed": len(relevant_queries),
                "priority_score": priority_score,
                "top_queries": sorted(relevant_queries, key=lambda x: x['impressions'], reverse=True)[:5]
            }
            
        except Exception as e:
            logger.error(f"Analysis failed for {collection.collection_title}: {e}")
            self._log_history(
                collection_id=collection_id,
                action_type="analyze",
                action_status="failed",
                action_details={"error": str(e)}
            )
            self.db.commit()
            raise
    
    def _filter_relevant_queries(self, queries: List[Dict], collection_title: str, category: str) -> List[Dict]:
        """
        Filter Search Console queries relevant to a collection
        """
        relevant = []
        
        # Keywords to match
        collection_keywords = collection_title.lower().split()
        category_keywords = {
            'direccion': ['cremallera', 'direccion', 'dirección', 'bomba', 'hidraulica', 'hidráulica'],
            'transmission': ['transmision', 'transmisión', 'cvt', '4l60e', 'automatica', 'caja'],
            'frenos': ['freno', 'brake', 'pastilla', 'disco'],
            'motor': ['motor', 'engine', 'pistón', 'biela']
        }.get(category, [])
        
        all_keywords = collection_keywords + category_keywords
        
        for query in queries:
            query_lower = query['query'].lower()
            
            # Check if query matches any keyword
            if any(keyword in query_lower for keyword in all_keywords):
                # Classify query type
                query_type = self._classify_query_type(query_lower)
                intent = self._classify_intent(query_lower)
                
                # Calculate priority score
                priority_score = self._calculate_query_priority(
                    query['impressions'],
                    query['ctr'],
                    query['position'],
                    query_type
                )
                
                query_data = query.copy()
                query_data['type'] = query_type
                query_data['intent'] = intent
                query_data['priority_score'] = priority_score
                
                relevant.append(query_data)
        
        return sorted(relevant, key=lambda x: x['priority_score'], reverse=True)
    
    def _classify_query_type(self, query: str) -> str:
        """Classify query as question, product, brand, or comparison"""
        question_words = ['que', 'qué', 'como', 'cómo', 'donde', 'dónde', 'cual', 'cuál', 'porque', 'por qué']
        comparison_words = ['vs', 'mejor', 'comparacion', 'comparación', 'diferencia', 'precio']
        
        if any(word in query for word in question_words):
            return 'question'
        elif any(word in query for word in comparison_words):
            return 'comparison'
        elif 'example-store' in query or 'example store' in query:
            return 'brand'
        else:
            return 'product'
    
    def _classify_intent(self, query: str) -> str:
        """Classify search intent"""
        transactional = ['comprar', 'precio', 'venta', 'tienda', 'donde comprar', 'cotizar']
        informational = ['que es', 'como', 'sintomas', 'falla', 'codigo']
        
        if any(word in query for word in transactional):
            return 'transactional'
        elif any(word in query for word in informational):
            return 'informational'
        else:
            return 'navigational'
    
    def _calculate_query_priority(self, impressions: int, ctr: float, position: float, query_type: str) -> int:
        """
        Calculate priority score (1-10) based on opportunity
        """
        score = 0
        
        # High impressions = high potential
        if impressions > 10000:
            score += 4
        elif impressions > 5000:
            score += 3
        elif impressions > 1000:
            score += 2
        elif impressions > 500:
            score += 1
        
        # Low CTR = optimization opportunity
        if ctr < 0.01:  # Less than 1%
            score += 3
        elif ctr < 0.03:  # Less than 3%
            score += 2
        
        # Position on page 1 but not top = can improve
        if 3 <= position <= 10:
            score += 2
        
        # Question queries are gold for AEO
        if query_type == 'question':
            score += 1
        
        return min(score, 10)
    
    def _calculate_priority_score(self, queries: List[Dict]) -> int:
        """Calculate overall collection priority"""
        if not queries:
            return 0
        
        # Average of top 5 query priority scores
        top_queries = sorted(queries, key=lambda x: x.get('priority_score', 0), reverse=True)[:5]
        avg_score = sum(q.get('priority_score', 0) for q in top_queries) / len(top_queries)
        
        return round(avg_score)
    
    # =========================================================================
    # GA4 INTEGRATION - Fetch and analyze GA4 data
    # =========================================================================
    
    async def analyze_ga4_performance(self, collection_id: int) -> Dict:
        """
        Analyze GA4 data for a specific collection
        Fetches engagement metrics, conversions, and AI referral traffic
        """
        collection = self.db.query(CollectionOptimizer).get(collection_id)
        if not collection:
            raise ValueError(f"Collection {collection_id} not found")
        
        logger.info(f"Analyzing GA4 performance for: {collection.collection_title}")
        
        try:
            # Get GA4 engagement data for all pages
            ga4_data = self.google_service.get_ga4_engagement_data(days=30)
            
            # Match collection to GA4 page path
            collection_path = f"/collections/{collection.collection_handle}"
            
            # Find matching page data
            page_data = None
            for item in ga4_data:
                if collection_path in item['page_path'] or collection.collection_handle in item['page_path']:
                    page_data = item
                    break
            
            # Get AI referral traffic for GEO tracking
            ai_referrals = self.google_service.get_ai_referral_traffic(days=30)
            ai_sessions = sum(item['sessions'] for item in ai_referrals if collection_path in item.get('page_path', ''))
            
            if page_data:
                # Calculate conversion rate
                conversion_rate = (page_data['conversions'] / page_data['sessions'] * 100) if page_data['sessions'] > 0 else 0
                
                # Store baseline GA4 metrics if not set
                if not collection.baseline_ga4_date:
                    collection.baseline_ga4_sessions = page_data['sessions']
                    collection.baseline_ga4_conversions = page_data['conversions']
                    collection.baseline_ga4_revenue = 0.0  # Revenue requires e-commerce tracking
                    collection.baseline_ga4_date = datetime.utcnow()
                
                # Update current GA4 metrics
                collection.ga4_sessions = page_data['sessions']
                collection.ga4_bounce_rate = 0.0  # Would need separate bounce rate query
                collection.ga4_avg_engagement_time = page_data['avg_duration']
                collection.ga4_conversions = page_data['conversions']
                collection.ga4_conversion_rate = conversion_rate
                collection.ga4_ai_referral_sessions = ai_sessions
                collection.last_ga4_sync = datetime.utcnow()
                
                self.db.commit()
                
                # Log history
                self._log_history(
                    collection_id=collection_id,
                    action_type="ga4_analyze",
                    action_status="success",
                    action_details={
                        "sessions": page_data['sessions'],
                        "conversions": page_data['conversions'],
                        "conversion_rate": conversion_rate,
                        "ai_sessions": ai_sessions
                    }
                )
                
                return {
                    "status": "success",
                    "collection": collection.collection_title,
                    "ga4_data": {
                        "sessions": page_data['sessions'],
                        "active_users": page_data['active_users'],
                        "avg_engagement_time": page_data['avg_duration'],
                        "conversions": page_data['conversions'],
                        "conversion_rate": conversion_rate,
                        "ai_referral_sessions": ai_sessions
                    }
                }
            else:
                logger.warning(f"No GA4 data found for collection: {collection.collection_title}")
                return {
                    "status": "warning",
                    "collection": collection.collection_title,
                    "message": "No GA4 data found for this collection path",
                    "path_searched": collection_path
                }
                
        except Exception as e:
            logger.error(f"GA4 analysis failed for {collection.collection_title}: {e}")
            self._log_history(
                collection_id=collection_id,
                action_type="ga4_analyze",
                action_status="failed",
                action_details={"error": str(e)}
            )
            self.db.commit()
            raise
    
    async def analyze_all_ga4(self) -> Dict:
        """
        Analyze GA4 data for all analyzed collections
        """
        collections = self.db.query(CollectionOptimizer).filter(
            CollectionOptimizer.optimization_status.in_(["analyzed", "ready", "published"])
        ).all()
        
        results = []
        for collection in collections:
            try:
                result = await self.analyze_ga4_performance(collection.id)
                results.append({"id": collection.id, "status": "success", "data": result})
            except Exception as e:
                results.append({"id": collection.id, "status": "error", "error": str(e)})
        
        return {
            "status": "complete",
            "analyzed": len(results),
            "results": results
        }
    
    async def sync_shopify_attribution(self, days: int = 30) -> Dict:
        """
        Sync Shopify order revenue attribution to all collections.
        Fetches orders once and distributes attribution by collection handle.
        """
        logger.info(f"[ShopifySync] Starting attribution sync for last {days} days...")

        attribution_map = self.shopify_service.get_collection_revenue_attribution(days)
        collections = self.db.query(CollectionOptimizer).all()
        updated = 0

        for collection in collections:
            handle = (collection.collection_handle or '').lower().strip()
            data = attribution_map.get(handle)

            if data:
                collection.shopify_attributed_revenue = round(data['attributed_revenue'], 2)
                collection.shopify_attributed_orders = data['attributed_orders']
                collection.shopify_llm_revenue = round(data['llm_revenue'], 2)
                collection.shopify_llm_orders = data['llm_orders']
                updated += 1
            else:
                collection.shopify_attributed_revenue = 0.0
                collection.shopify_attributed_orders = 0
                collection.shopify_llm_revenue = 0.0
                collection.shopify_llm_orders = 0

            collection.last_shopify_sync = datetime.utcnow()

        self.db.commit()

        top_10 = sorted(attribution_map.items(), key=lambda x: x[1]['attributed_revenue'], reverse=True)[:10]
        logger.info(f"[ShopifySync] Done. {len(attribution_map)} collections with revenue, {updated} updated.")

        return {
            "status": "success",
            "days": days,
            "collections_with_revenue": len(attribution_map),
            "total_updated": len(collections),
            "top_collections": [
                {"handle": h, **d} for h, d in top_10
            ]
        }

    async def run_dataforseo_for_collection(self, collection_id: int) -> Dict:
        """
        Fetch DataForSEO SERP and keyword volume data for a single collection.
        Uses the collection's top GSC queries as keywords.
        Requires the collection to have been analyzed first (has search queries).
        """
        from app.services.dataforseo_service import DataForSEOService

        collection = self.db.query(CollectionOptimizer).filter(
            CollectionOptimizer.id == collection_id
        ).first()
        if not collection:
            raise ValueError(f"Collection {collection_id} not found")

        top_queries = self.db.query(CollectionSearchQuery).filter(
            CollectionSearchQuery.collection_id == collection_id
        ).order_by(CollectionSearchQuery.impressions.desc()).limit(5).all()

        if not top_queries:
            return {
                "status": "skipped",
                "reason": "No GSC queries found — run Analyze first",
                "collection": collection.collection_title
            }

        gsc_queries = [
            {"query": q.query, "impressions": q.impressions, "clicks": q.clicks}
            for q in top_queries
        ]

        dfs_service = DataForSEOService()
        if not dfs_service.is_configured():
            return {
                "status": "skipped",
                "reason": "DataForSEO credentials not configured",
                "collection": collection.collection_title
            }

        serp_data = await dfs_service.get_serp_data_for_product(
            product_title=collection.collection_title,
            gsc_queries=gsc_queries,
            db=self.db,
            max_keywords=3
        )

        keyword_strings = [q["query"] for q in gsc_queries[:5]]
        volumes = await dfs_service.fetch_keyword_volumes(keyword_strings, self.db)

        # Determine primary keyword by highest search volume
        primary_keyword = None
        primary_volume = 0
        primary_competition = "UNKNOWN"
        primary_cpc = 0.0

        for kw, vol_data in (volumes or {}).items():
            vol = int(vol_data.get("volume") or 0)
            if vol > primary_volume:
                primary_volume = vol
                primary_keyword = kw
                primary_competition = str(vol_data.get("competition") or "UNKNOWN")
                primary_cpc = float(vol_data.get("cpc") or 0.0)

        if not primary_keyword and top_queries:
            primary_keyword = top_queries[0].query

        # Extract top competitor (first non-example-store organic result)
        top_competitor = None
        all_organic = serp_data.get("all_organic") or []
        for org in all_organic:
            domain = (org.get("domain") or "").lower()
            if domain and "example-store" not in domain:
                top_competitor = domain
                break

        collection.dataforseo_primary_keyword = primary_keyword
        collection.dataforseo_volume = primary_volume
        collection.dataforseo_competition = primary_competition
        collection.dataforseo_cpc = primary_cpc
        collection.dataforseo_top_competitor = top_competitor
        collection.dataforseo_serp_features = serp_data.get("serp_features_detected") or []
        collection.dataforseo_people_also_ask = (serp_data.get("all_paa") or [])[:8]
        # Store top 10 organic results permanently (never expires, survives cache TTL)
        collection.dataforseo_organic_results = (serp_data.get("all_organic") or [])[:10]
        collection.dataforseo_last_sync = datetime.utcnow()

        self.db.commit()

        return {
            "status": "success",
            "collection": collection.collection_title,
            "primary_keyword": primary_keyword,
            "volume": primary_volume,
            "competition": primary_competition,
            "cpc": primary_cpc,
            "top_competitor": top_competitor,
            "serp_features": collection.dataforseo_serp_features,
            "paa_count": len(collection.dataforseo_people_also_ask or [])
        }

    async def run_dataforseo_for_all_collections(self) -> Dict:
        """
        Fetch DataForSEO data for all analyzed/ready/published collections.
        Skips collections synced within the last 30 days (respects DataForSEO cache TTL).
        """
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        collections = self.db.query(CollectionOptimizer).filter(
            CollectionOptimizer.optimization_status.in_(["analyzed", "ready", "published"])
        ).all()

        results = []
        skipped = 0

        for collection in collections:
            # Skip if already synced within the cache window (30 days)
            if collection.dataforseo_last_sync and collection.dataforseo_last_sync > thirty_days_ago:
                skipped += 1
                continue
            try:
                result = await self.run_dataforseo_for_collection(collection.id)
                results.append({"id": collection.id, "status": result.get("status"), "data": result})
            except Exception as e:
                results.append({"id": collection.id, "status": "error", "error": str(e)})

        return {
            "status": "complete",
            "processed": len(results),
            "skipped_cached": skipped,
            "results": results
        }

    def _calculate_revenue_priority_score(self, collection: CollectionOptimizer) -> float:
        """
        Calculate priority score based on revenue potential
        Combines Search Console data with GA4 conversion data
        """
        score = 0.0
        
        # Base score from search visibility
        if collection.current_impressions > 100000:
            score += 3.0
        elif collection.current_impressions > 50000:
            score += 2.0
        elif collection.current_impressions > 10000:
            score += 1.0
        
        # CTR opportunity (low CTR = high potential)
        if collection.current_ctr < 0.5:
            score += 3.0
        elif collection.current_ctr < 1.0:
            score += 2.0
        elif collection.current_ctr < 2.0:
            score += 1.0
        
        # Conversion rate factor (if GA4 data available)
        if collection.ga4_sessions > 0:
            conversion_factor = collection.ga4_conversion_rate / 100  # Normalize
            score += conversion_factor * 2.0  # Up to 2 points for high conversion rate
            
            # High traffic but low conversions = opportunity
            if collection.ga4_sessions > 1000 and collection.ga4_conversion_rate < 1.0:
                score += 2.0
        
        # AI referral bonus (GEO optimization working)
        if collection.ga4_ai_referral_sessions > 0:
            score += 1.0
        
        return min(score, 10.0)
    
    # =========================================================================
    # PHASE 3: GENERATE - Create optimized content
    # =========================================================================
    
    async def generate_collection_content(self, collection_id: int, skip_cannibalization_check: bool = False) -> Dict:
        """
        Generate optimized content for a collection using AI.

        Includes cannibalization guard: checks keyword conflicts with blogs/products
        before generating content. Creates a CollectionContentDraft for review.
        """
        import uuid

        collection = self.db.query(CollectionOptimizer).get(collection_id)
        if not collection:
            raise ValueError(f"Collection {collection_id} not found")

        logger.info(f"Generating content for: {collection.collection_title}")

        try:
            # Step 1: Run cannibalization check
            cannibal_result = None
            if not skip_cannibalization_check:
                guard = CollectionCannibalizationGuard(self.db)
                cannibal_result = await guard.check_collection(collection_id)

                if cannibal_result.status == "blocked" and not cannibal_result.can_generate:
                    logger.warning(
                        f"Content generation BLOCKED for '{collection.collection_title}' "
                        f"— risk score {cannibal_result.risk_score}%, "
                        f"{len(cannibal_result.blocked_keywords)} blocked keywords"
                    )
                    return {
                        "status": "blocked",
                        "collection": collection.collection_title,
                        "reason": "cannibalization_risk",
                        "risk_score": cannibal_result.risk_score,
                        "blocked_keywords": [k.keyword for k in cannibal_result.blocked_keywords],
                        "safe_keywords": [k.keyword for k in cannibal_result.safe_keywords],
                        "message": (
                            f"Generación bloqueada: {len(cannibal_result.blocked_keywords)} keywords "
                            f"ya rankean en blogs/productos. Riesgo: {cannibal_result.risk_score}%"
                        )
                    }

            # Step 2: Get top queries for this collection
            top_queries = self.db.query(CollectionSearchQuery).filter(
                CollectionSearchQuery.collection_id == collection_id
            ).order_by(CollectionSearchQuery.priority_score.desc()).limit(10).all()

            if not top_queries:
                raise ValueError("No queries found for content generation")

            # Step 3: Generate educational content (with cannibalization guidance)
            educational_content = await self._generate_educational_content(
                collection.collection_title,
                collection.category,
                top_queries,
                collection=collection,
                cannibal_result=cannibal_result
            )

            # Step 4: Generate FAQ section (only from safe keywords)
            faq_content = await self._generate_faq_section(
                collection.collection_title,
                collection.category,
                top_queries,
                cannibal_result=cannibal_result
            )

            # Step 5: Generate schema markup
            schema_markup = self._generate_faq_schema(faq_content)

            # Step 6: Create content draft
            existing_drafts = self.db.query(CollectionContentDraft).filter(
                CollectionContentDraft.collection_id == collection_id
            ).count()

            draft = CollectionContentDraft(
                id=str(uuid.uuid4()),
                collection_id=collection_id,
                version=existing_drafts + 1,
                draft_status='draft',
                educational_content=educational_content,
                faq_content=faq_content,
                schema_markup=schema_markup,
                cannibalization_check=cannibal_result.model_dump() if cannibal_result else None,
                safe_keywords_used=[k.keyword for k in cannibal_result.safe_keywords] if cannibal_result else None,
                blocked_keywords_avoided=[k.keyword for k in cannibal_result.blocked_keywords] if cannibal_result else None,
                generation_provider=self._get_active_llm_provider()
            )
            self.db.add(draft)

            # Step 7: Also update collection (backward compatible)
            collection.generated_content = educational_content
            collection.generated_faq = faq_content
            collection.generated_schema = schema_markup
            collection.content_generated_at = datetime.utcnow()
            collection.optimization_status = "ready"

            self.db.commit()

            # Log history
            self._log_history(
                collection_id=collection_id,
                action_type="generate",
                action_status="success",
                action_details={
                    "content_length": len(educational_content),
                    "faq_items": len(faq_content),
                    "draft_id": draft.id,
                    "draft_version": draft.version,
                    "cannibalization_status": cannibal_result.status if cannibal_result else "skipped",
                    "risk_score": cannibal_result.risk_score if cannibal_result else 0,
                    "safe_keywords": len(cannibal_result.safe_keywords) if cannibal_result else 0,
                    "blocked_keywords": len(cannibal_result.blocked_keywords) if cannibal_result else 0
                }
            )

            return {
                "status": "success",
                "collection": collection.collection_title,
                "educational_content_preview": educational_content[:500] + "...",
                "faq_count": len(faq_content),
                "schema_generated": bool(schema_markup),
                "draft_id": draft.id,
                "draft_version": draft.version,
                "cannibalization": {
                    "status": cannibal_result.status if cannibal_result else "skipped",
                    "risk_score": cannibal_result.risk_score if cannibal_result else 0,
                    "safe_keywords": len(cannibal_result.safe_keywords) if cannibal_result else 0,
                    "blocked_keywords": len(cannibal_result.blocked_keywords) if cannibal_result else 0,
                    "warning_keywords": len(cannibal_result.warning_keywords) if cannibal_result else 0
                }
            }

        except Exception as e:
            logger.error(f"Content generation failed: {e}")
            self._log_history(
                collection_id=collection_id,
                action_type="generate",
                action_status="failed",
                action_details={"error": str(e)}
            )
            self.db.commit()
            raise
    
    async def _generate_educational_content(
        self,
        title: str,
        category: str,
        queries: List,
        collection: Optional[CollectionOptimizer] = None,
        cannibal_result=None
    ) -> str:
        """
        Generate optimized collection content using LLM.

        Enhanced prompt with:
        - Cannibalization-safe keyword guidance
        - Transactional intent framing
        - DataForSEO competitor context
        - PAA questions integration
        - Character count requirements
        """
        # Extract query types
        question_queries = [q for q in queries if q.query_type == 'question'][:5]
        transactional_queries = [q for q in queries if q.intent == 'transactional'][:5]
        all_query_texts = [q.query for q in queries[:10]]

        # Build keyword guidance from cannibalization check
        keyword_section = ""
        if cannibal_result:
            keyword_section = cannibal_result.generation_guidance
        else:
            keyword_section = f"Keywords principales: {', '.join(all_query_texts[:8])}"

        # DataForSEO context
        dataforseo_section = ""
        if collection:
            if collection.dataforseo_primary_keyword:
                dataforseo_section += f"Keyword principal (DataForSEO): {collection.dataforseo_primary_keyword}\n"
                dataforseo_section += f"Volumen mensual: {collection.dataforseo_volume or 'N/A'}\n"
                dataforseo_section += f"Competencia: {collection.dataforseo_competition or 'N/A'}\n"
            if collection.dataforseo_top_competitor:
                dataforseo_section += f"Competidor principal: {collection.dataforseo_top_competitor}\n"
            if collection.dataforseo_serp_features:
                features = collection.dataforseo_serp_features
                if isinstance(features, list):
                    dataforseo_section += f"SERP features activos: {', '.join(features[:5])}\n"

            # PAA questions from DataForSEO
            paa = collection.dataforseo_people_also_ask or []
            if paa:
                paa_questions = [p.get('question', '') for p in paa[:5] if p.get('question')]
                if paa_questions:
                    dataforseo_section += f"\nPreguntas PAA (People Also Ask):\n"
                    dataforseo_section += "\n".join([f"  - {q}" for q in paa_questions])

        # Build the enhanced prompt
        prompt = f"""Genera contenido optimizado para una PÁGINA DE COLECCIÓN (categoría) de e-commerce de autopartes.

=== DATOS DE LA COLECCIÓN ===
Título: {title}
Categoría: {category}
{f"Productos en la colección: disponibles en Example Store" if collection else ""}

=== DATOS DE BÚSQUEDA ===
{dataforseo_section}

Preguntas de los usuarios:
{chr(10).join([f"- {q.query} ({q.impressions} impresiones, posición #{q.position:.1f})" for q in question_queries])}

Queries transaccionales:
{chr(10).join([f"- {q.query} ({q.clicks} clicks)" for q in transactional_queries])}

=== GUÍA DE KEYWORDS ===
{keyword_section}

=== ESTRUCTURA REQUERIDA ===
1. H1: Título principal con keyword transaccional (50-60 caracteres MAX)
2. Meta descripción: 150-160 caracteres, incluir CTA ("Compra en Example Store")
3. Introducción (2-3 oraciones): Qué productos incluye esta colección y por qué comprar aquí
4. Beneficios clave de comprar en Example Store (lista de 3-5 items):
   - Envío a todo México
   - Garantía en refacciones
   - Precios competitivos
   - Asesoría técnica
5. Breve sección técnica (1 párrafo): Cuándo necesitas estos productos (síntomas comunes)
6. CTA final: Invitación a explorar los productos de la colección

=== REGLAS CRÍTICAS ===
- INTENCIÓN TRANSACCIONAL: Esta es una página de COMPRA, no un artículo educativo
- Español mexicano natural, tono profesional
- Longitud TOTAL: 250-400 palabras (no más — es una colección, no un blog)
- Menciona "Example Store" naturalmente 2-3 veces
- NO escribas contenido informacional/educativo extenso (eso lo hacen los blogs)
- NO dupliques contenido de artículos del blog
- SÍ incluye: precios, disponibilidad, envío, garantía, marcas disponibles
- Usa las keywords SEGURAS proporcionadas arriba
- EVITA las keywords BLOQUEADAS proporcionadas arriba
- Si mencionas información técnica, sé breve y sugiere "consulta nuestro blog para más detalles"
- Formato HTML con tags semánticos (<h1>, <h2>, <p>, <ul>, <li>)
"""

        # Use active LLM provider
        active_provider = self._get_active_llm_provider()
        provider = LLMProviderFactory.create(active_provider)
        result = await provider.generate(
            system_prompt=(
                "Eres un experto en SEO para e-commerce de autopartes en México. "
                "Generas contenido TRANSACCIONAL para páginas de colección (categoría), "
                "no contenido informacional (eso va en blogs). Tu objetivo es maximizar "
                "conversiones sin canibalizar rankings existentes de blogs y productos."
            ),
            user_prompt=apply_store_profile(prompt)
        )

        return result.get('content', '')
    
    async def _generate_faq_section(self, title: str, category: str, queries: List, cannibal_result=None) -> List[Dict]:
        """
        Generate FAQ items based on search queries.
        Filters out blocked keywords to avoid cannibalization.
        """
        # Get question and comparison queries
        faq_queries = [q for q in queries if q.query_type in ['question', 'comparison']][:8]

        # Filter out blocked keywords if cannibalization check was run
        if cannibal_result:
            blocked_kws = {k.keyword.lower() for k in cannibal_result.blocked_keywords}
            faq_queries = [q for q in faq_queries if q.query.lower() not in blocked_kws]

        faqs = []

        for query in faq_queries:
            prompt = f"""Genera una respuesta para una pregunta frecuente en una página de COLECCIÓN (categoría de productos).

Pregunta: {query.query}
Contexto: Página de colección "{title}" en Example Store (tienda de autopartes en México)

Requisitos:
- Respuesta de 2-4 oraciones
- Enfoque TRANSACCIONAL: menciona Example Store como lugar donde comprar
- Incluye un beneficio específico (precio competitivo, garantía, envío a todo México)
- NO escribas una guía técnica extensa (eso va en el blog)
- Si la pregunta es técnica, da una respuesta breve y sugiere "visita nuestro blog para una guía completa"
- Tono: Profesional, directo y útil
"""

            active_provider = self._get_active_llm_provider()
            provider = LLMProviderFactory.create(active_provider)
            result = await provider.generate(
                system_prompt="Eres un experto en atención al cliente para autopartes. Respondes de forma transaccional, no educativa.",
                user_prompt=apply_store_profile(prompt)
            )

            answer = result.get('content', '').strip()

            if answer:
                faqs.append({
                    'question': query.query.capitalize() + '?',
                    'answer': answer,
                    'source_query': query.query,
                    'clicks': query.clicks,
                    'impressions': query.impressions
                })

        return faqs
    
    def _generate_faq_schema(self, faqs: List[Dict]) -> str:
        """
        Generate JSON-LD FAQ schema markup
        """
        import json
        
        schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": []
        }
        
        for faq in faqs:
            schema["mainEntity"].append({
                "@type": "Question",
                "name": faq['question'],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": faq['answer']
                }
            })
        
        return json.dumps(schema, indent=2, ensure_ascii=False)
    
    # =========================================================================
    # PHASE 4: DEPLOY - Push content to Shopify metafields
    # =========================================================================
    
    async def deploy_to_shopify(self, collection_id: int, dry_run: bool = False) -> Dict:
        """
        Deploy generated content to Shopify collection metafields
        """
        collection = self.db.query(CollectionOptimizer).get(collection_id)
        if not collection:
            raise ValueError(f"Collection {collection_id} not found")
        
        if collection.optimization_status != "ready":
            raise ValueError(f"Collection not ready for deployment. Status: {collection.optimization_status}")
        
        logger.info(f"Deploying content for: {collection.collection_title}")
        
        try:
            if not dry_run:
                # Deploy to Shopify
                await self.shopify_service.update_collection_metafields(
                    collection_id=collection.shopify_collection_id,
                    metafields={
                        'collection_description': collection.generated_content,
                        'collection_faq': collection.generated_faq,
                        'collection_schema': collection.generated_schema,
                        'optimized_at': datetime.utcnow().isoformat(),
                        'optimization_version': '1.0'
                    }
                )
                
                # Update status
                collection.optimization_status = "published"
                collection.metafield_description = collection.generated_content
                collection.metafield_faq = str(collection.generated_faq)
                collection.metafield_updated_at = datetime.utcnow()
                
                self.db.commit()
            
            # Log history
            self._log_history(
                collection_id=collection_id,
                action_type="deploy",
                action_status="success" if not dry_run else "dry_run",
                action_details={"dry_run": dry_run}
            )
            
            return {
                "status": "success",
                "collection": collection.collection_title,
                "dry_run": dry_run,
                "content_deployed": not dry_run,
                "educational_content_length": len(collection.generated_content) if collection.generated_content else 0,
                "faq_items_count": len(collection.generated_faq) if collection.generated_faq else 0
            }
            
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            self._log_history(
                collection_id=collection_id,
                action_type="deploy",
                action_status="failed",
                action_details={"error": str(e)}
            )
            self.db.commit()
            raise
    
    # =========================================================================
    # PHASE 5: TRACK - Monitor performance improvements
    # =========================================================================
    
    async def track_performance(self, collection_id: int) -> Dict:
        """
        Track performance improvements after optimization
        Includes both Search Console and GA4 metrics
        """
        collection = self.db.query(CollectionOptimizer).get(collection_id)
        if not collection:
            raise ValueError(f"Collection {collection_id} not found")
        
        logger.info(f"Tracking performance for: {collection.collection_title}")
        
        try:
            # Get current Search Console data
            queries = self.google_service.get_search_console_data(days=30)
            
            # Filter relevant queries
            relevant_queries = self._filter_relevant_queries(
                queries,
                collection.collection_title,
                collection.category
            )
            
            # Get GA4 data
            ga4_data = self.google_service.get_ga4_engagement_data(days=30)
            collection_path = f"/collections/{collection.collection_handle}"
            
            page_data = None
            for item in ga4_data:
                if collection_path in item['page_path'] or collection.collection_handle in item['page_path']:
                    page_data = item
                    break
            
            if relevant_queries:
                # Calculate current metrics
                total_impressions = sum(q['impressions'] for q in relevant_queries)
                total_clicks = sum(q['clicks'] for q in relevant_queries)
                avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
                
                # Calculate changes from baseline (Search Console)
                impressions_change = total_impressions - collection.baseline_impressions
                clicks_change = total_clicks - collection.baseline_clicks
                ctr_change = avg_ctr - collection.baseline_ctr
                
                # Update collection
                collection.current_impressions = total_impressions
                collection.current_clicks = total_clicks
                collection.current_ctr = avg_ctr
                collection.last_analytics_sync = datetime.utcnow()
                
                # Update GA4 metrics if available
                ga4_changes = {}
                if page_data:
                    collection.ga4_sessions = page_data['sessions']
                    collection.ga4_conversions = page_data['conversions']
                    collection.ga4_conversion_rate = (page_data['conversions'] / page_data['sessions'] * 100) if page_data['sessions'] > 0 else 0
                    collection.last_ga4_sync = datetime.utcnow()
                    
                    # Calculate GA4 changes
                    sessions_change = page_data['sessions'] - collection.baseline_ga4_sessions
                    conversions_change = page_data['conversions'] - collection.baseline_ga4_conversions
                    
                    ga4_changes = {
                        "sessions_change": sessions_change,
                        "conversions_change": conversions_change,
                        "current_sessions": page_data['sessions'],
                        "current_conversions": page_data['conversions'],
                        "conversion_rate": collection.ga4_conversion_rate
                    }
                
                self.db.commit()
                
                # Log history
                self._log_history(
                    collection_id=collection_id,
                    action_type="track",
                    action_status="success",
                    action_details={
                        "impressions_change": impressions_change,
                        "clicks_change": clicks_change,
                        "ctr_change": ctr_change,
                        **ga4_changes
                    },
                    impressions_change=impressions_change,
                    clicks_change=clicks_change,
                    ctr_change=ctr_change
                )
                
                result = {
                    "status": "success",
                    "collection": collection.collection_title,
                    "search_console": {
                        "baseline": {
                            "impressions": collection.baseline_impressions,
                            "clicks": collection.baseline_clicks,
                            "ctr": collection.baseline_ctr
                        },
                        "current": {
                            "impressions": total_impressions,
                            "clicks": total_clicks,
                            "ctr": avg_ctr
                        },
                        "improvement": {
                            "impressions": impressions_change,
                            "clicks": clicks_change,
                            "ctr": f"{ctr_change:+.2f}%"
                        }
                    }
                }
                
                # Add GA4 data if available
                if ga4_changes:
                    result["ga4"] = {
                        "baseline": {
                            "sessions": collection.baseline_ga4_sessions,
                            "conversions": collection.baseline_ga4_conversions
                        },
                        "current": {
                            "sessions": ga4_changes["current_sessions"],
                            "conversions": ga4_changes["current_conversions"],
                            "conversion_rate": f"{ga4_changes['conversion_rate']:.2f}%"
                        },
                        "improvement": {
                            "sessions": ga4_changes["sessions_change"],
                            "conversions": ga4_changes["conversions_change"]
                        }
                    }
                
                return result
            
        except Exception as e:
            logger.error(f"Tracking failed: {e}")
            self._log_history(
                collection_id=collection_id,
                action_type="track",
                action_status="failed",
                action_details={"error": str(e)}
            )
            self.db.commit()
            raise
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def _log_history(self, collection_id: Optional[int], action_type: str, 
                     action_status: str, action_details: Dict, **kwargs):
        """Log optimization history"""
        history = CollectionOptimizationHistory(
            collection_id=collection_id,
            action_type=action_type,
            action_status=action_status,
            action_details=action_details,
            **kwargs
        )
        self.db.add(history)
    
    async def get_optimization_queue(self, limit: int = 10, use_revenue_scoring: bool = True) -> List[Dict]:
        """
        Get collections queued for optimization
        
        Args:
            limit: Number of collections to return
            use_revenue_scoring: If True, uses GA4 conversion data for priority scoring
        """
        collections = self.db.query(CollectionOptimizer).filter(
            CollectionOptimizer.optimization_status.in_(["pending", "analyzed"])
        ).all()
        
        # Calculate priority for each collection
        collection_scores = []
        for c in collections:
            if use_revenue_scoring and c.ga4_sessions > 0:
                # Use revenue-based scoring
                priority = self._calculate_revenue_priority_score(c)
            else:
                # Use original priority score
                priority = c.optimization_priority
            
            collection_scores.append({
                "collection": c,
                "priority": priority
            })
        
        # Sort by priority (descending)
        collection_scores.sort(key=lambda x: x["priority"], reverse=True)
        
        # Return top N
        return [
            {
                "id": item["collection"].id,
                "title": item["collection"].collection_title,
                "status": item["collection"].optimization_status,
                "priority": item["priority"],
                "impressions": item["collection"].current_impressions,
                "ctr": item["collection"].current_ctr,
                "ga4_sessions": item["collection"].ga4_sessions,
                "ga4_conversions": item["collection"].ga4_conversions,
                "ga4_conversion_rate": item["collection"].ga4_conversion_rate,
                "revenue_potential": self._estimate_revenue_potential(item["collection"])
            }
            for item in collection_scores[:limit]
        ]
    
    def _estimate_revenue_potential(self, collection: CollectionOptimizer) -> str:
        """
        Estimate revenue potential based on current traffic and conversion rate
        """
        if collection.ga4_sessions == 0:
            return "unknown"
        
        # Estimate: If we improve conversion rate by 1%, what's the revenue impact?
        # Assuming average order value of $2000 MXN (adjust based on your data)
        avg_order_value = 2000
        
        current_revenue = collection.ga4_conversions * avg_order_value
        potential_additional_conversions = collection.ga4_sessions * 0.01  # 1% improvement
        potential_additional_revenue = potential_additional_conversions * avg_order_value
        
        if potential_additional_revenue > 10000:
            return f"high (+${potential_additional_revenue:,.0f} potential)"
        elif potential_additional_revenue > 5000:
            return f"medium (+${potential_additional_revenue:,.0f} potential)"
        else:
            return f"low (+${potential_additional_revenue:,.0f} potential)"
    
    async def run_full_workflow(self, collection_id: int) -> Dict:
        """
        Run complete workflow: Sync All Data → Analyze → Generate → Deploy

        Syncs all 4 data sources (GSC, GA4, Shopify, DataForSEO) before
        generating content to ensure recommendations are data-complete.
        """
        results = {}

        # Phase 1: Sync all data sources
        try:
            results['gsc_analyze'] = await self.analyze_collection_performance(collection_id)
        except Exception as e:
            logger.warning(f"GSC sync failed for {collection_id}: {e}")
            results['gsc_analyze'] = {"status": "failed", "error": str(e)}

        try:
            results['ga4_analyze'] = await self.analyze_ga4_performance(collection_id)
        except Exception as e:
            logger.warning(f"GA4 sync failed for {collection_id}: {e}")
            results['ga4_analyze'] = {"status": "failed", "error": str(e)}

        try:
            results['dataforseo'] = await self.run_dataforseo_for_collection(collection_id)
        except Exception as e:
            logger.warning(f"DataForSEO sync failed for {collection_id}: {e}")
            results['dataforseo'] = {"status": "failed", "error": str(e)}

        try:
            results['shopify_attribution'] = await self.sync_shopify_attribution(days=30)
        except Exception as e:
            logger.warning(f"Shopify attribution sync failed: {e}")
            results['shopify_attribution'] = {"status": "failed", "error": str(e)}

        # Phase 2: Generate content (with cannibalization guard)
        results['generate'] = await self.generate_collection_content(collection_id)

        # Phase 3: Deploy (dry run first)
        results['deploy_preview'] = await self.deploy_to_shopify(collection_id, dry_run=True)

        return results

    async def sync_all_data_sources(self, collection_id: int) -> Dict:
        """
        Sync all 4 data sources for a collection without generating content.
        Use this to refresh data before running intelligence/recommendations.
        """
        results = {"collection_id": collection_id, "sources": {}}

        # GSC
        try:
            results["sources"]["gsc"] = await self.analyze_collection_performance(collection_id)
            results["sources"]["gsc"]["status"] = "success"
        except Exception as e:
            results["sources"]["gsc"] = {"status": "failed", "error": str(e)}

        # GA4
        try:
            results["sources"]["ga4"] = await self.analyze_ga4_performance(collection_id)
            results["sources"]["ga4"]["status"] = "success"
        except Exception as e:
            results["sources"]["ga4"] = {"status": "failed", "error": str(e)}

        # DataForSEO
        try:
            results["sources"]["dataforseo"] = await self.run_dataforseo_for_collection(collection_id)
            results["sources"]["dataforseo"]["status"] = "success"
        except Exception as e:
            results["sources"]["dataforseo"] = {"status": "failed", "error": str(e)}

        # Shopify Attribution
        try:
            results["sources"]["shopify"] = await self.sync_shopify_attribution(days=30)
            results["sources"]["shopify"]["status"] = "success"
        except Exception as e:
            results["sources"]["shopify"] = {"status": "failed", "error": str(e)}

        # Summary
        successful = sum(1 for s in results["sources"].values() if s.get("status") == "success")
        results["summary"] = {
            "total_sources": 4,
            "successful": successful,
            "failed": 4 - successful,
        }

        return results
