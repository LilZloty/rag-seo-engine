"""
Backfill missing 301 redirects for products whose handle was changed in the past
without Shopify auto-creating the redirect.

Strategy:
1. Walk generation_history rows with status='previous' — each captures a handle
   that was the live one BEFORE a regeneration push.
2. Look up the product's CURRENT handle in the products table.
3. If old_handle != current_handle, query Shopify to see if a redirect from
   /products/<old_handle> already exists.
4. If not, create the redirect via the REST API.

Run:
    docker exec rag-seo-backend sh -c "cd /app && PYTHONPATH=/app python /tmp/backfill_redirects.py [--dry-run]"
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import Optional

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

from app.db.session import SessionLocal, engine as _engine
_engine.echo = False

from sqlalchemy import text

from app.models.product import Product
from app.services.shopify_service import ShopifyService


def fetch_handle_changes(db) -> list[dict]:
    """All (product_id, old_handle) pairs from generation_history."""
    rows = db.execute(text(
        "SELECT DISTINCT product_id, url_handle, generated_at "
        "FROM generation_history "
        "WHERE status = 'previous' AND url_handle IS NOT NULL AND url_handle != '' "
        "ORDER BY generated_at DESC"
    )).fetchall()
    return [
        {"product_id": r[0], "old_handle": r[1], "generated_at": r[2]}
        for r in rows
    ]


def fetch_redirect_index(svc: ShopifyService) -> set[str]:
    """All existing redirect source paths in Shopify, lowercased."""
    import shopify

    paths: set[str] = set()
    page = None
    pulled = 0
    while True:
        kwargs = {"limit": 250}
        if page:
            kwargs["page_info"] = page
        try:
            batch = shopify.Redirect.find(**kwargs)
        except Exception as e:
            print(f"[redirects] fetch error: {e}", file=sys.stderr)
            break
        if not batch:
            break
        for r in batch:
            paths.add(r.path.lower())
        pulled += len(batch)
        # paginate via next link
        next_link = batch.metadata.get("link", {}).get("next") if hasattr(batch, "metadata") else None
        if not next_link or len(batch) < 250:
            break
        # parse page_info from the link if present
        import re
        m = re.search(r"page_info=([^&>]+)", next_link)
        if not m:
            break
        page = m.group(1)
    print(f"[redirects] indexed {pulled} existing redirects", file=sys.stderr)
    return paths


def create_redirect(old_handle: str, new_handle: str) -> tuple[bool, str]:
    """Create a 301 redirect, return (success, message)."""
    import shopify

    redirect = shopify.Redirect()
    redirect.path = f"/products/{old_handle}"
    redirect.target = f"/products/{new_handle}"
    try:
        ok = redirect.save()
    except Exception as e:
        return (False, f"exception: {e}")
    if ok:
        return (True, "created")
    msgs = redirect.errors.full_messages() if hasattr(redirect, "errors") else []
    if any("taken" in m.lower() or "duplicate" in m.lower() for m in msgs):
        return (True, "already exists")
    return (False, "; ".join(msgs) if msgs else "save returned False")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Don't actually create redirects")
    parser.add_argument("--limit", type=int, default=0, help="Cap on redirects to create (0 = unlimited)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        # Init Shopify (silenced)
        import contextlib
        with contextlib.redirect_stdout(sys.stderr):
            svc = ShopifyService()
            svc._ensure_initialized()

            changes = fetch_handle_changes(db)
            print(f"[history] {len(changes)} previous-state entries in generation_history")

            existing = fetch_redirect_index(svc)

        # Group by product_id, keep the OLDEST 'previous' handle per product
        # (covers the case where a product was renamed multiple times: we want
        # to redirect every old handle to the latest current handle).
        per_product_old_handles: dict[int, set[str]] = {}
        for ch in changes:
            per_product_old_handles.setdefault(ch["product_id"], set()).add(ch["old_handle"])

        # Resolve current handles for these products
        product_ids = list(per_product_old_handles.keys())
        products = db.query(Product).filter(Product.id.in_(product_ids)).all()
        current_handles = {p.id: p.handle for p in products}

        plan: list[tuple[int, str, str]] = []  # (product_id, old, current)
        for pid, old_handles in per_product_old_handles.items():
            current = current_handles.get(pid)
            if not current:
                continue
            for old in old_handles:
                if not old or old == current:
                    continue
                # Skip if redirect already exists
                if f"/products/{old}".lower() in existing:
                    continue
                plan.append((pid, old, current))

        print(f"[plan] {len(plan)} missing redirects to create")
        if args.limit:
            plan = plan[: args.limit]
            print(f"[plan] capped at {len(plan)} for this run")

        # Show first 10 as preview
        for i, (pid, old, current) in enumerate(plan[:10]):
            print(f"  {i+1}. /products/{old} → /products/{current}  (product {pid})")
        if len(plan) > 10:
            print(f"  ... and {len(plan) - 10} more")

        if args.dry_run:
            print("[dry-run] no changes made")
            return 0

        # Execute
        created = 0
        already = 0
        failed = 0
        for i, (pid, old, current) in enumerate(plan):
            ok, msg = create_redirect(old, current)
            if ok and msg == "created":
                created += 1
            elif ok:
                already += 1
            else:
                failed += 1
                print(f"  FAIL {old} → {current}: {msg}")
            # Light throttle to be polite to Shopify (40 calls/sec hard cap on REST)
            if (i + 1) % 20 == 0:
                time.sleep(1)

        print()
        print(f"[done] created={created}  already_existed={already}  failed={failed}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
