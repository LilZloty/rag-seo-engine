"""
Collection Analytics Snapshot Service
=======================================

Creates daily snapshots of collection metrics for trend tracking.
Mirrors the ProductAnalyticsSnapshot pattern.
"""

import uuid
import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.collection_optimizer_models import CollectionOptimizer, CollectionSearchQuery
from app.models.collection_intelligence_models import CollectionAnalyticsSnapshot

logger = logging.getLogger("collection_snapshots")


def create_collection_daily_snapshot(
    db: Session,
    collection_ids: Optional[List[int]] = None
) -> Dict:
    """
    Create daily analytics snapshots for collections.

    Captures current metrics from all 4 data sources (GSC, GA4, Shopify, DataForSEO)
    into a historical snapshot for trend tracking.

    Args:
        db: Database session
        collection_ids: Specific collections to snapshot. If None, snapshots all.

    Returns:
        Summary dict with created/skipped counts.
    """
    today = datetime.utcnow().date()
    created = 0
    skipped = 0

    # Get collections to snapshot
    query = db.query(CollectionOptimizer)
    if collection_ids:
        query = query.filter(CollectionOptimizer.id.in_(collection_ids))

    collections = query.all()

    for collection in collections:
        # Check if snapshot already exists for today
        existing = db.query(CollectionAnalyticsSnapshot).filter(
            and_(
                CollectionAnalyticsSnapshot.collection_id == collection.id,
                CollectionAnalyticsSnapshot.snapshot_date >= datetime.combine(today, datetime.min.time()),
                CollectionAnalyticsSnapshot.snapshot_date < datetime.combine(today + timedelta(days=1), datetime.min.time()),
            )
        ).first()

        if existing:
            skipped += 1
            continue

        # Get top queries for this collection
        top_queries = db.query(CollectionSearchQuery).filter(
            CollectionSearchQuery.collection_id == collection.id
        ).order_by(CollectionSearchQuery.priority_score.desc()).limit(10).all()

        top_queries_json = [
            {
                "query": q.query,
                "clicks": q.clicks,
                "impressions": q.impressions,
                "ctr": float(q.ctr or 0),
                "position": float(q.position or 0),
                "type": q.query_type,
                "intent": q.intent
            }
            for q in top_queries
        ]

        snapshot = CollectionAnalyticsSnapshot(
            id=str(uuid.uuid4()),
            collection_id=collection.id,
            snapshot_date=datetime.utcnow(),

            # GSC
            gsc_impressions=collection.current_impressions or 0,
            gsc_clicks=collection.current_clicks or 0,
            gsc_ctr=float(collection.current_ctr or 0),
            gsc_position=float(collection.current_position or 0),
            gsc_top_queries=top_queries_json,

            # GA4
            ga4_sessions=collection.ga4_sessions or 0,
            ga4_bounce_rate=float(collection.ga4_bounce_rate or 0),
            ga4_engagement_time=float(collection.ga4_avg_engagement_time or 0),
            ga4_conversions=collection.ga4_conversions or 0,
            ga4_conversion_rate=float(collection.ga4_conversion_rate or 0),
            ga4_revenue=float(collection.ga4_revenue or 0),
            ga4_ai_referral_sessions=collection.ga4_ai_referral_sessions or 0,

            # Shopify
            shopify_attributed_revenue=float(collection.shopify_attributed_revenue or 0),
            shopify_attributed_orders=collection.shopify_attributed_orders or 0,
            shopify_llm_revenue=float(collection.shopify_llm_revenue or 0),
            shopify_llm_orders=collection.shopify_llm_orders or 0,

            # DataForSEO
            dataforseo_volume=collection.dataforseo_volume or 0,
            dataforseo_competition=collection.dataforseo_competition,

            # Status
            optimization_status=collection.optimization_status,
            has_content=bool(collection.generated_content),
            snapshot_type='daily'
        )

        db.add(snapshot)
        created += 1

    db.commit()
    logger.info(f"Collection snapshots: {created} created, {skipped} skipped")

    return {
        "created": created,
        "skipped": skipped,
        "total_collections": len(collections),
        "snapshot_date": today.isoformat()
    }


def get_collection_trends(
    db: Session,
    collection_id: int,
    days: int = 30
) -> Dict:
    """
    Get trend data for a collection.

    Returns historical snapshots with computed deltas for
    sparkline charts and before/after analysis.
    """
    collection = db.query(CollectionOptimizer).get(collection_id)
    if not collection:
        raise ValueError(f"Collection {collection_id} not found")

    cutoff = datetime.utcnow() - timedelta(days=days)

    snapshots = db.query(CollectionAnalyticsSnapshot).filter(
        CollectionAnalyticsSnapshot.collection_id == collection_id,
        CollectionAnalyticsSnapshot.snapshot_date >= cutoff
    ).order_by(CollectionAnalyticsSnapshot.snapshot_date.asc()).all()

    if not snapshots:
        return {
            "collection_title": collection.collection_title,
            "snapshots": [],
            "deltas": None,
            "total_snapshots": 0
        }

    # Build sparkline data
    sparkline_data = []
    for s in snapshots:
        sparkline_data.append({
            "date": s.snapshot_date.isoformat() if s.snapshot_date else None,
            "gsc_impressions": s.gsc_impressions,
            "gsc_clicks": s.gsc_clicks,
            "gsc_ctr": s.gsc_ctr,
            "gsc_position": s.gsc_position,
            "ga4_sessions": s.ga4_sessions,
            "ga4_conversions": s.ga4_conversions,
            "ga4_revenue": s.ga4_revenue,
            "ga4_bounce_rate": s.ga4_bounce_rate,
            "shopify_revenue": s.shopify_attributed_revenue,
            "shopify_orders": s.shopify_attributed_orders,
            "dataforseo_volume": s.dataforseo_volume,
            "has_content": s.has_content,
            "optimization_status": s.optimization_status,
        })

    # Compute deltas (first snapshot vs latest)
    first = snapshots[0]
    latest = snapshots[-1]
    deltas = {
        "period_days": days,
        "gsc_impressions_delta": (latest.gsc_impressions or 0) - (first.gsc_impressions or 0),
        "gsc_clicks_delta": (latest.gsc_clicks or 0) - (first.gsc_clicks or 0),
        "gsc_ctr_delta": round((latest.gsc_ctr or 0) - (first.gsc_ctr or 0), 4),
        "gsc_position_delta": round((latest.gsc_position or 0) - (first.gsc_position or 0), 1),
        "ga4_sessions_delta": (latest.ga4_sessions or 0) - (first.ga4_sessions or 0),
        "ga4_conversions_delta": (latest.ga4_conversions or 0) - (first.ga4_conversions or 0),
        "ga4_revenue_delta": round((latest.ga4_revenue or 0) - (first.ga4_revenue or 0), 2),
        "shopify_revenue_delta": round(
            (latest.shopify_attributed_revenue or 0) - (first.shopify_attributed_revenue or 0), 2
        ),
    }

    # Detect if optimization happened during this period
    optimization_events = []
    for i in range(1, len(snapshots)):
        prev = snapshots[i - 1]
        curr = snapshots[i]
        if prev.optimization_status != curr.optimization_status:
            optimization_events.append({
                "date": curr.snapshot_date.isoformat() if curr.snapshot_date else None,
                "from_status": prev.optimization_status,
                "to_status": curr.optimization_status,
            })
        if not prev.has_content and curr.has_content:
            optimization_events.append({
                "date": curr.snapshot_date.isoformat() if curr.snapshot_date else None,
                "event": "content_generated",
            })

    return {
        "collection_title": collection.collection_title,
        "snapshots": sparkline_data,
        "deltas": deltas,
        "optimization_events": optimization_events,
        "total_snapshots": len(snapshots)
    }
