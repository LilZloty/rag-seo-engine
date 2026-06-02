"""
Store Intelligence API Endpoints
Provides unified store analytics, health scores, and AI recommendations.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from app.db.session import get_db
from app.models.store_intelligence import (
    StoreSnapshot, IntelligenceReport, AIRecommendation,
    StoreSnapshotResponse, IntelligenceReportResponse, 
    AIRecommendationResponse, StoreHealthGauge
)
from app.models.product import Product
from app.models.seo_intelligence import KeywordDailyMetric, SEOAlert, GA4FunnelDaily
from app.services.intelligence.data_hub import StoreDataHub, get_store_data_hub
from app.services.intelligence.intelligence_engine import (
    IntelligenceEngine, AIAdvisor, generate_store_intelligence
)
from app.services.redis_service import cache

router = APIRouter(prefix="/intelligence", tags=["Store Intelligence"])


# ============================================================================
# SNAPSHOT ENDPOINTS
# ============================================================================

@router.post("/snapshot/generate", response_model=StoreSnapshotResponse)
async def generate_snapshot(
    background_tasks: BackgroundTasks,
    force_refresh: bool = False,
    db: Session = Depends(get_db)
):
    """
    Generate a new store snapshot by aggregating all data sources.
    
    - **force_refresh**: Ignore cache and fetch fresh data
    - Returns complete snapshot with all metrics
    """
    try:
        data_hub = StoreDataHub(db)
        snapshot = await data_hub.generate_snapshot(force_refresh=force_refresh)
        
        return StoreSnapshotResponse(
            id=snapshot.id,
            timestamp=snapshot.timestamp,
            commerce=snapshot.commerce_data,
            traffic=snapshot.traffic_data,
            seo=snapshot.seo_data,
            geo=snapshot.geo_data,
            content=snapshot.content_data,
            technical=snapshot.technical_data,
            health_scores={
                'overall': snapshot.overall_health_score,
                'commerce': snapshot.commerce_health,
                'cro': snapshot.cro_health,
                'seo': snapshot.seo_health,
                'geo': snapshot.geo_health,
                'technical': snapshot.technical_health
            },
            trend=snapshot.trend_direction
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate snapshot: {str(e)}")


@router.get("/snapshot/latest", response_model=StoreSnapshotResponse)
async def get_latest_snapshot(db: Session = Depends(get_db)):
    """Get the most recent store snapshot."""
    data_hub = StoreDataHub(db)
    snapshot = data_hub.get_latest_snapshot()
    
    if not snapshot:
        raise HTTPException(status_code=404, detail="No snapshots found")
    
    return StoreSnapshotResponse(
        id=snapshot.id,
        timestamp=snapshot.timestamp,
        commerce=snapshot.commerce_data,
        traffic=snapshot.traffic_data,
        seo=snapshot.seo_data,
        geo=snapshot.geo_data,
        content=snapshot.content_data,
        technical=snapshot.technical_data,
        health_scores={
            'overall': snapshot.overall_health_score,
            'commerce': snapshot.commerce_health,
            'cro': snapshot.cro_health,
            'seo': snapshot.seo_health,
            'geo': snapshot.geo_health,
            'technical': snapshot.technical_health
        },
        trend=snapshot.trend_direction
    )


@router.get("/snapshot/history")
async def get_snapshot_history(
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Get historical snapshots for trend analysis."""
    data_hub = StoreDataHub(db)
    trends = data_hub.get_historical_trends(days=days)
    return {
        'period': f'{days} days',
        'snapshots': trends
    }


# ============================================================================
# HEALTH SCORE ENDPOINTS
# ============================================================================

@router.get("/health", response_model=StoreHealthGauge)
async def get_health_score(db: Session = Depends(get_db)):
    """
    Get current store health score with breakdown.
    
    Returns overall score (0-100) and category breakdowns:
    - Commerce: Sales, inventory, AOV
    - CRO: Conversion rate, funnel metrics
    - SEO: Rankings, CTR, indexation
    - GEO: AI visibility, citations
    - Technical: Core Web Vitals, site health
    """
    data_hub = StoreDataHub(db)
    snapshot = data_hub.get_latest_snapshot()
    
    if not snapshot:
        raise HTTPException(status_code=404, detail="No health data available")
    
    return StoreHealthGauge(
        overall=snapshot.overall_health_score,
        trend=snapshot.trend_direction,
        breakdown={
            'commerce': snapshot.commerce_health,
            'cro': snapshot.cro_health,
            'seo': snapshot.seo_health,
            'geo': snapshot.geo_health,
            'technical': snapshot.technical_health
        },
        last_updated=snapshot.timestamp
    )


@router.get("/health/trends")
async def get_health_trends(
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Get health score trends over time."""
    data_hub = StoreDataHub(db)
    trends = data_hub.get_historical_trends(days=days)
    
    return {
        'period': f'{days} days',
        'data': trends,
        'summary': {
            'current': trends[-1] if trends else None,
            'change_7d': trends[-1]['overall'] - trends[-8]['overall'] if len(trends) >= 8 else 0,
            'change_30d': trends[-1]['overall'] - trends[0]['overall'] if len(trends) > 1 else 0
        }
    }


# ============================================================================
# INTELLIGENCE REPORT ENDPOINTS
# ============================================================================

@router.post("/report/generate", response_model=IntelligenceReportResponse)
async def generate_intelligence_report(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Generate complete intelligence report with:
    - Critical issues analysis
    - Opportunity identification
    - Trend analysis
    - Cross-channel correlations
    - Executive summary
    """
    try:
        # Generate snapshot first
        data_hub = StoreDataHub(db)
        snapshot = await data_hub.generate_snapshot()
        
        # Generate intelligence report
        engine = IntelligenceEngine(db)
        report = await engine.generate_report(snapshot)
        
        return IntelligenceReportResponse(
            id=report.id,
            snapshot_id=report.snapshot_id,
            generated_at=report.generated_at,
            executive_summary=report.executive_summary,
            store_health={
                'overall': snapshot.overall_health_score,
                'breakdown': {
                    'commerce': snapshot.commerce_health,
                    'cro': snapshot.cro_health,
                    'seo': snapshot.seo_health,
                    'geo': snapshot.geo_health,
                    'technical': snapshot.technical_health
                }
            },
            critical_issues=report.critical_issues,
            opportunities=report.opportunities,
            correlations=report.correlations,
            weekly_focus=report.weekly_focus,
            strategic_initiatives=report.strategic_initiatives
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.get("/report/latest", response_model=IntelligenceReportResponse)
async def get_latest_report(db: Session = Depends(get_db)):
    """Get the most recent intelligence report."""
    report = db.query(IntelligenceReport).order_by(
        IntelligenceReport.generated_at.desc()
    ).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="No reports found")
    
    # Get associated snapshot
    snapshot = db.query(StoreSnapshot).filter(
        StoreSnapshot.id == report.snapshot_id
    ).first()
    
    return IntelligenceReportResponse(
        id=report.id,
        snapshot_id=report.snapshot_id,
        generated_at=report.generated_at,
        executive_summary=report.executive_summary,
        store_health={
            'overall': snapshot.overall_health_score if snapshot else 0,
            'breakdown': {
                'commerce': snapshot.commerce_health if snapshot else 0,
                'cro': snapshot.cro_health if snapshot else 0,
                'seo': snapshot.seo_health if snapshot else 0,
                'geo': snapshot.geo_health if snapshot else 0,
                'technical': snapshot.technical_health if snapshot else 0
            }
        },
        critical_issues=report.critical_issues,
        opportunities=report.opportunities,
        correlations=report.correlations,
        weekly_focus=report.weekly_focus,
        strategic_initiatives=report.strategic_initiatives
    )


# ============================================================================
# AI RECOMMENDATIONS ENDPOINTS
# ============================================================================

@router.post("/recommendations/generate", response_model=List[AIRecommendationResponse])
async def generate_recommendations(
    background_tasks: BackgroundTasks,
    force_refresh: bool = False,
    db: Session = Depends(get_db)
):
    """
    Generate AI-powered recommendations using Grok.
    
    - Uses cached recommendations if available (saves API costs)
    - Set force_refresh=true to regenerate (costs API tokens)
    
    Provides:
    - Prioritized action items
    - Revenue/traffic impact estimates
    - Effort required
    - Step-by-step implementation
    """
    try:
        # Generate full intelligence
        snapshot, report, recommendations = await generate_store_intelligence(db, force_refresh=force_refresh)
        
        return [
            AIRecommendationResponse(
                id=rec.id,
                category=rec.category,
                priority=rec.priority,
                title=rec.title,
                description=rec.description,
                action_steps=rec.action_steps,
                revenue_impact=rec.revenue_impact,
                traffic_impact=rec.traffic_impact,
                effort_required=rec.effort_required,
                confidence_score=rec.confidence_score,
                status=rec.status,
                can_auto_implement=rec.can_auto_implement
            )
            for rec in recommendations
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate recommendations: {str(e)}")


@router.get("/recommendations", response_model=List[AIRecommendationResponse])
async def get_recommendations(
    status: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    Get AI recommendations with filtering.
    
    - **status**: pending, in_progress, completed, dismissed
    - **category**: CRO, SEO, GEO, CONTENT, TECHNICAL, COMMERCE
    - **priority**: CRITICAL, HIGH, MEDIUM, LOW
    """
    query = db.query(AIRecommendation)
    
    if status:
        query = query.filter(AIRecommendation.status == status)
    if category:
        query = query.filter(AIRecommendation.category == category)
    if priority:
        query = query.filter(AIRecommendation.priority == priority)
    
    recommendations = query.order_by(
        AIRecommendation.created_at.desc()
    ).limit(limit).all()
    
    return [
        AIRecommendationResponse(
            id=rec.id,
            category=rec.category,
            priority=rec.priority,
            title=rec.title,
            description=rec.description,
            action_steps=rec.action_steps,
            revenue_impact=rec.revenue_impact,
            traffic_impact=rec.traffic_impact,
            effort_required=rec.effort_required,
            confidence_score=rec.confidence_score,
            status=rec.status,
            can_auto_implement=rec.can_auto_implement
        )
        for rec in recommendations
    ]


@router.patch("/recommendations/{recommendation_id}/status")
async def update_recommendation_status(
    recommendation_id: str,
    status: str,
    db: Session = Depends(get_db)
):
    """Update recommendation status (pending, in_progress, completed, dismissed)."""
    rec = db.query(AIRecommendation).filter(
        AIRecommendation.id == recommendation_id
    ).first()
    
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    
    rec.status = status
    if status == 'completed':
        rec.implemented_at = datetime.utcnow()
    
    db.commit()
    
    return {"message": f"Recommendation status updated to {status}"}


# ============================================================================
# DASHBOARD SUMMARY ENDPOINT
# ============================================================================

@router.get("/dashboard")
async def get_dashboard_summary(db: Session = Depends(get_db)):
    """
    Get complete dashboard summary in one call.

    Returns:
    - Health scores
    - Critical issues (top 5)
    - Opportunities (top 5)
    - AI recommendations (top 5)
    - Weekly focus
    """
    # Check cache first (10 min TTL)
    cached = cache.get("intelligence:dashboard")
    if cached:
        return cached

    # Get latest snapshot
    data_hub = StoreDataHub(db)
    snapshot = data_hub.get_latest_snapshot()
    
    if not snapshot:
        raise HTTPException(status_code=404, detail="No data available")
    
    # Get latest report
    report = db.query(IntelligenceReport).order_by(
        IntelligenceReport.generated_at.desc()
    ).first()
    
    # Get recommendations
    recommendations = db.query(AIRecommendation).filter(
        AIRecommendation.status == 'pending'
    ).order_by(
        AIRecommendation.confidence_score.desc()
    ).limit(5).all()
    
    # Extract score details from snapshot data
    score_details = {
        'commerce': snapshot.commerce_data.get('score_details', {}),
        'cro': snapshot.traffic_data.get('score_details', {}),
        'seo': snapshot.seo_data.get('score_details', {}),
        'geo': snapshot.geo_data.get('score_details', {}),
        'technical': snapshot.technical_data.get('score_details', {})
    }
    
    result = {
        'generated_at': datetime.utcnow().isoformat(),
        'health': {
            'overall': snapshot.overall_health_score,
            'trend': snapshot.trend_direction,
            'breakdown': {
                'commerce': snapshot.commerce_health,
                'cro': snapshot.cro_health,
                'seo': snapshot.seo_health,
                'geo': snapshot.geo_health,
                'technical': snapshot.technical_health
            },
            'details': score_details
        },
        'summary': report.executive_summary if report else None,
        'critical_issues': report.critical_issues[:5] if report else [],
        'opportunities': report.opportunities[:5] if report else [],
        'weekly_focus': report.weekly_focus if report else [],
        'ai_recommendations': [
            {
                'id': rec.id,
                'category': rec.category,
                'priority': rec.priority,
                'title': rec.title,
                'impact': rec.revenue_impact,
                'effort': rec.effort_required
            }
            for rec in recommendations
        ],
        'quick_stats': {
            'total_products': db.query(Product).count(),
            'products_optimized': db.query(Product).filter(
                Product.seo_status == 'published'
            ).count(),
            'pending_recommendations': db.query(AIRecommendation).filter(
                AIRecommendation.status == 'pending'
            ).count()
        },
        'seo_data': _get_seo_intelligence_preview(db),
        'traffic_data': {**snapshot.traffic_data, 'cro_preview': _get_cro_preview(db)}
    }
    cache.set("intelligence:dashboard", result, ttl=600)
    return result


def _get_seo_intelligence_preview(db: Session) -> dict:
    """Get real-time SEO Intelligence preview data directly from tables."""
    preview = {
        'intelligence_preview': {
            'keywords_tracked': 0,
            'keywords_improving': 0,
            'keywords_declining': 0,
            'open_alerts': 0,
            'ctr_opportunities': 0,
            'potential_clicks': 0,
            'last_collection': None,
            'has_data': False
        }
    }
    
    try:
        # Get latest keyword data
        latest_date = db.query(KeywordDailyMetric.date).order_by(
            KeywordDailyMetric.date.desc()
        ).first()
        
        if latest_date and latest_date[0]:
            preview['intelligence_preview']['last_collection'] = latest_date[0].isoformat()
            preview['intelligence_preview']['has_data'] = True
            
            keywords = db.query(KeywordDailyMetric).filter(
                KeywordDailyMetric.date == latest_date[0]
            ).all()
            
            preview['intelligence_preview']['keywords_tracked'] = len(keywords)
            preview['intelligence_preview']['keywords_improving'] = sum(
                1 for k in keywords if k.position_change_7d is not None and k.position_change_7d < -0.5
            )
            preview['intelligence_preview']['keywords_declining'] = sum(
                1 for k in keywords if k.position_change_7d is not None and k.position_change_7d > 0.5
            )
            preview['intelligence_preview']['ctr_opportunities'] = sum(
                1 for k in keywords if k.is_underperforming
            )
            preview['intelligence_preview']['potential_clicks'] = sum(
                int(k.impressions * abs(k.ctr_gap)) 
                for k in keywords if k.is_underperforming and k.ctr_gap
            )
        
        preview['intelligence_preview']['open_alerts'] = db.query(SEOAlert).filter(
            SEOAlert.status == 'open'
        ).count()
        
    except Exception as e:
        print(f"Error getting SEO preview: {e}")
    
    return preview


def _get_cro_preview(db: Session) -> dict:
    """Get real-time CRO preview data directly from GA4 funnel tables."""
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
        from datetime import date
        since = date.today() - timedelta(days=7)
        
        funnel_data = db.query(GA4FunnelDaily).filter(
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
        device_data = db.query(GA4FunnelDaily).filter(
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
                data['share'] = (data['sessions'] / total_sessions * 100) if total_sessions > 0 else 0
                data['conversion'] = (data['purchases'] / data['sessions'] * 100) if data['sessions'] > 0 else 0
            
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
                preview['biggest_dropoff'] = {'step': min_drop[0], 'rate': round(min_drop[1], 1)}
        
    except Exception as e:
        print(f"Error getting CRO preview: {e}")
    
    return preview


# ============================================================================
# WEEKLY REPORT ENDPOINT
# ============================================================================

@router.get("/report/weekly")
async def get_weekly_report(
    days: int = 7,
    db: Session = Depends(get_db)
):
    """Get weekly summary report with AI insights."""
    advisor = AIAdvisor(db)
    return await advisor.generate_weekly_report(days=days)


# ============================================================================
# CRO TECHNICAL ANALYSIS ENDPOINT
# ============================================================================

@router.get("/cro-technical-report")
async def get_cro_technical_report(
    days: int = 30,
    db: Session = Depends(get_db)
):
    """
    Get detailed CRO technical analysis report.
    
    Includes:
    - Core Web Vitals (LCP, FID, CLS)
    - Page speed analysis
    - Checkout funnel breakdown
    - Device performance comparison
    - Friction points identification
    - Technical recommendations
    """
    try:
        from app.services.cro_technical_analyzer import CROTechnicalAnalyzer
        
        analyzer = CROTechnicalAnalyzer(db)
        report = await analyzer.generate_technical_report(days=days)
        
        return report
        
    except Exception as e:
        import traceback
        print(f"[ERROR] CRO technical report failed: {e}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to generate CRO technical report: {str(e)}")


# ============================================================================
# SCHEDULED TASK ENDPOINTS
# ============================================================================

@router.post("/scheduled/generate-all")
async def generate_all_intelligence(
    background_tasks: BackgroundTasks,
    force_refresh: bool = False,
    db: Session = Depends(get_db)
):
    """
    Generate complete intelligence (snapshot + report + recommendations).
    Intended for scheduled execution (e.g., daily at 6 AM).
    
    - Generates new snapshot and report always (data changes)
    - Uses cached AI recommendations unless force_refresh=true (saves API costs)
    """
    import traceback
    try:
        snapshot, report, recommendations = await generate_store_intelligence(db, force_refresh=force_refresh)
        
        return {
            'success': True,
            'snapshot_id': snapshot.id,
            'report_id': report.id,
            'recommendations_count': len(recommendations),
            'health_score': snapshot.overall_health_score,
            'generated_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        error_msg = f"Scheduled generation failed: {str(e)}"
        print(f"[ERROR] {error_msg}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_msg)
