"""
Store Intelligence Data Hub
Aggregates data from Shopify, GA4, Search Console, site crawler, and AEO/GEO systems.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid

from app.models.store_intelligence import StoreSnapshot
from app.models.store_intelligence import (
    CommerceData, TrafficData, SEOData, 
    GEOData, ContentData, TechnicalData, B2BData
)
from app.services.tier_tag_sync_service import tier_sync_service, TIER_HIERARCHY, ALL_TIER_TAGS
from app.models.product import Product
from app.models.aeo_models import FaultCode, ProductVisibilitySnapshot
from app.models.seo_intelligence import (
    KeywordDailyMetric, SEOAlert, GA4FunnelDaily
)
from app.services.shopify_service import shopify_service
from app.services.redis_service import create_cache
from app.services.google_api_service import GoogleApiService
from app.services.cro_analytics_service import CROAnalyticsService

logger = logging.getLogger("store_intelligence")

# Cache for expensive operations (Redis-backed)
_snapshot_cache = create_cache(default_ttl=3600)  # 1 hour


class StoreDataHub:
    """
    Central data aggregation hub for store intelligence.
    Pulls data from all sources and creates unified snapshots.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.shopify = shopify_service
        self.google = GoogleApiService()
    
    async def generate_snapshot(self, force_refresh: bool = False) -> StoreSnapshot:
        """
        Generate a comprehensive store snapshot by aggregating all data sources.
        
        Args:
            force_refresh: Ignore cache and fetch fresh data
            
        Returns:
            StoreSnapshot with all metrics
        """
        cache_key = f"store_snapshot:{datetime.now().strftime('%Y-%m-%d-%H')}"
        
        if not force_refresh:
            cached = _snapshot_cache.get(cache_key)
            if cached:
                logger.info("[DataHub] Returning cached snapshot")
                return cached
        
        logger.info("[DataHub] Generating fresh store snapshot...")
        
        # Gather all data sources
        commerce_data = await self._gather_commerce_data()
        traffic_data = await self._gather_traffic_data()
        seo_data = await self._gather_seo_data()
        geo_data = await self._gather_geo_data()
        content_data = await self._gather_content_data()
        technical_data = await self._gather_technical_data()
        b2b_data = await self._gather_b2b_data()
        
        # Gather preview data from SEO Intelligence and CRO
        seo_intelligence_preview = await self._gather_seo_intelligence_preview()
        cro_preview = await self._gather_cro_preview()
        
        # Calculate health scores
        health_scores_result = self._calculate_health_scores(
            commerce_data, traffic_data, seo_data, geo_data, technical_data
        )
        
        # Extract scores and details separately
        health_scores = {k: v for k, v in health_scores_result.items() if k != 'details'}
        score_details = health_scores_result.get('details', {})
        
        # Create snapshot
        snapshot = StoreSnapshot(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            
            # Raw data
            commerce_data={**commerce_data.dict(), 'score_details': score_details.get('commerce', {})},
            traffic_data={**traffic_data.dict(), 'score_details': score_details.get('cro', {}), 'cro_preview': cro_preview},
            seo_data={**seo_data.dict(), 'score_details': score_details.get('seo', {}), 'intelligence_preview': seo_intelligence_preview},
            geo_data={**geo_data.dict(), 'score_details': score_details.get('geo', {})},
            content_data=content_data.dict(),
            technical_data={**technical_data.dict(), 'score_details': score_details.get('technical', {})},
            b2b_data=b2b_data.dict(),
            
            # Health scores
            overall_health_score=health_scores['overall'],
            commerce_health=health_scores['commerce'],
            cro_health=health_scores['cro'],
            seo_health=health_scores['seo'],
            geo_health=health_scores['geo'],
            technical_health=health_scores['technical'],
            
            # Trend will be calculated by comparing to previous snapshot
            trend_direction=self._calculate_trend(health_scores['overall'])
        )
        
        # Save to database
        self.db.add(snapshot)
        self.db.commit()
        
        # Cache
        _snapshot_cache.set(cache_key, snapshot)
        
        logger.info(f"[DataHub] Snapshot generated: {snapshot.id}")
        return snapshot
    
    async def _gather_commerce_data(self) -> CommerceData:
        """Gather e-commerce metrics from Shopify."""
        logger.info("[DataHub] Gathering commerce data...")
        
        try:
            # Get sales data
            sales_30d = self.shopify.get_product_sales_all_periods()
            
            # Aggregate
            total_revenue = sum(
                p['30d']['total_revenue'] for p in sales_30d.values()
            )
            total_orders = sum(
                p['30d']['total_sold'] for p in sales_30d.values()
            )
            
            # Get product performance from DB
            products = self.db.query(Product).all()
            
            top_products = sorted(
                [{
                    'id': p.id,
                    'title': p.title[:50],
                    'revenue_30d': p.revenue_30d or 0,
                    'sold_30d': p.sold_30d or 0
                } for p in products if (p.revenue_30d or 0) > 0],
                key=lambda x: x['revenue_30d'],
                reverse=True
            )[:10]
            
            slow_movers = [{
                'id': p.id,
                'title': p.title[:50],
                'revenue_30d': p.revenue_30d or 0
            } for p in products if (p.sold_30d or 0) == 0 and (p.revenue_90d or 0) == 0][:10]
            
            # Category breakdown
            category_stats = self.db.query(
                Product.product_type,
                func.count(Product.id).label('count'),
                func.sum(Product.revenue_30d).label('revenue')
            ).group_by(Product.product_type).all()
            
            category_performance = [{
                'category': cat or 'Uncategorized',
                'product_count': count,
                'revenue_30d': float(revenue or 0)
            } for cat, count, revenue in category_stats]
            
            # Inventory status from DB
            out_of_stock = self.db.query(Product).filter(
                Product.inventory_quantity != None,
                Product.inventory_quantity <= 0
            ).count()
            low_stock = self.db.query(Product).filter(
                Product.inventory_quantity != None,
                Product.inventory_quantity > 0,
                Product.inventory_quantity <= 5
            ).count()
            
            # Customer metrics from product sales
            unique_customers = len(sales_30d)  # Approximate: unique SKUs sold
            
            return CommerceData(
                total_revenue_30d=total_revenue,
                total_orders_30d=total_orders,
                aov=total_revenue / total_orders if total_orders > 0 else 0,
                conversion_rate=0.0,  # Will be calculated with traffic data
                top_products=top_products,
                slow_movers=slow_movers,
                out_of_stock_count=out_of_stock,
                low_stock_count=low_stock,
                category_performance=category_performance,
                new_customers_30d=0,  # Requires Shopify customer API
                returning_customers_30d=0,
                customer_ltv_avg=total_revenue / max(unique_customers, 1)
            )
            
        except Exception as e:
            logger.error(f"[DataHub] Error gathering commerce data: {e}")
            return CommerceData()
    
    async def _gather_traffic_data(self) -> TrafficData:
        """Gather traffic and REAL CRO metrics from GA4 and Shopify."""
        logger.info("[DataHub] Gathering traffic and CRO data...")
        
        try:
            # Get REAL CRO metrics
            cro_service = CROAnalyticsService(self.db)
            cro_metrics = cro_service.get_cro_metrics(days=30)
            
            # Get GA4 engagement data
            ga4_data = self.google.get_ga4_engagement_data(days=30)
            
            total_sessions = sum(item.get('sessions', 0) for item in ga4_data)
            total_users = sum(item.get('active_users', 0) for item in ga4_data)
            
            # Get product-level traffic from DB
            total_db_sessions = self.db.query(
                func.sum(Product.ga4_sessions)
            ).scalar() or 0
            
            # Channel breakdown (simplified)
            channel_performance = {
                'organic_search': {
                    'sessions': self.db.query(func.sum(Product.gsc_clicks)).scalar() or 0
                },
                'direct': {
                    'sessions': total_db_sessions - (self.db.query(func.sum(Product.gsc_clicks)).scalar() or 0)
                }
            }
            
            # Top landing pages
            top_pages = self.db.query(
                Product.handle,
                Product.title,
                Product.ga4_sessions,
                Product.sold_30d
            ).filter(
                Product.ga4_sessions > 0
            ).order_by(Product.ga4_sessions.desc()).limit(10).all()
            
            top_landing_pages = [{
                'url': f"/products/{handle}",
                'title': title[:50],
                'sessions': sessions or 0,
                'conversions': sold or 0,
                'conversion_rate': ((sold or 0) / sessions * 100) if sessions > 0 else 0
            } for handle, title, sessions, sold in top_pages]
            
            # Use REAL CRO data if available
            purchase_rate = cro_metrics.get('conversion_rate', 0)
            cart_abandonment = cro_metrics.get('cart_abandonment_rate', 0)
            
            logger.info(f"[DataHub] Real CRO data - Conversion: {purchase_rate:.2f}%, Cart abandonment: {cart_abandonment:.0f}%")
            
            return TrafficData(
                total_sessions=total_sessions or total_db_sessions,
                unique_users=total_users,
                add_to_cart_rate=cro_metrics.get('add_to_cart_rate', 0),
                checkout_rate=0.0,  # TODO: Add from Shopify
                purchase_rate=purchase_rate,
                cart_abandonment_rate=cart_abandonment,
                channel_performance=channel_performance,
                top_landing_pages=top_landing_pages,
                high_exit_pages=[],  # TODO: Implement
                avg_session_duration=self.db.query(
                    func.avg(Product.ga4_engagement_time)
                ).scalar() or 0,
                bounce_rate=self.db.query(
                    func.avg(Product.ga4_bounce_rate)
                ).scalar() or 0,
                pages_per_session=0.0,
                mobile_percentage=cro_metrics.get('mobile_percentage', 50.0),
                desktop_percentage=cro_metrics.get('desktop_percentage', 50.0)
            )
            
        except Exception as e:
            logger.error(f"[DataHub] Error gathering traffic data: {e}")
            return TrafficData()
    
    async def _gather_seo_data(self) -> SEOData:
        """Gather SEO metrics from Search Console and internal data."""
        logger.info("[DataHub] Gathering SEO data...")
        
        try:
            # Get GSC data
            gsc_data = self.google.get_search_console_data(days=30)
            
            total_clicks = sum(item.get('clicks', 0) for item in gsc_data)
            total_impressions = sum(item.get('impressions', 0) for item in gsc_data)
            avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
            avg_position = sum(item.get('position', 0) for item in gsc_data) / len(gsc_data) if gsc_data else 0
            
            # Top queries
            top_queries = sorted(gsc_data, key=lambda x: x.get('clicks', 0), reverse=True)[:20]
            
            # Opportunity queries (high impressions, low CTR)
            opportunity_queries = [
                q for q in gsc_data 
                if q.get('impressions', 0) > 100 and q.get('ctr', 0) < 0.02
            ][:10]
            
            # Product SEO status from DB
            total_products = self.db.query(Product).count()
            optimized_products = self.db.query(Product).filter(
                Product.seo_status == 'published'
            ).count()
            
            # Competitor mentions (from AI visibility)
            visibility_data = self.db.query(ProductVisibilitySnapshot).order_by(
                ProductVisibilitySnapshot.snapshot_date.desc()
            ).first()
            
            competitor_mentions = 0
            your_mentions = 0
            if visibility_data and visibility_data.top_competitors:
                competitor_mentions = len(visibility_data.top_competitors)
                your_mentions = visibility_data.visibility_score // 10  # Rough estimate
            
            return SEOData(
                total_clicks=total_clicks,
                total_impressions=total_impressions,
                avg_ctr=avg_ctr,
                avg_position=avg_position,
                top_queries=[{
                    'query': q.get('query'),
                    'clicks': q.get('clicks'),
                    'impressions': q.get('impressions'),
                    'ctr': q.get('ctr'),
                    'position': q.get('position')
                } for q in top_queries],
                declining_queries=[],  # TODO: Compare with historical
                opportunity_queries=[{
                    'query': q.get('query'),
                    'impressions': q.get('impressions'),
                    'ctr': q.get('ctr'),
                    'potential_clicks': int(q.get('impressions', 0) * 0.03)
                } for q in opportunity_queries],
                indexed_pages=total_products,
                products_optimized=optimized_products,
                products_needing_seo=total_products - optimized_products,
                competitor_mentions=competitor_mentions,
                your_mentions=your_mentions
            )
            
        except Exception as e:
            logger.error(f"[DataHub] Error gathering SEO data: {e}")
            return SEOData()
    
    async def _gather_geo_data(self) -> GEOData:
        """Gather AI/GEO visibility metrics."""
        logger.info("[DataHub] Gathering GEO data...")
        
        try:
            # Get latest AI visibility data
            latest_visibility = self.db.query(ProductVisibilitySnapshot).order_by(
                ProductVisibilitySnapshot.snapshot_date.desc()
            ).first()
            
            if latest_visibility and latest_visibility.scores_by_llm:
                scores = latest_visibility.scores_by_llm
                grok_score = scores.get('grok', 0)
                openai_score = scores.get('openai', 0)
                perplexity_score = scores.get('perplexity', 0)
                overall = latest_visibility.visibility_score
            else:
                grok_score = openai_score = perplexity_score = overall = 0
            
            # LLM traffic
            llm_traffic = self.google.get_llm_txt_traffic(days=30)
            llm_sessions = sum(item.get('sessions', 0) for item in llm_traffic)
            
            # Get competitive analysis
            fault_codes = self.db.query(FaultCode).all()
            total_citations = sum(fc.monthly_clicks or 0 for fc in fault_codes)
            
            return GEOData(
                grok_score=grok_score,
                openai_score=openai_score,
                perplexity_score=perplexity_score,
                overall_visibility=overall,
                total_citations=total_citations,
                citations_by_source={
                    'grok': grok_score // 10,
                    'openai': openai_score // 10,
                    'perplexity': perplexity_score // 10
                },
                llm_referral_sessions=llm_sessions,
                llm_conversions=0,  # TODO: Implement
                llm_conversion_rate=0.0,
                vs_competitors={
                    'your_mentions': overall // 10,
                    'avg_competitor_mentions': 25  # Placeholder
                }
            )
            
        except Exception as e:
            logger.error(f"[DataHub] Error gathering GEO data: {e}")
            return GEOData()
    
    async def _gather_content_data(self) -> ContentData:
        """Gather content quality and coverage metrics."""
        logger.info("[DataHub] Gathering content data...")
        
        try:
            # Product content status
            total_products = self.db.query(Product).count()
            # Note: description_length is a property, not a column, so we filter in Python
            products_with_html = self.db.query(Product).filter(
                Product.current_description_html.isnot(None)
            ).all()
            products_with_content = len([
                p for p in products_with_html 
                if p.current_description_html and len(p.current_description_html) > 500
            ])
            
            products_needing_content = self.db.query(Product).filter(
                Product.needs_seo == True
            ).count()
            
            # Average content score (simple heuristic)
            avg_content_score = self.db.query(
                func.avg(Product.performance_score)
            ).scalar() or 0
            
            # Products with SEO scores
            products_with_scores = self.db.query(Product).filter(
                Product.performance_score > 0
            ).all()
            
            if products_with_scores:
                avg_content_score = sum(
                    p.performance_score or 0 for p in products_with_scores
                ) / len(products_with_scores)
            
            # Outdated content (not updated in 90 days)
            cutoff_date = datetime.utcnow() - timedelta(days=90)
            outdated = self.db.query(Product).filter(
                Product.last_scraped_at < cutoff_date
            ).limit(10).all()
            
            outdated_content = [{
                'id': p.id,
                'title': p.title[:50],
                'last_updated': p.last_scraped_at.isoformat() if p.last_scraped_at else None
            } for p in outdated]
            
            return ContentData(
                products_with_content=products_with_content,
                products_needing_content=products_needing_content,
                avg_content_score=float(avg_content_score),
                collections_optimized=0,  # TODO: Implement
                collections_needing_work=0,
                blog_posts_30d=0,  # TODO: Fetch from cache
                total_blog_posts=0,
                missing_topics=[],  # TODO: Implement content gap analysis
                outdated_content=outdated_content
            )
            
        except Exception as e:
            logger.error(f"[DataHub] Error gathering content data: {e}")
            return ContentData()
    
    async def _gather_technical_data(self) -> TechnicalData:
        """Gather technical SEO metrics."""
        logger.info("[DataHub] Gathering technical data...")
        
        try:
            # Schema coverage
            products_with_schema = self.db.query(Product).filter(
                Product.transmission_code.isnot(None)
            ).count()
            total_products = self.db.query(Product).count()
            
            schema_coverage = (
                (products_with_schema / total_products * 100) 
                if total_products > 0 else 0
            )
            
            # For now, return placeholder data
            # In production, this would crawl the site or use CrUX API
            return TechnicalData(
                lcp=2.0,  # Placeholder - would get from CrUX
                fid=50.0,
                cls=0.1,
                cwv_status='good',  # or 'needs_improvement', 'poor'
                broken_links_count=0,  # TODO: Implement crawler
                redirect_chains_count=0,
                schema_coverage_pct=schema_coverage,
                schema_errors_count=0,
                mobile_usability_issues=0,
                ssl_valid=True,
                security_issues=[]
            )
            
        except Exception as e:
            logger.error(f"[DataHub] Error gathering technical data: {e}")
            return TechnicalData()
    
    async def _gather_b2b_data(self) -> B2BData:
        """Gather B2B customer tier intelligence from Shopify segments."""
        logger.info("[DataHub] Gathering B2B tier data...")
        
        try:
            # Use tier sync service to get segment member counts and tag status
            tier_breakdown = {}
            total_b2b = 0
            correctly_tagged = 0
            missing_tags = 0
            
            for tier in TIER_HIERARCHY:
                tier_name = tier["name"]
                tag = tier["tag"]
                segment_id = tier["segment_id"]
                
                try:
                    members = tier_sync_service.get_segment_members(segment_id)
                    count = len(members)
                    tier_breakdown[tier_name] = count
                    total_b2b += count
                    
                    # Check tag health
                    for m in members:
                        if tag in m.get("tags", []):
                            correctly_tagged += 1
                        else:
                            missing_tags += 1
                            
                except Exception as e:
                    logger.warning(f"[DataHub] Failed to fetch tier {tier_name}: {e}")
                    tier_breakdown[tier_name] = 0
            
            tag_health_pct = (correctly_tagged / total_b2b * 100) if total_b2b > 0 else 0
            
            logger.info(f"[DataHub] B2B data: {total_b2b} customers, {correctly_tagged} tagged ({tag_health_pct:.0f}%)")
            
            return B2BData(
                total_b2b_customers=total_b2b,
                tier_breakdown=tier_breakdown,
                correctly_tagged=correctly_tagged,
                missing_tags=missing_tags,
                tag_health_pct=round(tag_health_pct, 1),
            )
            
        except Exception as e:
            logger.error(f"[DataHub] Error gathering B2B data: {e}")
            return B2BData()
    
    async def _gather_seo_intelligence_preview(self) -> Dict[str, Any]:
        """
        Gather preview data from SEO Intelligence tables.
        This is for the main dashboard - full data is in /intelligence/seo
        """
        logger.info("[DataHub] Gathering SEO Intelligence preview...")
        
        preview = {
            'keywords_tracked': 0,
            'keywords_improving': 0,
            'keywords_declining': 0,
            'open_alerts': 0,
            'ctr_opportunities': 0,
            'potential_clicks': 0,
            'last_collection': None,
            'has_data': False
        }
        
        try:
            # Get latest keyword data
            latest_date = self.db.query(
                KeywordDailyMetric.date
            ).order_by(
                KeywordDailyMetric.date.desc()
            ).first()
            
            if latest_date:
                latest_date = latest_date[0]
                preview['last_collection'] = latest_date.isoformat() if latest_date else None
                preview['has_data'] = True
                
                # Count keywords
                keywords = self.db.query(KeywordDailyMetric).filter(
                    KeywordDailyMetric.date == latest_date
                ).all()
                
                preview['keywords_tracked'] = len(keywords)
                preview['keywords_improving'] = sum(
                    1 for k in keywords 
                    if k.position_change_7d is not None and k.position_change_7d < -0.5
                )
                preview['keywords_declining'] = sum(
                    1 for k in keywords 
                    if k.position_change_7d is not None and k.position_change_7d > 0.5
                )
                
                # CTR opportunities
                preview['ctr_opportunities'] = sum(
                    1 for k in keywords 
                    if k.is_underperforming
                )
                preview['potential_clicks'] = sum(
                    int(k.impressions * abs(k.ctr_gap)) 
                    for k in keywords 
                    if k.is_underperforming and k.ctr_gap
                )
            
            # Count open alerts
            preview['open_alerts'] = self.db.query(SEOAlert).filter(
                SEOAlert.status == 'open'
            ).count()
            
        except Exception as e:
            logger.error(f"[DataHub] Error gathering SEO Intelligence preview: {e}")
        
        return preview
    
    async def _gather_cro_preview(self) -> Dict[str, Any]:
        """
        Gather preview data from CRO/GA4 funnel tables.
        This is for the main dashboard - full data is in /intelligence/cro-technical
        """
        logger.info("[DataHub] Gathering CRO preview...")
        
        preview = {
            'sessions': 0,
            'purchases': 0,
            'conversion_rate': 0,
            'revenue': 0,
            'biggest_dropoff': None,
            'device_breakdown': {},
            'has_data': False
        }
        
        try:
            # Get funnel data from last 7 days
            from datetime import date as date_type
            since = date_type.today() - timedelta(days=7)
            
            funnel_data = self.db.query(GA4FunnelDaily).filter(
                GA4FunnelDaily.date >= since,
                GA4FunnelDaily.device_category == 'all'
            ).all()
            
            if funnel_data:
                preview['has_data'] = True
                preview['sessions'] = sum(f.sessions for f in funnel_data)
                preview['purchases'] = sum(f.purchases for f in funnel_data)
                preview['revenue'] = sum(f.revenue for f in funnel_data)
                preview['conversion_rate'] = (
                    preview['purchases'] / preview['sessions'] * 100 
                    if preview['sessions'] > 0 else 0
                )
            
            # Device breakdown
            device_data = self.db.query(GA4FunnelDaily).filter(
                GA4FunnelDaily.date >= since,
                GA4FunnelDaily.device_category != 'all'
            ).all()
            
            if device_data:
                devices = {}
                for d in device_data:
                    if d.device_category not in devices:
                        devices[d.device_category] = {'sessions': 0, 'purchases': 0}
                    devices[d.device_category]['sessions'] += d.sessions
                    devices[d.device_category]['purchases'] += d.purchases
                
                total_sessions = sum(v['sessions'] for v in devices.values())
                for device, data in devices.items():
                    data['share'] = (
                        data['sessions'] / total_sessions * 100 
                        if total_sessions > 0 else 0
                    )
                    data['conversion'] = (
                        data['purchases'] / data['sessions'] * 100 
                        if data['sessions'] > 0 else 0
                    )
                
                preview['device_breakdown'] = devices
            
            # Find biggest dropoff
            if funnel_data:
                total_views = sum(f.product_views for f in funnel_data)
                total_carts = sum(f.add_to_carts for f in funnel_data)
                total_checkouts = sum(f.begin_checkouts for f in funnel_data)
                
                drops = [
                    ('View to Cart', total_carts / total_views * 100 if total_views > 0 else 0),
                    ('Cart to Checkout', total_checkouts / total_carts * 100 if total_carts > 0 else 0),
                    ('Checkout to Purchase', preview['purchases'] / total_checkouts * 100 if total_checkouts > 0 else 0),
                ]
                
                if drops:
                    min_drop = min(drops, key=lambda x: x[1])
                    preview['biggest_dropoff'] = {
                        'step': min_drop[0],
                        'rate': round(min_drop[1], 1)
                    }
            
        except Exception as e:
            logger.error(f"[DataHub] Error gathering CRO preview: {e}")
        
        return preview
    
    def _calculate_health_scores(
        self,
        commerce: CommerceData,
        traffic: TrafficData,
        seo: SEOData,
        geo: GEOData,
        technical: TechnicalData
    ) -> Dict[str, Any]:
        """Calculate health scores for each category (0-100)."""
        
        # ---- COMMERCE HEALTH ----
        # Revenue component (0-25): scaled logarithmically 
        revenue = commerce.total_revenue_30d
        if revenue >= 500000:
            rev_pts = 25
        elif revenue >= 100000:
            rev_pts = 20
        elif revenue >= 50000:
            rev_pts = 15
        elif revenue >= 10000:
            rev_pts = 10
        elif revenue > 0:
            rev_pts = 5
        else:
            rev_pts = 0
        
        # AOV component (0-15)
        aov_pts = min(15, int(commerce.aov / 20)) if commerce.aov > 0 else 0
        
        # Product health component (0-30): penalize slow movers and out-of-stock
        total_products = len(commerce.top_products) + len(commerce.slow_movers)
        if total_products > 0:
            slow_ratio = len(commerce.slow_movers) / max(total_products, 1)
            product_pts = int(30 * (1 - slow_ratio))  # More slow movers = lower score
        else:
            product_pts = 15
        
        # Inventory penalty (0 to -15)
        inventory_penalty = min(15, commerce.out_of_stock_count * 2)
        
        # Customer health (0-15)
        customer_pts = 5  # Base
        if commerce.customer_ltv_avg > 500:
            customer_pts = 15
        elif commerce.customer_ltv_avg > 200:
            customer_pts = 10
        
        # Diversity bonus (0-15)
        diversity_pts = min(15, len(commerce.category_performance) * 3)
        
        commerce_score = min(100, max(0, 
            rev_pts + aov_pts + product_pts - inventory_penalty + customer_pts + diversity_pts
        ))
        
        # ---- CRO HEALTH ----
        # Conversion rate component (0-40): 3% = excellent for B2B auto parts
        cr = traffic.purchase_rate
        if cr >= 3.0:
            cr_pts = 40
        elif cr >= 2.0:
            cr_pts = 30
        elif cr >= 1.0:
            cr_pts = 20
        elif cr > 0:
            cr_pts = int(cr * 20)
        else:
            cr_pts = 0
        
        # Cart abandonment penalty (0-30): 70% = severe, <40% = excellent
        abandon = traffic.cart_abandonment_rate
        if abandon <= 30:
            abandon_pts = 30
        elif abandon <= 50:
            abandon_pts = 20
        elif abandon <= 65:
            abandon_pts = 10
        elif abandon <= 75:
            abandon_pts = 5
        else:
            abandon_pts = 0  # >75% abandonment = 0 points
        
        # Engagement component (0-15)
        engage_pts = 5  # Base
        if traffic.avg_session_duration > 180:
            engage_pts = 15
        elif traffic.avg_session_duration > 60:
            engage_pts = 10
        
        # Bounce rate penalty (0-15)
        if traffic.bounce_rate < 30:
            bounce_pts = 15
        elif traffic.bounce_rate < 50:
            bounce_pts = 10
        elif traffic.bounce_rate < 70:
            bounce_pts = 5
        else:
            bounce_pts = 0
        
        cro_score = min(100, max(0, cr_pts + abandon_pts + engage_pts + bounce_pts))
        
        # ---- SEO HEALTH ----
        # Position component (0-25)
        if seo.avg_position < 5:
            pos_pts = 25
        elif seo.avg_position < 10:
            pos_pts = 20
        elif seo.avg_position < 20:
            pos_pts = 15
        elif seo.avg_position < 30:
            pos_pts = 10
        else:
            pos_pts = 5
        
        # CTR component (0-20)
        if seo.avg_ctr > 5:
            ctr_pts = 20
        elif seo.avg_ctr > 3:
            ctr_pts = 15
        elif seo.avg_ctr > 1.5:
            ctr_pts = 10
        else:
            ctr_pts = 5
        
        # Product optimization ratio (0-35): this is the KEY metric
        total_seo = seo.products_optimized + seo.products_needing_seo
        if total_seo > 0:
            opt_ratio = seo.products_optimized / total_seo
            opt_pts = int(35 * opt_ratio)  # 100% optimized = 35pts, 5% = 1.75pts
        else:
            opt_pts = 0
        
        # Impressions/clicks volume (0-20)
        if seo.total_clicks > 10000:
            vol_pts = 20
        elif seo.total_clicks > 5000:
            vol_pts = 15
        elif seo.total_clicks > 1000:
            vol_pts = 10
        elif seo.total_clicks > 0:
            vol_pts = 5
        else:
            vol_pts = 0
        
        seo_score = min(100, max(0, pos_pts + ctr_pts + opt_pts + vol_pts))
        
        # ---- GEO HEALTH ----
        # Weighted average across LLMs (each 0-33)
        geo_score = min(100, max(0,
            geo.overall_visibility if geo.overall_visibility > 0 else
            (geo.grok_score + geo.openai_score + geo.perplexity_score) // 3
        ))
        
        # ---- TECHNICAL HEALTH ----
        # CWV base (0-40)
        if technical.cwv_status == 'good':
            cwv_pts = 40
        elif technical.cwv_status == 'needs_improvement':
            cwv_pts = 25
        else:
            cwv_pts = 10
        
        # LCP detail (0-15)
        if technical.lcp < 1.5:
            lcp_pts = 15
        elif technical.lcp < 2.5:
            lcp_pts = 10
        elif technical.lcp < 4.0:
            lcp_pts = 5
        else:
            lcp_pts = 0
        
        # CLS detail (0-15)
        if technical.cls < 0.05:
            cls_pts = 15
        elif technical.cls < 0.1:
            cls_pts = 10
        elif technical.cls < 0.25:
            cls_pts = 5
        else:
            cls_pts = 0
        
        # Schema coverage (0-20)
        schema_pts = min(20, int(technical.schema_coverage_pct / 5))  # 100% = 20pts
        
        # Security (0-10)
        sec_pts = 10 if technical.ssl_valid and len(technical.security_issues) == 0 else 5
        
        tech_score = min(100, max(0, cwv_pts + lcp_pts + cls_pts + schema_pts + sec_pts))
        
        # ---- OVERALL WEIGHTED AVERAGE ----
        overall = int(
            commerce_score * 0.25 +
            cro_score * 0.20 +
            seo_score * 0.25 +
            geo_score * 0.15 +
            tech_score * 0.15
        )
        
        # Build detailed breakdowns for transparency (stored separately)
        opt_ratio_pct = (seo.products_optimized / max(seo.products_optimized + seo.products_needing_seo, 1)) * 100
        
        details = {
            'commerce': {
                'revenue_30d': float(commerce.total_revenue_30d),
                'aov': float(commerce.aov),
                'orders_30d': int(commerce.total_orders_30d),
                'top_products_count': len(commerce.top_products),
                'slow_movers_count': len(commerce.slow_movers),
                'out_of_stock': int(commerce.out_of_stock_count),
                'low_stock': int(commerce.low_stock_count),
                'customer_ltv': float(commerce.customer_ltv_avg),
                'calculation': f"Rev({rev_pts}) + AOV({aov_pts}) + Products({product_pts}) - OOS({inventory_penalty}) + LTV({customer_pts}) + Diversity({diversity_pts})"
            },
            'cro': {
                'conversion_rate': float(traffic.purchase_rate),
                'cart_abandonment': float(traffic.cart_abandonment_rate),
                'bounce_rate': float(traffic.bounce_rate),
                'avg_session_duration': float(traffic.avg_session_duration),
                'target_rate': 3.0,
                'calculation': f"CR({cr_pts}) + Abandon({abandon_pts}) + Engage({engage_pts}) + Bounce({bounce_pts})"
            },
            'seo': {
                'avg_position': float(seo.avg_position),
                'avg_ctr': float(seo.avg_ctr),
                'products_optimized': int(seo.products_optimized),
                'products_needing_seo': int(seo.products_needing_seo),
                'optimization_ratio': f"{opt_ratio_pct:.1f}%",
                'indexed_pages': int(seo.indexed_pages),
                'total_clicks': int(seo.total_clicks),
                'calculation': f"Position({pos_pts}) + CTR({ctr_pts}) + OptRatio {opt_ratio_pct:.0f}%({opt_pts}) + Volume({vol_pts})"
            },
            'geo': {
                'grok_score': int(geo.grok_score),
                'openai_score': int(geo.openai_score),
                'perplexity_score': int(geo.perplexity_score),
                'total_citations': int(geo.total_citations),
                'llm_traffic': int(geo.llm_referral_sessions),
                'calculation': f"Avg of Grok({geo.grok_score}) + OpenAI({geo.openai_score}) + Perplexity({geo.perplexity_score})"
            },
            'technical': {
                'cwv_status': str(technical.cwv_status),
                'lcp': float(technical.lcp),
                'cls': float(technical.cls),
                'schema_coverage': float(technical.schema_coverage_pct),
                'calculation': f"CWV({cwv_pts}) + LCP({lcp_pts}) + CLS({cls_pts}) + Schema({schema_pts}) + Security({sec_pts})"
            }
        }
        
        return {
            'overall': overall,
            'commerce': commerce_score,
            'cro': cro_score,
            'seo': seo_score,
            'geo': geo_score,
            'technical': tech_score,
            'details': details
        }
    
    def _calculate_trend(self, current_score: int) -> str:
        """Compare to previous snapshot to determine trend."""
        previous = self.db.query(StoreSnapshot).order_by(
            StoreSnapshot.timestamp.desc()
        ).offset(1).first()  # Get second most recent
        
        if not previous:
            return 'stable'
        
        diff = current_score - previous.overall_health_score
        
        if diff > 5:
            return 'improving'
        elif diff < -5:
            return 'declining'
        else:
            return 'stable'
    
    def get_latest_snapshot(self) -> Optional[StoreSnapshot]:
        """Get the most recent snapshot."""
        return self.db.query(StoreSnapshot).order_by(
            StoreSnapshot.timestamp.desc()
        ).first()
    
    def get_historical_trends(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get historical snapshots for trend analysis."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        snapshots = self.db.query(StoreSnapshot).filter(
            StoreSnapshot.timestamp >= cutoff
        ).order_by(StoreSnapshot.timestamp.asc()).all()
        
        return [{
            'timestamp': s.timestamp.isoformat(),
            'overall': s.overall_health_score,
            'commerce': s.commerce_health,
            'cro': s.cro_health,
            'seo': s.seo_health,
            'geo': s.geo_health,
            'technical': s.technical_health
        } for s in snapshots]


# Singleton instance
def get_store_data_hub(db: Session) -> StoreDataHub:
    """Factory function for StoreDataHub."""
    return StoreDataHub(db)
