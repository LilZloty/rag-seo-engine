import asyncio
from app.celery_app import celery
from app.db.session import SessionLocal


@celery.task(bind=True, name="sync_analytics_data")
def sync_analytics_data(self):
    """Sync GSC and GA4 data — long-running."""
    from app.services.google_api_service import GoogleApiService

    db = SessionLocal()
    try:
        service = GoogleApiService()
        result = service.sync_performance_data(db)
        return {"status": "completed", "result": result}
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


@celery.task(bind=True, name="refresh_fault_codes_from_gsc")
def refresh_fault_codes_from_gsc(self):
    """Upsert FaultCode rows from the last 30 days of GSC queries.

    Replaces the one-shot hardcoded PRIORITY_FAULT_CODES seed as the source
    of truth for which codes are priorities — they're whichever codes are
    actually driving search traffic this month.
    """
    from app.services.google_api_service import GoogleApiService

    db = SessionLocal()
    try:
        service = GoogleApiService()
        result = service.refresh_fault_codes_from_gsc(db)
        return {"status": "completed", "result": result}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery.task(bind=True, name="refresh_ai_visibility")
def refresh_ai_visibility(self, provider_names: list = None, limit: int = 50):
    """Run AI visibility checks on every active prompt and snapshot the result.

    Uses temperature=0 (set at the service level) so repeated runs against
    the same prompt set produce near-identical scores — week-over-week
    deltas reflect real changes in AI knowledge / your content, not LLM
    sampling variance.

    Scheduled Mondays at 08:00 America/Mexico_City so the AEO dashboard
    reflects the current week's state when the owner starts the week.
    """
    from app.services.ai_visibility_service import AIVisibilityService

    providers = provider_names or ["grok"]
    db = SessionLocal()
    try:
        service = AIVisibilityService()
        batch = asyncio.run(
            service.batch_check_visibility(
                db=db,
                provider_names=providers,
                limit=limit,
                max_concurrent=3,
                timeout_per_check=60,
            )
        )
        snapshot = service.create_daily_snapshot(db)
        return {
            "status": "completed",
            "batch_summary": {
                "total_checks": batch.get("total_checks"),
                "succeeded": batch.get("succeeded"),
                "failed": batch.get("failed"),
                "providers": providers,
            },
            "snapshot": {
                "snapshot_date": snapshot.snapshot_date.isoformat() if snapshot else None,
                "visibility_score": snapshot.visibility_score if snapshot else None,
                "citation_score": snapshot.citation_score if snapshot else None,
            } if snapshot else None,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery.task(bind=True, name="run_dataforseo_batch")
def run_dataforseo_batch(self):
    """Run DataForSEO for all collections — very slow."""
    from app.services.collection_optimizer_service import CollectionOptimizerService

    db = SessionLocal()
    try:
        service = CollectionOptimizerService(db)
        result = asyncio.run(service.run_dataforseo_for_all_collections())
        return {"status": "completed", "result": result}
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


@celery.task(bind=True, name="recalculate_seo_scores")
def recalculate_seo_scores(self):
    """Recalculate SEO scores for all products — long-running."""
    from app.models.product import Product
    from app.services.shopify_service import ShopifyService

    db = SessionLocal()
    try:
        shopify_service = ShopifyService()
        products = db.query(Product).all()
        updated = 0
        total = len(products)

        for i, product in enumerate(products):
            old_score = product.seo_score
            new_score = shopify_service.calculate_seo_score(product)
            if new_score != old_score:
                product.seo_score = new_score
                updated += 1

            if (i + 1) % 100 == 0:
                self.update_state(
                    state="PROGRESS",
                    meta={"current": i + 1, "total": total, "updated": updated},
                )

        db.commit()
        return {"total_products": total, "updated": updated, "unchanged": total - updated}
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


@celery.task(bind=True, name="take_daily_analytics_snapshot")
def take_daily_analytics_snapshot(self):
    """
    Persist a daily snapshot of every product's analytics into product_analytics_snapshots.
    Runs at 06:30 America/Mexico_City — after the analytics sync at 06:00 — so each
    snapshot reflects the freshest GSC + GA4 numbers.
    """
    from app.jobs.analytics_snapshot import create_daily_snapshot

    db = SessionLocal()
    try:
        result = create_daily_snapshot(db=db)
        return result
    finally:
        db.close()


@celery.task(bind=True, name="seo_intelligence_collect")
def seo_intelligence_collect(self):
    """
    Run the SEO Intelligence daily harvest: GSC queries, page metrics, GA4 funnel,
    cannibalization detection, alert generation. Writes to keyword_daily_metrics,
    page_daily_metrics, keyword_page_mappings, ga4_funnel_daily, seo_alerts.
    """
    from app.services.seo_intelligence.daily_collector import DailyCollector
    from app.services.seo_intelligence.alert_service import AlertService

    db = SessionLocal()
    try:
        collector = DailyCollector(db)
        result = collector.run_daily_harvest()
        alert_service = AlertService(db)
        result["alerts_generated"] = alert_service.generate_alerts()
        db.commit()
        return result
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


@celery.task(bind=True, name="recompute_product_priority_scores")
def recompute_product_priority_scores(self):
    """Nightly recompute of priority_score + priority_components for every product.

    Runs after `refresh_and_snapshot_analytics` (06:00) so the score reflects
    the freshest GSC/GA4/sales numbers + the newly-written daily snapshot.

    The score is what powers the Optimization Queue surface on /seo/dashboard.
    """
    from app.services.priority_score import compute_priority_scores_bulk

    db = SessionLocal()
    try:
        summary = compute_priority_scores_bulk(db)
        return {"status": "completed", **summary}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery.task(bind=True, name="derive_ctr_curve")
def derive_ctr_curve_task(self):
    """Derive the position→CTR curve from Example Store's own GSC history and cache it.

    Weekly cadence is deliberate: CTR-per-position is impressions-weighted and
    shifts slowly. Nightly derivation would burn DB cycles on a 4,600-row
    aggregation for near-identical output.
    """
    from app.services.seo_opportunity import build_and_cache_ctr_curve

    db = SessionLocal()
    try:
        payload = build_and_cache_ctr_curve(db)
        return {
            "status": "completed",
            "source": payload["source"],
            "derived_from_count": payload["derived_from_count"],
            "fallback_positions": payload["fallback_positions"],
            "curve_size": len(payload["curve"]),
            "derived_at": payload["derived_at"],
        }
    finally:
        db.close()


@celery.task(bind=True, name="refresh_and_snapshot_analytics")
def refresh_and_snapshot_analytics(self):
    """
    Atomic "fetch fresh + snapshot" pipeline:
      1. Pull GSC + GA4 data into Product fields via ProductService.sync_product_analytics()
      2. Recalculate SEO scores from current HTML (so snapshot reflects fresh score)
      3. Persist a snapshot row per product for trend tracking

    This is what /seo/intelligence's "Refresh & Snapshot" button calls. Also run by
    Celery beat every morning so the dashboard always has fresh data when users arrive.
    """
    import asyncio
    from app.services.product_service import ProductService
    from app.services.shopify_service import ShopifyService
    from app.models.product import Product
    from app.jobs.analytics_snapshot import create_daily_snapshot, backfill_missing_snapshots

    db = SessionLocal()
    try:
        result = {"steps": {}}

        # Step 1: GSC + GA4 → Product fields
        try:
            product_service = ProductService(db)
            sync_result = asyncio.run(product_service.sync_product_analytics())
            result["steps"]["analytics_sync"] = sync_result
        except Exception as e:
            result["steps"]["analytics_sync"] = {"error": str(e)}

        # Step 2: Recalculate SEO scores from HTML (so snapshot reflects fresh score)
        try:
            shopify_service = ShopifyService()
            products = db.query(Product).all()
            updated_scores = 0
            for product in products:
                html = product.current_description_html or ""
                new_score = shopify_service.get_seo_score(html)
                if product.seo_score != new_score:
                    product.seo_score = new_score
                    updated_scores += 1
            db.commit()
            result["steps"]["seo_recalc"] = {"updated": updated_scores, "total": len(products)}
        except Exception as e:
            db.rollback()
            result["steps"]["seo_recalc"] = {"error": str(e)}

        # Step 3: Snapshot the now-fresh values
        try:
            snap_result = create_daily_snapshot(db=db)
            result["steps"]["snapshot"] = snap_result
        except Exception as e:
            result["steps"]["snapshot"] = {"error": str(e)}

        # Step 4 (Gap #12): backfill any missing historical days so beat
        # outages, mid-day product creations, and deploys around 06:00 don't
        # leave permanent holes in the trend. Independent of step 3 — if
        # the daily snapshot errored, the backfill can still patch yesterday.
        try:
            backfill_result = backfill_missing_snapshots(db=db, days_back=30)
            result["steps"]["backfill"] = backfill_result
        except Exception as e:
            result["steps"]["backfill"] = {"error": str(e)}

        return result
    finally:
        db.close()
