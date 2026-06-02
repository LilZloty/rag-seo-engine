from app.celery_app import celery
from app.db.session import SessionLocal


@celery.task(bind=True, name="sync_shopify_products")
def sync_shopify_products(self, min_description_length: int = 300):
    """Sync all products from Shopify — long-running."""
    from datetime import datetime as dt
    from app.models.product import Product
    from app.services.shopify_service import ShopifyService

    db = SessionLocal()
    try:
        shopify_service = ShopifyService()
        shopify_products = shopify_service.get_all_products()
        total = len(shopify_products)

        # Pre-load all existing products in one query (avoids N+1)
        existing_map = {
            p.shopify_id: p
            for p in db.query(Product).all()
        }

        synced = 0
        updated = 0

        for i, sp in enumerate(shopify_products):
            shopify_id = str(sp.id)
            desc_html = sp.body_html or ""
            desc_length = len(desc_html)
            has_structure = shopify_service._has_seo_structure(desc_html)
            needs_seo = desc_length < min_description_length or not has_structure

            # Collect primary SKU from first variant
            primary_sku = ""
            if hasattr(sp, "variants") and sp.variants:
                for v in sp.variants:
                    if v.sku:
                        primary_sku = v.sku
                        break

            # Parse timestamps
            shopify_created_at = None
            shopify_updated_at = None
            if hasattr(sp, "created_at") and sp.created_at:
                try:
                    shopify_created_at = dt.fromisoformat(sp.created_at.replace("Z", "+00:00"))
                except Exception:
                    pass
            if hasattr(sp, "updated_at") and sp.updated_at:
                try:
                    shopify_updated_at = dt.fromisoformat(sp.updated_at.replace("Z", "+00:00"))
                except Exception:
                    pass

            # Parse price
            price = None
            if hasattr(sp, "variants") and sp.variants:
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
                existing.vendor = getattr(sp, "vendor", None)
                existing.image_count = len(sp.images) if hasattr(sp, "images") else 0
                existing.needs_seo = needs_seo
                existing.seo_status = "needs_seo" if needs_seo else "published"
                existing.shopify_created_at = shopify_created_at
                existing.shopify_updated_at = shopify_updated_at
                existing.sku = primary_sku
                if price is not None:
                    existing.price = price
                updated += 1
            else:
                # Add ALL products (not just ones needing SEO)
                product = Product(
                    id=shopify_id,
                    shopify_id=shopify_id,
                    sku=primary_sku,
                    title=sp.title,
                    handle=sp.handle,
                    product_type=sp.product_type,
                    vendor=getattr(sp, "vendor", None),
                    current_description_html=desc_html,
                    image_count=len(sp.images) if hasattr(sp, "images") else 0,
                    needs_seo=needs_seo,
                    seo_status="needs_seo" if needs_seo else "published",
                    shopify_created_at=shopify_created_at,
                    shopify_updated_at=shopify_updated_at,
                    price=price,
                )
                db.add(product)
                synced += 1

            # Report progress every 50 products
            if (i + 1) % 50 == 0:
                self.update_state(
                    state="PROGRESS",
                    meta={"current": i + 1, "total": total, "synced": synced, "updated": updated},
                )

        db.commit()

        # Phase 1.5: refresh transmission_codes after sync so freshly imported
        # or title-edited products immediately have correct codes. Runs after
        # commit so a failure here doesn't roll back the sync.
        try:
            from app.services.aeo.knowledge_graph import create_knowledge_graph_manager
            kg = create_knowledge_graph_manager(db)
            refreshed = kg.update_product_transmission_codes(force_recompute=True)
            print(f"[sync_shopify_products] Refreshed transmission_codes on {refreshed} products")
        except Exception as _kg_err:
            print(f"[sync_shopify_products] transmission_codes refresh failed: {_kg_err}")

        from app.services.redis_service import cache
        cache.invalidate_pattern("api:products:list:*")
        cache.invalidate("products:segment_counts")

        return {
            "new_products": synced,
            "updated_products": updated,
            "total_in_shopify": total,
            "total_in_database": synced + updated + len(existing_map),
            "message": f"Sync complete — {synced} new, {updated} updated",
        }
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


@celery.task(bind=True, name="sync_sales_data")
def sync_sales_data(self):
    """
    Sync sales data from Shopify orders — long-running.
    Delegates to InventoryService.sync_sales_data() so all callers (API endpoint,
    Celery scheduler, manual triggers) share the same logic: capturing last_sold_at,
    recomputing tier/velocity/demand/urgency, and resetting counters for products
    that fell out of the 365d window.
    """
    from app.services.inventory_service import InventoryService
    from app.services.redis_service import cache

    db = SessionLocal()
    try:
        service = InventoryService(db)
        result = service.sync_sales_data()
        cache.invalidate_pattern("api:products:list:*")
        cache.invalidate("products:segment_counts")
        return {
            "message": "Sales data synced",
            "products_updated": result.get("sales_updated", 0),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery.task(bind=True, name="sync_product_analytics")
def sync_product_analytics(self):
    """Sync GA4 and Search Console data — long-running."""
    import asyncio
    from app.services.product_service import ProductService
    from app.services.redis_service import cache

    db = SessionLocal()
    try:
        service = ProductService(db)
        result = asyncio.run(service.sync_product_analytics())
        cache.invalidate_pattern("api:products:list:*")
        cache.invalidate("products:segment_counts")
        return result
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()
