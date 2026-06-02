from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.product import Product
from app.services.google_api_service import GoogleApiService


class ProductService:
    """Service layer for Product operations including analytics sync."""
    
    def __init__(self, db: Session):
        self.db = db
        self.google_service = GoogleApiService()
    
    def calculate_performance_score(self, product: Product) -> int:
        """
        Calculate a combined performance score (0-100) based on:
        - Sessions (30%)
        - Revenue (40%)
        - SEO Score (30%)
        """
        # Normalize sessions (0-30 points, assuming 1000+ is max)
        session_score = min(30, (product.ga4_sessions / 1000) * 30)
        
        # Normalize revenue (0-40 points, assuming $10k+ is max)
        revenue_score = min(40, (product.ga4_revenue / 10000) * 40)
        
        # SEO score (0-30 points, already 0-100 so scale down)
        # Get seo_score from product or calculate if not available
        seo_score = getattr(product, 'seo_score', 50) * 0.3
        
        total_score = int(session_score + revenue_score + seo_score)
        return min(100, max(0, total_score))
    
    def calculate_seo_score(self, html: str) -> int:
        """
        Calculate SEO score (0-100) for product description HTML.
        Same logic as shopify_service.get_seo_score()
        """
        if not html:
            return 0
        
        score = 0
        html_lower = html.lower()
        
        # Length scoring (0-30 points)
        length = len(html)
        if length >= 1500:
            score += 30
        elif length >= 1000:
            score += 25
        elif length >= 500:
            score += 20
        elif length >= 300:
            score += 15
        elif length >= 150:
            score += 10
        elif length >= 50:
            score += 5
        
        # Headings scoring (0-20 points)
        has_h1 = '<h1>' in html_lower or '<h1 ' in html_lower
        has_h2 = '<h2>' in html_lower or '<h2 ' in html_lower
        has_h3 = '<h3>' in html_lower or '<h3 ' in html_lower
        heading_count = sum([has_h1, has_h2, has_h3])
        score += min(heading_count * 7, 20)
        
        # Lists scoring (0-15 points)
        has_ul = '<ul>' in html_lower or '<ul ' in html_lower
        has_ol = '<ol>' in html_lower or '<ol ' in html_lower
        if has_ul or has_ol:
            li_count = html_lower.count('<li>')
            if li_count >= 5:
                score += 15
            elif li_count >= 3:
                score += 12
            elif li_count >= 1:
                score += 8
        
        # Links scoring (0-10 points)
        link_count = html_lower.count('<a href')
        if link_count >= 3:
            score += 10
        elif link_count >= 1:
            score += 5
        
        # Paragraphs scoring (0-10 points)
        p_count = html_lower.count('<p>')
        if p_count >= 3:
            score += 10
        elif p_count >= 1:
            score += 5
        
        # Bold/emphasis scoring (0-5 points)
        bold_count = html_lower.count('<strong>') + html_lower.count('<b>')
        if bold_count >= 3:
            score += 5
        elif bold_count >= 1:
            score += 3
        
        return min(100, score)
    
    def determine_opportunity_level(self, product: Product) -> str:
        """
        Determine opportunity level based on traffic and SEO performance.
        
        High: High traffic (>100 sessions) but low SEO score (<50)
        Medium: Moderate traffic (>50 sessions) and SEO needs work (<70)
        Low: Everything else
        """
        # Calculate actual SEO score from HTML content
        seo_score = self.calculate_seo_score(product.current_description_html or "")
        
        if product.ga4_sessions > 100 and seo_score < 50:
            return 'high'
        elif product.ga4_sessions > 50 and seo_score < 70:
            return 'medium'
        else:
            return 'low'
    
    async def sync_product_analytics(self) -> Dict:
        """
        Match products to GA4 and Search Console data by URL.
        
        Returns:
            Dict with update statistics
        """
        import os
        
        print("\n" + "="*60)
        print("🔍 ANALYTICS SYNC DIAGNOSTICS")
        print("="*60)
        
        # Check environment configuration
        ga4_property = os.getenv('GOOGLE_GA4_PROPERTY_ID', 'NOT SET')
        gsc_url = os.getenv('GOOGLE_SEARCH_CONSOLE_SITE_URL', 'NOT SET')
        creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'NOT SET')
        
        print(f"📊 GA4 Property ID: {ga4_property}")
        print(f"🔍 GSC Site URL: {gsc_url}")
        print(f"🔑 Credentials Path: {creds_path}")
        print(f"✅ Credentials Loaded: {self.google_service.credentials is not None}")
        
        # Get all products
        products = self.db.query(Product).all()
        print(f"\n📦 Total products in database: {len(products)}")
        
        # Get GA4 data for product pages (last 30 days)
        print("\n🔄 Fetching GA4 data...")
        ga4_data = self.google_service.get_ga4_engagement_data(days=30)
        print(f"✅ GA4 returned {len(ga4_data)} page records")
        
        # Show sample GA4 data
        if ga4_data:
            print(f"   Sample GA4 paths: {[d.get('page_path', 'N/A') for d in ga4_data[:3]]}")
        else:
            print("   ⚠️ No GA4 data returned - check GA4 Property ID and credentials")
        
        # Get Search Console data for product pages
        print("\n🔄 Fetching Search Console data...")
        gsc_data = self.google_service.get_search_console_product_data(days=30)
        print(f"✅ GSC returned {len(gsc_data)} page records")
        
        # Show sample GSC data
        if gsc_data:
            print(f"   Sample GSC pages: {[d.get('page', 'N/A') for d in gsc_data[:3]]}")
        else:
            print("   ⚠️ No GSC data returned - check Search Console URL and credentials")
        
        # Count product pages in analytics data
        ga4_product_pages = [d for d in ga4_data if '/products/' in d.get('page_path', '')]
        gsc_product_pages = [d for d in gsc_data if '/products/' in d.get('page', '')]
        print(f"\n📈 Product pages found in GA4: {len(ga4_product_pages)}")
        print(f"📈 Product pages found in GSC: {len(gsc_product_pages)}")
        
        updated_count = 0
        ga4_matched = 0
        gsc_matched = 0
        ga4_reset = 0
        gsc_reset = 0
        high_opps = 0
        medium_opps = 0
        low_opps = 0

        # Build lookup dicts with normalized paths for exact matching
        def normalize_path(url: str) -> str:
            """Extract clean product path: /products/handle (no query params, trailing slash, or domain)."""
            from urllib.parse import urlparse
            parsed = urlparse(url)
            path = parsed.path.rstrip('/')
            return path.lower()

        ga4_lookup = {}
        for item in ga4_data:
            path = normalize_path(item.get('page_path', ''))
            if '/products/' in path:
                ga4_lookup[path] = item

        gsc_lookup = {}
        for item in gsc_data:
            path = normalize_path(item.get('page', ''))
            if '/products/' in path:
                gsc_lookup[path] = item

        for product in products:
            if not product.handle:
                continue

            product_path = f"/products/{product.handle}".lower()

            # Exact match GA4 data
            ga4_match = ga4_lookup.get(product_path)

            if ga4_match:
                product.ga4_sessions = ga4_match.get('sessions', 0)
                product.ga4_engagement_time = ga4_match.get('avg_duration', 0.0)
                product.ga4_revenue = ga4_match.get('revenue', 0.0)
                product.ga4_bounce_rate = ga4_match.get('bounce_rate', 0.0)
                ga4_matched += 1
            else:
                # Reset GA4 fields when no data found — prevents stale data
                product.ga4_sessions = 0
                product.ga4_engagement_time = 0.0
                product.ga4_revenue = 0.0
                product.ga4_bounce_rate = 0.0
                ga4_reset += 1

            # Exact match GSC data
            gsc_match = gsc_lookup.get(product_path)

            if gsc_match:
                product.gsc_impressions = gsc_match.get('impressions', 0)
                product.gsc_clicks = gsc_match.get('clicks', 0)
                product.gsc_ctr = gsc_match.get('ctr', 0.0)
                product.gsc_position = gsc_match.get('position', 0.0)
                gsc_matched += 1
            else:
                # Reset GSC fields when no data found — prevents stale data
                product.gsc_impressions = 0
                product.gsc_clicks = 0
                product.gsc_ctr = 0.0
                product.gsc_position = 0.0
                gsc_reset += 1

            # Calculate performance score
            product.performance_score = self.calculate_performance_score(product)

            # Determine opportunity level
            product.opportunity_level = self.determine_opportunity_level(product)

            # Count opportunity levels
            if product.opportunity_level == 'high':
                high_opps += 1
            elif product.opportunity_level == 'medium':
                medium_opps += 1
            else:
                low_opps += 1

            # Update sync timestamp
            product.last_analytics_sync = datetime.utcnow()

            if ga4_match or gsc_match:
                updated_count += 1

        self.db.commit()
        
        # Print summary
        print("\n" + "="*60)
        print("SYNC SUMMARY")
        print("="*60)
        print(f"  Products matched to GA4 data: {ga4_matched}")
        print(f"  Products matched to GSC data: {gsc_matched}")
        print(f"  GA4 reset (no data found): {ga4_reset}")
        print(f"  GSC reset (no data found): {gsc_reset}")
        print(f"  Total products with analytics: {updated_count}")
        print(f"  Total products processed: {len(products)}")
        print("")
        print("OPPORTUNITY LEVELS:")
        print(f"   High: {high_opps} (traffic >100, SEO score <50)")
        print(f"   Medium: {medium_opps} (traffic >50, SEO score <70)")
        print(f"   Low: {low_opps} (everything else)")
        print("="*60 + "\n")
        
        return {
            "updated": updated_count,
            "ga4_matched": ga4_matched,
            "gsc_matched": gsc_matched,
            "high_opportunity": high_opps,
            "medium_opportunity": medium_opps,
            "low_opportunity": low_opps,
            "total_products": len(products),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def get_product_analytics_summary(self) -> Dict:
        """
        Get summary statistics of product analytics.
        """
        products = self.db.query(Product).all()
        
        total_products = len(products)
        if total_products == 0:
            return {
                "total_products": 0,
                "products_with_ga4": 0,
                "products_with_gsc": 0,
                "avg_performance_score": 0,
                "high_opportunity_count": 0,
                "medium_opportunity_count": 0,
                "low_opportunity_count": 0
            }
        
        products_with_ga4 = sum(1 for p in products if p.ga4_sessions > 0)
        products_with_gsc = sum(1 for p in products if p.gsc_impressions > 0)
        
        avg_performance = sum(p.performance_score for p in products) / total_products
        
        high_opps = sum(1 for p in products if p.opportunity_level == 'high')
        medium_opps = sum(1 for p in products if p.opportunity_level == 'medium')
        low_opps = sum(1 for p in products if p.opportunity_level == 'low')
        
        return {
            "total_products": total_products,
            "products_with_ga4": products_with_ga4,
            "products_with_gsc": products_with_gsc,
            "avg_performance_score": round(avg_performance, 1),
            "high_opportunity_count": high_opps,
            "medium_opportunity_count": medium_opps,
            "low_opportunity_count": low_opps
        }
