"""
Analytics Snapshot Job

Creates daily snapshots of product analytics for historical trend tracking.
Run this job daily via cron, scheduler, or manual trigger.

Usage:
    python -m app.jobs.analytics_snapshot
    or
    POST /api/v1/analytics/snapshots/create
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import uuid

from app.db.session import SessionLocal
from app.models.product import Product, ProductAnalyticsSnapshot


def create_daily_snapshot(db: Session = None, product_ids: List[str] = None) -> Dict[str, Any]:
    """
    Create or refresh today's analytics snapshots for products.

    Behavior: UPSERT — if a snapshot already exists for today (UTC day boundary),
    its values are REFRESHED with the current Product fields. This means calling
    this function multiple times on the same day (e.g. via the "Refresh & Snapshot"
    button) progressively improves the snapshot as upstream data settles
    (GSC/GA4 sync, SEO score recalculation, etc.).

    Args:
        db: Database session (optional, creates new if not provided)
        product_ids: Specific products to snapshot (optional, all if not provided)

    Returns:
        {status, created, updated, total_products, timestamp}
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # Query products
        query = db.query(Product)
        if product_ids:
            query = query.filter(Product.id.in_(product_ids))

        products = query.all()
        created_count = 0
        updated_count = 0
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        for product in products:
            # Check if snapshot already exists for today
            existing = db.query(ProductAnalyticsSnapshot).filter(
                ProductAnalyticsSnapshot.product_id == product.id,
                ProductAnalyticsSnapshot.snapshot_date >= today_start
            ).first()

            if existing:
                # REFRESH the existing snapshot with current Product values
                existing.snapshot_date = datetime.utcnow()  # touch the timestamp
                existing.sold_30d = product.sold_30d or 0
                existing.revenue_30d = product.revenue_30d or 0.0
                existing.sold_90d = product.sold_90d or 0
                existing.revenue_90d = product.revenue_90d or 0.0
                existing.sold_365d = product.sold_365d or 0
                existing.revenue_365d = product.revenue_365d or 0.0
                existing.ga4_sessions = product.ga4_sessions or 0
                existing.ga4_engagement_time = product.ga4_engagement_time or 0.0
                existing.ga4_bounce_rate = product.ga4_bounce_rate or 0.0
                existing.ga4_revenue = product.ga4_revenue or 0.0
                existing.gsc_impressions = product.gsc_impressions or 0
                existing.gsc_clicks = product.gsc_clicks or 0
                existing.gsc_ctr = product.gsc_ctr or 0.0
                existing.gsc_position = product.gsc_position or 0.0
                existing.performance_score = product.performance_score or 0
                existing.seo_score = getattr(product, 'seo_score', 0) or 0
                # Shopify product state — captured so we can detect non-content
                # changes (price moves, stockouts) that otherwise get silently
                # blamed on the most recent content edit
                existing.price = product.price
                existing.inventory_quantity = product.inventory_quantity
                existing.image_count = product.image_count or 0
                existing.description_length = product.description_length or 0
                updated_count += 1
                continue

            # Create new snapshot
            snapshot = ProductAnalyticsSnapshot(
                id=str(uuid.uuid4()),
                product_id=product.id,
                snapshot_date=datetime.utcnow(),
                snapshot_type='daily',

                # Sales metrics — 30d/90d/365d for signal vs noise separation
                sold_30d=product.sold_30d or 0,
                revenue_30d=product.revenue_30d or 0.0,
                sold_90d=product.sold_90d or 0,
                revenue_90d=product.revenue_90d or 0.0,
                sold_365d=product.sold_365d or 0,
                revenue_365d=product.revenue_365d or 0.0,

                # GA4 metrics
                ga4_sessions=product.ga4_sessions or 0,
                ga4_engagement_time=product.ga4_engagement_time or 0.0,
                ga4_bounce_rate=product.ga4_bounce_rate or 0.0,
                ga4_revenue=product.ga4_revenue or 0.0,

                # Search Console metrics
                gsc_impressions=product.gsc_impressions or 0,
                gsc_clicks=product.gsc_clicks or 0,
                gsc_ctr=product.gsc_ctr or 0.0,
                gsc_position=product.gsc_position or 0.0,

                # Calculated scores
                performance_score=product.performance_score or 0,
                seo_score=getattr(product, 'seo_score', 0) or 0,

                # Shopify product state (overlap detection)
                price=product.price,
                inventory_quantity=product.inventory_quantity,
                image_count=product.image_count or 0,
                description_length=product.description_length or 0,
            )

            db.add(snapshot)
            created_count += 1

        db.commit()

        return {
            "status": "success",
            "created": created_count,
            "updated": updated_count,
            "skipped": 0,  # legacy field — we no longer skip
            "total_products": len(products),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        db.rollback()
        return {
            "status": "error",
            "error": str(e),
            "created": 0
        }
    finally:
        if close_db:
            db.close()


def backfill_missing_snapshots(
    db: Session = None,
    days_back: int = 30,
    product_ids: List[str] = None,
) -> Dict[str, Any]:
    """Gap #12 — fill historical gaps in product_analytics_snapshots.

    For each product, find days in the last `days_back` window that have no
    snapshot row and create one using the product's current values. The
    snapshot is dated to the missing day (not today) so trend dashboards
    that group by date treat it as historical. snapshot_type='backfill'
    lets downstream consumers tell these apart from organic daily rows.

    Why this exists: the 06:00 Celery beat task is the only thing that
    creates snapshots. If the worker is down, deploys happen across the
    schedule boundary, or a product is created mid-day, that day's row
    is permanently lost — which leaves visible holes in trend charts and
    breaks overlap-attribution windowing in /seo/intelligence.

    Trade-off: backfilled rows use *current* metrics applied to *past*
    dates. They aren't a true reconstruction — GSC's 2–3 day lag means
    we genuinely don't know what the position was on day N. They are a
    "this product existed and looked roughly like this" approximation,
    which is still better than a NULL row that the dashboards have to
    special-case.

    Args:
        db: Database session (optional, creates new if not provided).
        days_back: Lookback window in days. Defaults to 30. Going further
            back than the daily refresh granularity (~30d) inflates row
            counts without adding signal.
        product_ids: Restrict backfill to these product IDs (optional).
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        window_start = today_start - timedelta(days=days_back)

        product_query = db.query(Product)
        if product_ids:
            product_query = product_query.filter(Product.id.in_(product_ids))
        products = product_query.all()
        if not products:
            return {
                "status": "success",
                "backfilled": 0,
                "products_touched": 0,
                "days_back": days_back,
                "window_start": window_start.isoformat(),
                "timestamp": datetime.utcnow().isoformat(),
            }

        # Load every snapshot in window in one query, then index by (product_id, date).
        existing_query = db.query(
            ProductAnalyticsSnapshot.product_id,
            ProductAnalyticsSnapshot.snapshot_date,
        ).filter(ProductAnalyticsSnapshot.snapshot_date >= window_start)
        if product_ids:
            existing_query = existing_query.filter(
                ProductAnalyticsSnapshot.product_id.in_(product_ids)
            )

        existing_days: set = set()
        for row in existing_query.all():
            pid, snap_dt = row[0], row[1]
            existing_days.add((pid, snap_dt.date()))

        backfilled_count = 0
        products_touched = 0
        # Days we expect rows for: every day from window_start (inclusive) to
        # *yesterday* (inclusive). Today is left to create_daily_snapshot so
        # this function never collides with the live snapshot logic.
        expected_days = [
            (today_start - timedelta(days=offset)).date()
            for offset in range(1, days_back + 1)
        ]

        for product in products:
            missing_days = [d for d in expected_days if (product.id, d) not in existing_days]
            if not missing_days:
                continue
            products_touched += 1
            for day in missing_days:
                # Date the snapshot to *noon UTC* of the missing day. Avoids
                # the day-boundary ambiguity that bites the create_daily_snapshot
                # path (it uses utcnow which can land at 23:59:59 of the wrong
                # day depending on transaction timing).
                snap_dt = datetime.combine(day, datetime.min.time()).replace(hour=12)
                snapshot = ProductAnalyticsSnapshot(
                    id=str(uuid.uuid4()),
                    product_id=product.id,
                    snapshot_date=snap_dt,
                    snapshot_type='backfill',
                    sold_30d=product.sold_30d or 0,
                    revenue_30d=product.revenue_30d or 0.0,
                    sold_90d=product.sold_90d or 0,
                    revenue_90d=product.revenue_90d or 0.0,
                    sold_365d=product.sold_365d or 0,
                    revenue_365d=product.revenue_365d or 0.0,
                    ga4_sessions=product.ga4_sessions or 0,
                    ga4_engagement_time=product.ga4_engagement_time or 0.0,
                    ga4_bounce_rate=product.ga4_bounce_rate or 0.0,
                    ga4_revenue=product.ga4_revenue or 0.0,
                    gsc_impressions=product.gsc_impressions or 0,
                    gsc_clicks=product.gsc_clicks or 0,
                    gsc_ctr=product.gsc_ctr or 0.0,
                    gsc_position=product.gsc_position or 0.0,
                    performance_score=product.performance_score or 0,
                    seo_score=getattr(product, 'seo_score', 0) or 0,
                    price=product.price,
                    inventory_quantity=product.inventory_quantity,
                    image_count=product.image_count or 0,
                    description_length=product.description_length or 0,
                )
                db.add(snapshot)
                backfilled_count += 1

        db.commit()

        return {
            "status": "success",
            "backfilled": backfilled_count,
            "products_touched": products_touched,
            "products_scanned": len(products),
            "days_back": days_back,
            "window_start": window_start.isoformat(),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        db.rollback()
        return {
            "status": "error",
            "error": str(e),
        }
    finally:
        if close_db:
            db.close()


def cleanup_old_snapshots(days_to_keep: int = 90, db: Session = None) -> Dict[str, Any]:
    """
    Delete snapshots older than specified days.
    
    Args:
        days_to_keep: Number of days of snapshots to keep
        db: Database session (optional)
    
    Returns:
        Number of deleted snapshots
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        deleted = db.query(ProductAnalyticsSnapshot).filter(
            ProductAnalyticsSnapshot.snapshot_date < cutoff_date
        ).delete()
        
        db.commit()
        
        return {
            "status": "success",
            "deleted": deleted,
            "cutoff_date": cutoff_date.isoformat()
        }
        
    except Exception as e:
        db.rollback()
        return {
            "status": "error",
            "error": str(e)
        }
    finally:
        if close_db:
            db.close()


if __name__ == "__main__":
    print("Creating daily analytics snapshots...")
    result = create_daily_snapshot()
    print(f"Result: {result}")
