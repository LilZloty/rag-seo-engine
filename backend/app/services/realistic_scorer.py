"""
Realistic Store Intelligence Scoring
No more fake 100/100 scores - this is harsh but accurate.
"""
import logging
from typing import Dict, List, Any
from datetime import datetime

logger = logging.getLogger("realistic_scoring")


class RealisticStoreScorer:
    """
    Scores store health based on ACTUAL performance, not potential.
    
    A small store with 150 visits/month should NEVER score 100/100.
    Amazon scores 100/100. You don't. And that's OK.
    """
    
    @staticmethod
    def score_commerce(commerce_data: Dict) -> Dict:
        """
        Real commerce scoring based on actual sales performance.
        
        100/100 = $100k+/month, 1000+ orders
        50/100 = $10k/month, 100 orders  
        0/100 = $0/month
        """
        revenue = commerce_data.get('total_revenue_30d', 0)
        orders = commerce_data.get('total_orders_30d', 0)
        aov = commerce_data.get('aov', 0)
        
        # Revenue score (logarithmic - harder to get high scores)
        # $0 = 0, $1k = 20, $10k = 40, $50k = 60, $100k = 80, $500k+ = 100
        if revenue < 1000:
            revenue_score = int(revenue / 50)  # $0-1000 = 0-20
        elif revenue < 10000:
            revenue_score = 20 + int((revenue - 1000) / 400)  # $1k-10k = 20-40
        elif revenue < 50000:
            revenue_score = 40 + int((revenue - 10000) / 1000)  # $10k-50k = 40-80
        else:
            revenue_score = min(100, 80 + int((revenue - 50000) / 10000))  # $50k+ = 80-100
        
        # Order volume score
        # 0 orders = 0, 10 = 10, 50 = 30, 100 = 50, 500 = 80, 1000+ = 100
        if orders < 10:
            order_score = orders  # 0-10 orders = 0-10 points
        elif orders < 50:
            order_score = 10 + int((orders - 10) / 2)  # 10-50 = 10-30
        elif orders < 100:
            order_score = 30 + int((orders - 50) / 2.5)  # 50-100 = 30-50
        elif orders < 500:
            order_score = 50 + int((orders - 100) / 12.5)  # 100-500 = 50-80
        else:
            order_score = min(100, 80 + int((orders - 500) / 25))  # 500+ = 80-100
        
        # AOV score (is it healthy?)
        aov_score = 50  # Default
        if aov >= 80:
            aov_score = 80
        elif aov >= 50:
            aov_score = 60
        elif aov >= 30:
            aov_score = 40
        elif aov > 0:
            aov_score = 20
        
        # Weighted average
        final_score = int(revenue_score * 0.5 + order_score * 0.35 + aov_score * 0.15)
        
        return {
            'score': final_score,
            'breakdown': {
                'revenue_performance': revenue_score,
                'order_volume': order_score,
                'aov_health': aov_score
            },
            'raw_data': {
                'revenue_30d': revenue,
                'orders_30d': orders,
                'aov': aov
            },
            'assessment': RealisticStoreScorer._assess_commerce(final_score, revenue, orders)
        }
    
    @staticmethod
    def _assess_commerce(score: int, revenue: float, orders: int) -> str:
        """Honest assessment, not fake positivity."""
        if score < 20:
            return f"CRITICAL: Only ${revenue:.0f} revenue, {orders} orders. Store is barely alive."
        elif score < 40:
            return f"STRUGGLING: ${revenue:.0f}/month isn't sustainable. Need 10x growth."
        elif score < 60:
            return f"BUILDING: ${revenue:.0f}/month is OK but not great. 5x to be healthy."
        elif score < 80:
            return f"GROWING: ${revenue:.0f}/month is solid. Keep pushing."
        else:
            return f"STRONG: ${revenue:.0f}/month is excellent performance."
    
    @staticmethod
    def score_cro(cro_data: Dict) -> Dict:
        """
        Real CRO scoring.
        
        Most stores are 0.5-2%, not 5%.
        """
        conversion_rate = cro_data.get('conversion_rate', 0)
        cart_abandonment = cro_data.get('cart_abandonment_rate', 70)
        sessions = cro_data.get('sessions', 0)
        orders = cro_data.get('orders', 0)
        is_estimated = cro_data.get('is_estimated', True)
        
        # Conversion rate score (realistic scale)
        # <0.5% = 0-20 (broken)
        # 0.5-1% = 20-40 (poor)
        # 1-2% = 40-60 (average)
        # 2-3% = 60-80 (good)
        # 3%+ = 80-100 (excellent)
        if conversion_rate < 0.5:
            conv_score = int(conversion_rate * 40)  # 0-0.5% = 0-20
        elif conversion_rate < 1.0:
            conv_score = 20 + int((conversion_rate - 0.5) * 40)  # 0.5-1% = 20-40
        elif conversion_rate < 2.0:
            conv_score = 40 + int((conversion_rate - 1.0) * 20)  # 1-2% = 40-60
        elif conversion_rate < 3.0:
            conv_score = 60 + int((conversion_rate - 2.0) * 20)  # 2-3% = 60-80
        else:
            conv_score = min(100, 80 + int((conversion_rate - 3.0) * 10))  # 3%+ = 80-100
        
        # Cart abandonment (inverse - lower is better)
        # 90%+ = 0, 80% = 20, 70% = 40, 60% = 60, 50% = 80, 40% = 100
        abandon_score = max(0, 100 - int((cart_abandonment - 40) * 2))
        
        # Volume check (low volume = less reliable data)
        if sessions < 100:
            volume_penalty = 20  # Small sample size, less reliable
        elif sessions < 500:
            volume_penalty = 10
        else:
            volume_penalty = 0
        
        final_score = max(0, int(conv_score * 0.7 + abandon_score * 0.3) - volume_penalty)
        
        return {
            'score': final_score,
            'is_estimated': is_estimated,
            'breakdown': {
                'conversion_performance': conv_score,
                'cart_recovery': abandon_score,
                'volume_penalty': -volume_penalty
            },
            'raw_data': {
                'conversion_rate': conversion_rate,
                'cart_abandonment': cart_abandonment,
                'sessions': sessions,
                'orders': orders
            },
            'assessment': RealisticStoreScorer._assess_cro(final_score, conversion_rate, is_estimated, sessions)
        }
    
    @staticmethod
    def _assess_cro(score: int, conversion: float, is_estimated: bool, sessions: int) -> str:
        """Honest CRO assessment."""
        if is_estimated:
            return f"⚠️ ESTIMATED: ~{conversion:.1f}% conversion (GA4 not connected). Real rate unknown."
        
        if sessions < 100:
            return f"LOW DATA: Only {sessions} sessions. Need 1000+ for reliable CRO analysis."
        
        if score < 20:
            return f"BROKEN: {conversion:.1f}% conversion. Something is seriously wrong."
        elif score < 40:
            return f"POOR: {conversion:.1f}% conversion. Major issues to fix."
        elif score < 60:
            return f"AVERAGE: {conversion:.1f}% conversion. Room for improvement."
        elif score < 80:
            return f"GOOD: {conversion:.1f}% conversion. Above average."
        else:
            return f"EXCELLENT: {conversion:.1f}% conversion. Top performer."
    
    @staticmethod
    def score_seo(seo_data: Dict) -> Dict:
        """
        Real SEO scoring based on actual rankings and traffic.
        """
        avg_position = seo_data.get('avg_position', 50)
        ctr = seo_data.get('avg_ctr', 0)
        optimized_products = seo_data.get('products_optimized', 0)
        total_products = seo_data.get('indexed_pages', 100)
        clicks = seo_data.get('total_clicks', 0)
        
        # Position score (lower is better)
        # Position 1-3 = 100, 4-10 = 80, 11-20 = 60, 21-30 = 40, 31-50 = 20, 50+ = 0
        if avg_position <= 3:
            pos_score = 100
        elif avg_position <= 10:
            pos_score = 80
        elif avg_position <= 20:
            pos_score = 60
        elif avg_position <= 30:
            pos_score = 40
        elif avg_position <= 50:
            pos_score = 20
        else:
            pos_score = 10
        
        # CTR score
        # >5% = 100, 3-5% = 80, 2-3% = 60, 1-2% = 40, <1% = 20
        if ctr >= 5:
            ctr_score = 100
        elif ctr >= 3:
            ctr_score = 80
        elif ctr >= 2:
            ctr_score = 60
        elif ctr >= 1:
            ctr_score = 40
        else:
            ctr_score = 20
        
        # Coverage score (% of products optimized)
        coverage_pct = (optimized_products / total_products * 100) if total_products > 0 else 0
        coverage_score = min(100, int(coverage_pct))
        
        # Traffic volume (absolute numbers matter)
        if clicks > 10000:
            volume_score = 100
        elif clicks > 1000:
            volume_score = 80
        elif clicks > 500:
            volume_score = 60
        elif clicks > 100:
            volume_score = 40
        elif clicks > 0:
            volume_score = 20
        else:
            volume_score = 0
        
        final_score = int(pos_score * 0.3 + ctr_score * 0.2 + coverage_score * 0.3 + volume_score * 0.2)
        
        return {
            'score': final_score,
            'breakdown': {
                'rankings': pos_score,
                'click_through_rate': ctr_score,
                'content_coverage': coverage_score,
                'traffic_volume': volume_score
            },
            'raw_data': {
                'avg_position': avg_position,
                'ctr': ctr,
                'products_optimized': optimized_products,
                'total_products': total_products,
                'monthly_clicks': clicks
            },
            'assessment': RealisticStoreScorer._assess_seo(final_score, avg_position, clicks, coverage_pct)
        }
    
    @staticmethod
    def _assess_seo(score: int, position: float, clicks: int, coverage: float) -> str:
        """Honest SEO assessment."""
        if score < 20:
            return f"INVISIBLE: Position {position:.0f}, {clicks} clicks. Google doesn't know you exist."
        elif score < 40:
            return f"WEAK: Position {position:.0f}, {clicks} clicks. Page 3+ of results."
        elif score < 60:
            return f"BUILDING: Position {position:.0f}, {clicks} clicks. Page 2, need more content."
        elif score < 80:
            return f"SOLID: Position {position:.0f}, {clicks} clicks. Page 1 for some terms."
        else:
            return f"STRONG: Position {position:.0f}, {clicks} clicks. Dominating search."
    
    @staticmethod
    def score_geo(geo_data: Dict) -> Dict:
        """
        Real GEO/AI visibility scoring.
        
        0 citations = 0/100
        This is realistic - AI doesn't know most small stores exist.
        """
        grok_score = geo_data.get('grok_score', 0)
        openai_score = geo_data.get('openai_score', 0)
        perplexity_score = geo_data.get('perplexity_score', 0)
        total_citations = geo_data.get('total_citations', 0)
        llm_traffic = geo_data.get('llm_referral_sessions', 0)
        
        # LLM scores (already 0-100)
        llm_avg = (grok_score + openai_score + perplexity_score) / 3
        
        # Citations score
        if total_citations > 100:
            cite_score = 100
        elif total_citations > 50:
            cite_score = 80
        elif total_citations > 20:
            cite_score = 60
        elif total_citations > 5:
            cite_score = 40
        elif total_citations > 0:
            cite_score = 20
        else:
            cite_score = 0
        
        # Traffic score
        if llm_traffic > 1000:
            traffic_score = 100
        elif llm_traffic > 500:
            traffic_score = 80
        elif llm_traffic > 100:
            traffic_score = 60
        elif llm_traffic > 10:
            traffic_score = 40
        elif llm_traffic > 0:
            traffic_score = 20
        else:
            traffic_score = 0
        
        final_score = int(llm_avg * 0.5 + cite_score * 0.3 + traffic_score * 0.2)
        
        return {
            'score': final_score,
            'breakdown': {
                'llm_scores_avg': int(llm_avg),
                'citation_volume': cite_score,
                'referral_traffic': traffic_score
            },
            'raw_data': {
                'grok': grok_score,
                'openai': openai_score,
                'perplexity': perplexity_score,
                'total_citations': total_citations,
                'llm_sessions': llm_traffic
            },
            'assessment': RealisticStoreScorer._assess_geo(final_score, total_citations, llm_traffic)
        }
    
    @staticmethod
    def _assess_geo(score: int, citations: int, traffic: int) -> str:
        """Honest GEO assessment."""
        if score < 10:
            return f"INVISIBLE TO AI: {citations} citations, {traffic} AI visits. ChatGPT doesn't know you exist."
        elif score < 30:
            return f"BARELY THERE: {citations} citations. Occasionally mentioned by AI."
        elif score < 50:
            return f"EMERGING: {citations} citations, {traffic} AI visits. Starting to appear."
        elif score < 70:
            return f"KNOWN: {citations} citations. AI recommends you sometimes."
        else:
            return f"AI FAVORITE: {citations} citations, {traffic} AI visits. Dominating AI search."
    
    @staticmethod
    def score_technical(technical_data: Dict) -> Dict:
        """
        Technical SEO scoring.
        """
        cwv_status = technical_data.get('cwv_status', 'unknown')
        schema_coverage = technical_data.get('schema_coverage_pct', 0)
        broken_links = technical_data.get('broken_links_count', 0)
        
        # Core Web Vitals
        if cwv_status == 'good':
            cwv_score = 100
        elif cwv_status == 'needs_improvement':
            cwv_score = 60
        elif cwv_status == 'poor':
            cwv_score = 20
        else:
            cwv_score = 50  # Unknown
        
        # Schema coverage
        schema_score = min(100, int(schema_coverage))
        
        # Health check (no broken links = good)
        if broken_links == 0:
            health_score = 100
        elif broken_links < 10:
            health_score = 80
        elif broken_links < 50:
            health_score = 60
        else:
            health_score = 40
        
        final_score = int(cwv_score * 0.4 + schema_score * 0.4 + health_score * 0.2)
        
        return {
            'score': final_score,
            'breakdown': {
                'core_web_vitals': cwv_score,
                'schema_coverage': schema_score,
                'site_health': health_score
            },
            'raw_data': {
                'cwv_status': cwv_status,
                'schema_coverage': schema_coverage,
                'broken_links': broken_links
            },
            'assessment': RealisticStoreScorer._assess_technical(final_score, cwv_status, broken_links)
        }
    
    @staticmethod
    def _assess_technical(score: int, cwv: str, broken: int) -> str:
        """Honest technical assessment."""
        if score >= 80:
            return f"TECHNICALLY SOUND: {cwv} CWV, {broken} broken links."
        elif score >= 60:
            return f"OK BUT NEEDS WORK: {cwv} CWV, {broken} broken links to fix."
        elif score >= 40:
            return f"PROBLEMATIC: {cwv} CWV, {broken} broken links. Hurting rankings."
        else:
            return f"BROKEN: {cwv} CWV, {broken} broken links. Fix immediately."
    
    @classmethod
    def calculate_all_scores(cls, data: Dict) -> Dict:
        """Calculate all scores realistically."""
        return {
            'commerce': cls.score_commerce(data.get('commerce', {})),
            'cro': cls.score_cro(data.get('cro', {})),
            'seo': cls.score_seo(data.get('seo', {})),
            'geo': cls.score_geo(data.get('geo', {})),
            'technical': cls.score_technical(data.get('technical', {}))
        }
