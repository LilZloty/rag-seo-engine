"""
Store Intelligence Engine + AI Advisor
Analyzes store data to find issues, opportunities, and generate AI recommendations.
"""
import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid

from app.models.store_intelligence import (
    StoreSnapshot, IntelligenceReport, AIRecommendation,
    CriticalIssue, Opportunity, CorrelationInsight,
    CommerceData, TrafficData, SEOData, GEOData, TechnicalData, ContentData, B2BData
)
from app.models.product import Product
from app.models.aeo_models import FaultCode
from app.services.llm_providers.grok import GrokProvider
from app.services.intelligence.data_hub import StoreDataHub

logger = logging.getLogger("intelligence_engine")


class IntelligenceEngine:
    """
    Analyzes store snapshots to detect issues, opportunities, and patterns.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.data_hub = StoreDataHub(db)
    
    async def generate_report(self, snapshot: StoreSnapshot) -> IntelligenceReport:
        """
        Generate comprehensive intelligence report from snapshot.
        """
        logger.info(f"[IntelligenceEngine] Generating report for snapshot {snapshot.id}")
        
        # Parse snapshot data
        commerce = CommerceData(**snapshot.commerce_data)
        traffic = TrafficData(**snapshot.traffic_data)
        seo = SEOData(**snapshot.seo_data)
        geo = GEOData(**snapshot.geo_data)
        content = ContentData(**snapshot.content_data)
        technical = TechnicalData(**snapshot.technical_data)
        b2b = B2BData(**(snapshot.b2b_data or {}))
        
        # Run all analyses
        critical_issues = self._find_critical_issues(
            commerce, traffic, seo, geo, technical, b2b
        )
        
        opportunities = self._find_opportunities(
            commerce, traffic, seo, geo, content, b2b
        )
        
        trends = self._analyze_trends(snapshot)
        
        anomalies = self._detect_anomalies(
            commerce, traffic, seo, geo
        )
        
        correlations = self._find_correlations(
            commerce, traffic, seo, geo
        )
        
        # Generate executive summary
        executive_summary = self._generate_executive_summary(
            snapshot, critical_issues, opportunities
        )
        
        # Determine weekly focus
        weekly_focus = self._determine_weekly_focus(
            critical_issues, opportunities
        )
        
        # Strategic initiatives (3-month view)
        strategic_initiatives = self._generate_strategic_initiatives(
            snapshot, opportunities
        )
        
        # Create report
        report = IntelligenceReport(
            id=str(uuid.uuid4()),
            snapshot_id=snapshot.id,
            generated_at=datetime.utcnow(),
            
            critical_issues=[issue.dict() for issue in critical_issues],
            opportunities=[opp.dict() for opp in opportunities],
            trends=trends,
            anomalies=anomalies,
            correlations=[corr.dict() for corr in correlations],
            
            executive_summary=executive_summary,
            weekly_focus=weekly_focus,
            strategic_initiatives=strategic_initiatives
        )
        
        self.db.add(report)
        self.db.commit()
        
        logger.info(f"[IntelligenceEngine] Report generated: {report.id}")
        return report
    
    def _find_critical_issues(
        self,
        commerce: CommerceData,
        traffic: TrafficData,
        seo: SEOData,
        geo: GEOData,
        technical: TechnicalData,
        b2b: B2BData = None
    ) -> List[CriticalIssue]:
        """Identify critical issues requiring immediate attention."""
        issues = []
        
        # CRO Issues
        if traffic.purchase_rate < 0.5 and traffic.purchase_rate > 0:
            estimated_loss = (
                traffic.total_sessions * 0.02 * commerce.aov - 
                traffic.total_sessions * traffic.purchase_rate * commerce.aov
            ) if commerce.aov > 0 else 0
            
            issues.append(CriticalIssue(
                category="CRO",
                severity="HIGH",
                title="Conversion Rate Below 0.5%",
                description=f"Current conversion rate is {traffic.purchase_rate:.2f}%. Industry average for automotive parts is 2-3%.",
                impact=f"Estimated revenue loss: ${estimated_loss:.0f}/month",
                action="Audit checkout flow, add trust signals, review pricing strategy",
                estimated_revenue_loss=f"${estimated_loss:.0f}/month"
            ))
        
        if traffic.cart_abandonment_rate > 70:
            issues.append(CriticalIssue(
                category="CRO",
                severity="HIGH",
                title=f"High Cart Abandonment ({traffic.cart_abandonment_rate:.0f}%)",
                description="Most users add to cart but don't complete purchase",
                impact="Significant revenue leak in checkout process",
                action="Add express checkout options, show shipping costs upfront, add trust badges"
            ))
        
        # SEO Issues
        if seo.avg_position > 20:
            issues.append(CriticalIssue(
                category="SEO",
                severity="MEDIUM",
                title=f"Average Ranking Position >20 (Currently: {seo.avg_position:.1f})",
                description="Products are ranking on page 3+ of search results",
                impact="Very low organic visibility - losing to competitors",
                action="Improve content quality, build internal links, optimize technical SEO"
            ))
        
        if seo.avg_ctr < 1.0 and seo.total_clicks > 0:
            issues.append(CriticalIssue(
                category="SEO",
                severity="MEDIUM",
                title=f"Low Click-Through Rate ({seo.avg_ctr:.1f}%)",
                description="Appearing in search results but users aren't clicking",
                impact="Wasted impressions - competitors getting the clicks",
                action="Rewrite meta titles/descriptions to be more compelling, add rich snippets"
            ))
        
        if seo.products_needing_seo > seo.products_optimized:
            issues.append(CriticalIssue(
                category="SEO",
                severity="MEDIUM",
                title=f"{seo.products_needing_seo} Products Need SEO Optimization",
                description="More than half of products haven't been optimized",
                impact="Missing opportunity for organic traffic",
                action="Prioritize top 20 products for content optimization"
            ))
        
        # Inventory Issues
        if commerce.out_of_stock_count > 5:
            issues.append(CriticalIssue(
                category="INVENTORY",
                severity="HIGH",
                title=f"{commerce.out_of_stock_count} Products Out of Stock",
                description="Popular items unavailable for purchase",
                impact="Direct revenue loss and frustrated customers",
                action="Review inventory management, set up automated reordering"
            ))
        
        # Technical Issues
        if technical.cwv_status == 'poor':
            issues.append(CriticalIssue(
                category="TECHNICAL",
                severity="HIGH",
                title="Poor Core Web Vitals",
                description=f"LCP: {technical.lcp:.1f}s, CLS: {technical.cls:.2f} (targets: <2.5s, <0.1)",
                impact="Affects Google rankings and user experience - high bounce rate",
                action="Optimize images, use CDN, reduce server response time"
            ))
        
        if technical.broken_links_count > 10:
            issues.append(CriticalIssue(
                category="TECHNICAL",
                severity="MEDIUM",
                title=f"{technical.broken_links_count} Broken Links Found",
                description="Internal or external links returning 404 errors",
                impact="Poor user experience and wasted crawl budget",
                action="Fix or remove broken links"
            ))
        
        # GEO Issues
        if geo.overall_visibility < 30:
            issues.append(CriticalIssue(
                category="GEO",
                severity="MEDIUM",
                title=f"Low AI Visibility Score ({geo.overall_visibility}/100)",
                description="Not appearing in AI assistant recommendations (ChatGPT, Perplexity, etc.)",
                impact="Missing emerging search channel - competitors gaining visibility",
                action="Enhance llms.txt, publish authoritative technical content, get cited in industry sources"
            ))
        
        # Commerce Issues
        if commerce.total_revenue_30d == 0:
            issues.append(CriticalIssue(
                category="COMMERCE",
                severity="CRITICAL",
                title="No Revenue in Last 30 Days",
                description="Store has generated no sales in the past month",
                impact="Business-critical: immediate action required",
                action="Check store functionality, pricing, payment processing, run promotional campaign"
            ))
        
        if len(commerce.slow_movers) > 20:
            issues.append(CriticalIssue(
                category="COMMERCE",
                severity="LOW",
                title=f"{len(commerce.slow_movers)} Products with No Sales",
                description="Large inventory of slow-moving items",
                impact="Tied-up capital and storage costs",
                action="Consider clearance sale, bundle with popular items, or discontinue"
            ))
        
        # B2B Issues
        if b2b and b2b.total_b2b_customers > 0:
            if b2b.tag_health_pct < 90:
                issues.append(CriticalIssue(
                    category="B2B",
                    severity="HIGH",
                    title=f"{b2b.missing_tags} B2B Customers Missing Tier Tags",
                    description=f"Only {b2b.tag_health_pct:.0f}% of {b2b.total_b2b_customers} B2B clients have correct tier tags. "
                               f"Tier breakdown: {', '.join(f'{k}: {v}' for k, v in b2b.tier_breakdown.items())}",
                    impact="Incorrect pricing, discounts, and customer experience for B2B clients",
                    action="Run tier sync to fix tags: POST /api/v1/tier-sync/sync?dry_run=false"
                ))
            
            if b2b.at_risk_clients > 0:
                issues.append(CriticalIssue(
                    category="B2B",
                    severity="MEDIUM",
                    title=f"{b2b.at_risk_clients} B2B Clients at Risk of Churning",
                    description="These clients haven't placed an order in 60+ days",
                    impact="Potential loss of recurring B2B revenue",
                    action="Reach out with personalized offers or check-in calls"
                ))
        
        return issues
    
    def _find_opportunities(
        self,
        commerce: CommerceData,
        traffic: TrafficData,
        seo: SEOData,
        geo: GEOData,
        content: ContentData,
        b2b: B2BData = None
    ) -> List[Opportunity]:
        """Identify growth opportunities."""
        opportunities = []
        
        # High traffic, low conversion pages
        for page in traffic.top_landing_pages[:5]:
            if page.get('sessions', 0) > 200 and page.get('conversion_rate', 0) < 1.0:
                potential_revenue = page['sessions'] * 0.02 * commerce.aov
                current_revenue = page['sessions'] * (page['conversion_rate']/100) * commerce.aov
                lift = potential_revenue - current_revenue
                
                opportunities.append(Opportunity(
                    category="CRO",
                    title=f"Optimize High-Traffic Page: {page.get('title', 'Unknown')}",
                    description=f"{page.get('sessions', 0)} sessions but only {page.get('conversion_rate', 0):.1f}% conversion",
                    potential_impact=f"+${lift:.0f}/month",
                    effort="1 day",
                    action="Add CTAs, improve product description, add social proof/reviews",
                    priority_score=lift / 8  # Higher score = more impact per effort
                ))
        
        # Low CTR but good position queries
        for query in seo.opportunity_queries[:5]:
            potential_clicks = int(query.get('impressions', 0) * 0.03)  # Target 3% CTR
            current_clicks = int(query.get('impressions', 0) * query.get('ctr', 0))
            lift = potential_clicks - current_clicks
            
            opportunities.append(Opportunity(
                category="SEO",
                title=f"Improve CTR for '{query.get('query', 'Unknown')}'",
                description=f"Position {query.get('position', 0):.0f} but only {query.get('ctr', 0):.1f}% CTR",
                potential_impact=f"+{lift} clicks/month",
                effort="2 hours",
                action="Rewrite meta title/description to be more compelling and relevant",
                priority_score=lift / 2
            ))
        
        # Content gaps
        if content.missing_topics:
            for topic in content.missing_topics[:3]:
                opportunities.append(Opportunity(
                    category="CONTENT",
                    title=f"Create Content: {topic}",
                    description=f"Competitors rank for '{topic}' but you have no content",
                    potential_impact="+50-100 visits/month",
                    effort="1 week",
                    action=f"Write comprehensive guide on {topic}",
                    priority_score=25
                ))
        
        # Fault code opportunities (unique to Example Store)
        # Check for trending fault codes without product links
        fault_codes = self.db.query(
            FaultCode
        ).filter(
            FaultCode.monthly_clicks > 100
        ).order_by(
            FaultCode.monthly_clicks.desc()
        ).limit(5).all()
        
        for fc in fault_codes:
            # Check if we have products for this fault code
            products_exist = self.db.query(Product).filter(
                Product.transmission_code.in_(fc.transmissions or [])
            ).count()
            
            if products_exist > 0:
                opportunities.append(Opportunity(
                    category="AEO",
                    title=f"Create '{fc.code}' Diagnostic Content",
                    description=f"{fc.monthly_clicks} monthly searches for {fc.code}, you have {products_exist} relevant products",
                    potential_impact=f"+{fc.monthly_clicks // 10} visits/month",
                    effort="3 days",
                    action=f"Create blog post: '{fc.code}: {fc.name} - Causas y Soluciones'",
                    priority_score=fc.monthly_clicks / 10
                ))
        
        # GEO opportunity
        if geo.total_citations < 50:
            opportunities.append(Opportunity(
                category="GEO",
                title="Increase AI Citation Coverage",
                description=f"Currently cited in {geo.total_citations} AI responses (target: 100+)",
                potential_impact="+20-30% AI-referred traffic",
                effort="2 weeks",
                action="Publish 5 technical diagnostic guides, update llms.txt with trending topics",
                priority_score=15
            ))
        
        # Bundle opportunity
        if len(commerce.top_products) >= 3:
            opportunities.append(Opportunity(
                category="COMMERCE",
                title="Create 'Complete Repair Kit' Bundles",
                description="Customers buying solenoides often need related parts (filtros, aceite)",
                potential_impact="+15% AOV",
                effort="3 days",
                action="Create bundles for top 5 transmission types with 10% discount",
                priority_score=20
            ))
        
        # B2B Opportunities
        if b2b and b2b.total_b2b_customers > 0:
            # Tier program utilization
            bronce_count = b2b.tier_breakdown.get('Bronce B2B', 0)
            if bronce_count > 100:
                opportunities.append(Opportunity(
                    category="B2B",
                    title=f"Upgrade {bronce_count} Bronce Clients to Higher Tiers",
                    description=f"{bronce_count} clients are in the lowest tier. Target those close to Plata thresholds (3 orders + $20K).",
                    potential_impact="+25% B2B revenue per upgraded client",
                    effort="1 week",
                    action="Identify Bronce clients with 2 orders, send targeted promo to trigger 3rd order",
                    priority_score=30
                ))
            
            platino_count = b2b.tier_breakdown.get('Platino B2B', 0)
            oro_count = b2b.tier_breakdown.get('Oro B2B', 0)
            if platino_count < 15 and oro_count > 10:
                opportunities.append(Opportunity(
                    category="B2B",
                    title=f"Grow Platino Tier from {platino_count} to 15+ Clients",
                    description=f"{oro_count} Oro clients could potentially upgrade to Platino (5+ orders, $100K+).",
                    potential_impact="+$15,000/month from tier upgrades",
                    effort="2 weeks",
                    action="Create VIP incentive program for top Oro clients approaching Platino threshold",
                    priority_score=35
                ))
        
        # Sort by priority score
        opportunities.sort(key=lambda x: x.priority_score, reverse=True)
        
        return opportunities
    
    def _analyze_trends(self, snapshot: StoreSnapshot) -> Dict[str, Any]:
        """Analyze trends by comparing to historical data."""
        trends = {
            'improving': [],
            'declining': [],
            'stable': []
        }
        
        # Get previous snapshot
        previous = self.db.query(StoreSnapshot).filter(
            StoreSnapshot.id != snapshot.id
        ).order_by(
            StoreSnapshot.timestamp.desc()
        ).first()
        
        if not previous:
            return trends
        
        # Compare health scores
        if snapshot.overall_health_score > previous.overall_health_score + 5:
            trends['improving'].append({
                'metric': 'Overall Health',
                'change': f"+{snapshot.overall_health_score - previous.overall_health_score} points",
                'current': snapshot.overall_health_score
            })
        elif snapshot.overall_health_score < previous.overall_health_score - 5:
            trends['declining'].append({
                'metric': 'Overall Health',
                'change': f"{snapshot.overall_health_score - previous.overall_health_score} points",
                'current': snapshot.overall_health_score
            })
        
        # Compare specific metrics
        current_geo = GEOData(**snapshot.geo_data)
        prev_geo = GEOData(**previous.geo_data)
        
        if current_geo.grok_score > prev_geo.grok_score + 10:
            trends['improving'].append({
                'metric': 'Grok AI Visibility',
                'change': f"+{current_geo.grok_score - prev_geo.grok_score} points",
                'current': current_geo.grok_score
            })
        
        return trends
    
    def _detect_anomalies(
        self,
        commerce: CommerceData,
        traffic: TrafficData,
        seo: SEOData,
        geo: GEOData
    ) -> List[Dict[str, Any]]:
        """Detect unusual patterns that may indicate problems or opportunities."""
        anomalies = []
        
        # Unusual traffic spike
        if traffic.total_sessions > 0:  # Would compare to historical average
            pass  # TODO: Implement historical comparison
        
        # Unusual revenue drop
        if commerce.total_revenue_30d == 0 and traffic.total_sessions > 100:
            anomalies.append({
                'type': 'revenue_drop',
                'severity': 'critical',
                'description': 'Traffic present but no revenue - possible checkout issue'
            })
        
        # Sudden SEO position change
        for query in seo.declining_queries[:3]:
            anomalies.append({
                'type': 'ranking_drop',
                'severity': 'medium',
                'description': f"'{query.get('query')}' dropped {query.get('position_change', 0)} positions"
            })
        
        return anomalies
    
    def _find_correlations(
        self,
        commerce: CommerceData,
        traffic: TrafficData,
        seo: SEOData,
        geo: GEOData
    ) -> List[CorrelationInsight]:
        """Find correlations between different metrics."""
        correlations = []
        
        # AI visibility vs Revenue correlation
        if geo.overall_visibility > 0 and commerce.total_revenue_30d > 0:
            # Simplified - in production would calculate actual correlation coefficient
            if geo.overall_visibility > 50 and commerce.total_revenue_30d > 5000:
                correlations.append(CorrelationInsight(
                    insight="Strong AI visibility correlates with higher revenue",
                    metric_1="AI Visibility Score",
                    metric_2="Monthly Revenue",
                    correlation=0.75,
                    recommendation="Prioritize GEO optimization - it directly impacts sales"
                ))
        
        # SEO vs Traffic
        if seo.avg_position < 15 and traffic.total_sessions > 1000:
            correlations.append(CorrelationInsight(
                insight="Good SEO rankings driving significant traffic",
                metric_1="Average Position",
                metric_2="Organic Sessions",
                correlation=0.68,
                recommendation="Continue SEO efforts - each position improvement = more traffic"
            ))
        
        return correlations
    
    def _generate_executive_summary(
        self,
        snapshot: StoreSnapshot,
        issues: List[CriticalIssue],
        opportunities: List[Opportunity]
    ) -> str:
        """Generate human-readable executive summary."""
        health = snapshot.overall_health_score
        trend = snapshot.trend_direction
        
        # Build summary
        if health >= 80:
            status = "excellent"
        elif health >= 60:
            status = "good"
        elif health >= 40:
            status = "needs improvement"
        else:
            status = "critical attention required"
        
        summary_parts = [
            f"Store health is {status} ({health}/100) with {trend} trend."
        ]
        
        if issues:
            high_severity = [i for i in issues if i.severity in ['CRITICAL', 'HIGH']]
            if high_severity:
                summary_parts.append(
                    f"{len(high_severity)} critical issues need immediate attention."
                )
        
        if opportunities:
            top_opp = opportunities[0] if opportunities else None
            if top_opp:
                summary_parts.append(
                    f"Top opportunity: {top_opp.title} could add {top_opp.potential_impact}."
                )
        
        return " ".join(summary_parts)
    
    def _determine_weekly_focus(
        self,
        issues: List[CriticalIssue],
        opportunities: List[Opportunity]
    ) -> List[Dict[str, Any]]:
        """Determine top 3 priorities for this week."""
        focus = []
        
        # Add critical issues first
        for issue in issues[:2]:
            focus.append({
                'type': 'fix',
                'category': issue.category,
                'title': issue.title,
                'action': issue.action,
                'impact': issue.impact,
                'effort': '1-3 days'
            })
        
        # Add top opportunity
        if opportunities and len(focus) < 3:
            opp = opportunities[0]
            focus.append({
                'type': 'opportunity',
                'category': opp.category,
                'title': opp.title,
                'action': opp.action,
                'impact': opp.potential_impact,
                'effort': opp.effort
            })
        
        return focus
    
    def _generate_strategic_initiatives(
        self,
        snapshot: StoreSnapshot,
        opportunities: List[Opportunity]
    ) -> List[Dict[str, Any]]:
        """Generate 3-month strategic initiatives."""
        initiatives = []
        
        # SEO initiative
        seo = SEOData(**snapshot.seo_data)
        if seo.products_needing_seo > 20:
            initiatives.append({
                'title': 'Product Content Optimization Campaign',
                'description': f'Optimize top {min(50, seo.products_needing_seo)} products with AI-generated content',
                'timeline': '3 months',
                'expected_outcome': '+30% organic traffic',
                'resources_needed': '2-3 hours/week'
            })
        
        # CRO initiative
        traffic = TrafficData(**snapshot.traffic_data)
        if traffic.purchase_rate < 1.5:
            initiatives.append({
                'title': 'Conversion Rate Optimization Program',
                'description': 'Systematically improve checkout flow, add trust signals, A/B test',
                'timeline': '2 months',
                'expected_outcome': 'Double conversion rate to 2%+',
                'resources_needed': '1 week initial + monitoring'
            })
        
        # GEO initiative
        geo = GEOData(**snapshot.geo_data)
        if geo.overall_visibility < 50:
            initiatives.append({
                'title': 'AI Search Visibility Program',
                'description': 'Publish 10 technical diagnostic guides, enhance llms.txt, get cited',
                'timeline': '3 months',
                'expected_outcome': 'Visibility score 70+ on all LLMs',
                'resources_needed': '5 hours/week content creation'
            })
        
        return initiatives


class AIAdvisor:
    """
    Uses Grok AI to generate strategic recommendations and insights.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.grok = GrokProvider()
        self.engine = IntelligenceEngine(db)
    
    async def generate_recommendations(
        self,
        report: IntelligenceReport,
        snapshot: StoreSnapshot,
        force_refresh: bool = False
    ) -> List[AIRecommendation]:
        """
        Generate AI-powered recommendations based on intelligence report.
        
        Args:
            report: Intelligence report to base recommendations on
            snapshot: Store snapshot with current data
            force_refresh: If True, regenerate even if recommendations exist
            
        Returns:
            List of AI recommendations (cached or fresh)
        """
        logger.info(f"[AIAdvisor] Checking recommendations for report {report.id}")
        
        # Check if recommendations already exist for this report
        if not force_refresh:
            existing = self.db.query(AIRecommendation).filter(
                AIRecommendation.report_id == report.id
            ).all()
            
            if existing:
                logger.info(f"[AIAdvisor] Returning {len(existing)} cached recommendations")
                return existing
        else:
            logger.info(f"[AIAdvisor] Force refresh requested, clearing old recommendations")
            # Clear old recommendations
            self.db.query(AIRecommendation).filter(
                AIRecommendation.report_id == report.id
            ).delete()
            self.db.commit()
        
        logger.info(f"[AIAdvisor] Generating fresh recommendations with Grok API")
        
        # Build comprehensive prompt
        prompt = self._build_recommendation_prompt(report, snapshot)
        
        try:
            # Call Grok (this costs API tokens)
            response = await self.grok.generate(
                system_prompt=self._get_system_prompt(),
                user_prompt=prompt,
                temperature=0.3,
                json_mode=True
            )
            
            # Parse recommendations
            recommendations = self._parse_ai_response(response, report.id)
            
            # Save to database for caching
            for rec in recommendations:
                self.db.add(rec)
            self.db.commit()
            
            logger.info(f"[AIAdvisor] Generated and saved {len(recommendations)} recommendations")
            return recommendations
            
        except Exception as e:
            logger.error(f"[AIAdvisor] Error generating recommendations: {e}")
            # Try to return any existing recommendations as fallback
            fallback = self.db.query(AIRecommendation).filter(
                AIRecommendation.report_id == report.id
            ).all()
            if fallback:
                logger.info(f"[AIAdvisor] Returning {len(fallback)} stale recommendations as fallback")
                return fallback
            return []
    
    def _build_recommendation_prompt(
        self,
        report: IntelligenceReport,
        snapshot: StoreSnapshot
    ) -> str:
        """Build detailed prompt for AI analysis."""
        
        commerce = CommerceData(**snapshot.commerce_data)
        traffic = TrafficData(**snapshot.traffic_data)
        seo = SEOData(**snapshot.seo_data)
        geo = GEOData(**snapshot.geo_data)
        
        critical_issues = [CriticalIssue(**issue) for issue in report.critical_issues]
        opportunities = [Opportunity(**opp) for opp in report.opportunities]
        
        # Parse B2B data if available
        b2b = B2BData(**(snapshot.b2b_data or {}))
        b2b_section = ""
        if b2b.total_b2b_customers > 0:
            b2b_section = f"""\n## B2B CUSTOMER INTELLIGENCE
- Total B2B Customers: {b2b.total_b2b_customers}
- Tier Breakdown: {', '.join(f'{k}: {v}' for k, v in b2b.tier_breakdown.items())}
- Tag Health: {b2b.tag_health_pct:.0f}% correctly tagged ({b2b.missing_tags} missing)
- At-Risk Clients (60+ days no order): {b2b.at_risk_clients}
- Churned Clients (120+ days): {b2b.churned_clients}
"""
        
        return f"""# STORE INTELLIGENCE REPORT
Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}

## BUSINESS SNAPSHOT
- Revenue (30d): ${commerce.total_revenue_30d:,.2f}
- Orders (30d): {commerce.total_orders_30d}
- AOV: ${commerce.aov:.2f}
- Traffic (30d): {traffic.total_sessions:,} sessions
- Conversion Rate: {traffic.purchase_rate:.2f}%
- Out of Stock: {commerce.out_of_stock_count} products
- Low Stock: {commerce.low_stock_count} products

## SEO PERFORMANCE
- Avg Position: {seo.avg_position:.1f}
- CTR: {seo.avg_ctr:.2f}%
- Indexed Pages: {seo.indexed_pages}
- Products Optimized: {seo.products_optimized}

## AI VISIBILITY (GEO)
- Overall Score: {geo.overall_visibility}/100
- Grok: {geo.grok_score}/100
- Perplexity: {geo.perplexity_score}/100
- LLM Referral Traffic: {geo.llm_referral_sessions} sessions
{b2b_section}
## CRITICAL ISSUES ({len(critical_issues)})
{self._format_issues_for_prompt(critical_issues)}

## TOP OPPORTUNITIES ({len(opportunities)})
{self._format_opportunities_for_prompt(opportunities[:5])}

## BUSINESS CONTEXT
- Industry: Automotive transmission parts (Mexico B2B)
- Target: Mechanics and DIY repair shops
- B2B Tier System: Platino > Oro > Plata > Bronce (based on order count + revenue)
- Unique Advantage: Fault code knowledge graph (P0700, P0706, etc.)
- Current Strength: Technical accuracy, RAG-powered content, automated tier management
- Current Challenge: Growing B2B client base, increasing repeat orders

---

Based on this data, generate 5-7 specific, actionable recommendations.
Include at least 1 B2B/customer-focused recommendation if B2B data is available.

For each recommendation provide:
1. Category (CRO, SEO, GEO, CONTENT, TECHNICAL, COMMERCE, B2B)
2. Priority (CRITICAL, HIGH, MEDIUM, LOW)
3. Title (specific, actionable)
4. Description (context and why it matters)
5. Action Steps (3-5 bullet points)
6. Revenue Impact (e.g., "+$500/month")
7. Traffic Impact (e.g., "+200 sessions/month")
8. Effort Required (e.g., "1 hour", "1 day", "1 week")
9. Confidence Score (0.0-1.0)

Return as JSON array.
"""
    
    def _get_system_prompt(self) -> str:
        """System prompt for AI advisor."""
        return """You are an elite e-commerce strategist and SEO expert specializing in:
- Automotive parts e-commerce in Mexico
- Technical product SEO (fault codes, transmission parts)
- Conversion Rate Optimization (CRO)
- AI Search Optimization (GEO)
- Revenue growth through cross-channel optimization

Your recommendations must be:
1. SPECIFIC: Not "improve SEO" but "Add FAQ schema to products ranking 5-10"
2. PRIORITIZED: Based on effort vs. impact ratio
3. DATA-DRIVEN: Reference specific metrics from the report
4. ACTIONABLE: Clear step-by-step implementation
5. RESULTS-ORIENTED: Estimate revenue/traffic impact in dollars/sessions

Focus on high-leverage activities that compound over time.
Consider Example Store's unique advantages: fault code knowledge, technical accuracy, AEO/GEO systems.

Return ONLY valid JSON. No markdown, no explanations outside JSON."""
    
    def _format_issues_for_prompt(self, issues: List[CriticalIssue]) -> str:
        """Format issues for AI prompt."""
        if not issues:
            return "None"
        return "\n".join([
            f"- [{issue.severity}] {issue.category}: {issue.title}\n  {issue.description}"
            for issue in issues[:5]
        ])
    
    def _format_opportunities_for_prompt(self, opportunities: List[Opportunity]) -> str:
        """Format opportunities for AI prompt."""
        if not opportunities:
            return "None"
        return "\n".join([
            f"- [{opp.category}] {opp.title}\n  Impact: {opp.potential_impact} | Effort: {opp.effort}"
            for opp in opportunities
        ])
    
    def _parse_ai_response(
        self,
        response: Any,
        report_id: str
    ) -> List[AIRecommendation]:
        """Parse AI response into recommendation objects."""
        recommendations = []
        
        if isinstance(response, dict) and 'recommendations' in response:
            items = response['recommendations']
        elif isinstance(response, list):
            items = response
        else:
            logger.warning(f"[AIAdvisor] Unexpected response format: {type(response)}")
            return []
        
        for item in items:
            try:
                rec = AIRecommendation(
                    id=str(uuid.uuid4()),
                    report_id=report_id,
                    category=item.get('category', 'GENERAL'),
                    priority=item.get('priority', 'MEDIUM'),
                    title=item.get('title', 'Untitled Recommendation'),
                    description=item.get('description', ''),
                    action_steps=item.get('action_steps', []),
                    revenue_impact=item.get('revenue_impact', 'Unknown'),
                    traffic_impact=item.get('traffic_impact', 'Unknown'),
                    effort_required=item.get('effort_required', 'Unknown'),
                    confidence_score=float(item.get('confidence_score', 0.5)),
                    status='pending',
                    can_auto_implement=item.get('can_auto_implement', False)
                )
                recommendations.append(rec)
            except Exception as e:
                logger.error(f"[AIAdvisor] Error parsing recommendation: {e}")
                continue
        
        return recommendations
    
    async def generate_weekly_report(
        self,
        days: int = 7
    ) -> Dict[str, Any]:
        """Generate weekly summary report with AI insights."""
        
        # Get latest snapshot
        snapshot = self.data_hub.get_latest_snapshot()
        if not snapshot:
            return {"error": "No snapshot available"}
        
        # Get or generate report
        report = self.db.query(IntelligenceReport).filter(
            IntelligenceReport.snapshot_id == snapshot.id
        ).first()
        
        if not report:
            report = await self.engine.generate_report(snapshot)
        
        # Get recommendations
        recommendations = self.db.query(AIRecommendation).filter(
            AIRecommendation.report_id == report.id
        ).all()
        
        if not recommendations:
            recommendations = await self.generate_recommendations(report, snapshot)
        
        return {
            'period': f'Last {days} days',
            'generated_at': datetime.utcnow().isoformat(),
            'executive_summary': report.executive_summary,
            'health_score': {
                'overall': snapshot.overall_health_score,
                'breakdown': {
                    'commerce': snapshot.commerce_health,
                    'cro': snapshot.cro_health,
                    'seo': snapshot.seo_health,
                    'geo': snapshot.geo_health,
                    'technical': snapshot.technical_health
                },
                'trend': snapshot.trend_direction
            },
            'critical_issues_count': len(report.critical_issues),
            'opportunities_count': len(report.opportunities),
            'top_priorities': report.weekly_focus,
            'ai_recommendations': [
                {
                    'category': rec.category,
                    'priority': rec.priority,
                    'title': rec.title,
                    'impact': rec.revenue_impact,
                    'effort': rec.effort_required
                }
                for rec in recommendations[:5]
            ]
        }


# Convenience functions for API
async def generate_store_intelligence(db: Session, force_refresh: bool = False) -> Tuple[StoreSnapshot, IntelligenceReport, List[AIRecommendation]]:
    """
    Generate complete store intelligence: snapshot, report, and recommendations.
    
    Args:
        db: Database session
        force_refresh: If True, regenerate AI recommendations even if cached
        
    Returns:
        Tuple of (snapshot, report, recommendations)
    """
    # Generate snapshot
    data_hub = StoreDataHub(db)
    snapshot = await data_hub.generate_snapshot()
    
    # Generate intelligence report
    engine = IntelligenceEngine(db)
    report = await engine.generate_report(snapshot)
    
    # Generate AI recommendations (uses cache unless force_refresh=True)
    advisor = AIAdvisor(db)
    recommendations = await advisor.generate_recommendations(report, snapshot, force_refresh=force_refresh)
    
    return snapshot, report, recommendations
