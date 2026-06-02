"""
SQLAlchemy event listeners.

These hook into the ORM lifecycle to record events that the application doesn't
explicitly emit. Currently used to log manual product edits as GenerationHistory
rows so the SEO Intelligence dashboard can attribute metric changes to the edit
that caused them — even when the edit didn't go through the AI generator.

Imported by app.models.__init__ at startup so listeners auto-register.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import event, inspect

from app.models.product import Product
from app.models.library import GenerationHistory


# Fields that count as a "meaningful optimization edit" worth tracking.
# Editing tags, vendor, or stock fields is NOT an SEO change and shouldn't
# create a row — that would flood the table with noise.
TRACKED_FIELDS = {
    "current_description_html",
    "title",
    "handle",
    # Note: Product doesn't directly store meta_title/meta_description — those live
    # on ContentDraft when generated through the AI flow. If you start storing them
    # on Product directly, add them here.
}


@event.listens_for(Product, "before_update", propagate=True)
def _log_manual_product_edit(mapper, connection, target):
    """
    Inspect a Product about to be updated. If any of the SEO-meaningful fields
    changed, queue a GenerationHistory row tagged as 'manual_edit'.

    We use INSERT directly via the connection (not the ORM session) because
    we're inside a flush. Mixing the ORM session here can cause re-entrant flush
    errors. Direct connection.execute is safe.
    """
    state = inspect(target)
    changed = []
    for field in TRACKED_FIELDS:
        attr = state.attrs.get(field)
        if attr is None:
            continue
        history = attr.history
        if history.has_changes() and history.deleted:
            old_val = history.deleted[0] if history.deleted else None
            new_val = history.added[0] if history.added else None
            # Skip if both are effectively empty / equal (None vs empty string, etc.)
            if (old_val or "") == (new_val or ""):
                continue
            changed.append(field)

    if not changed:
        return

    # Skip noise from internal sync flows: if the only thing happening is a fresh
    # sync from Shopify with `seo_status` flipping or analytics fields updating,
    # we don't want a manual_edit row. So check that ONLY tracked fields changed,
    # and that the change isn't part of a bulk Shopify resync (no easy heuristic
    # for this — for now we accept the noise; can add a flag later).

    # Build the new row payload directly via connection so we don't disturb the
    # active session's flush cycle.
    new_h1 = getattr(target, "title", None) or None
    new_handle = getattr(target, "handle", None) or None
    description_html = getattr(target, "current_description_html", None) or None

    row = {
        "id": str(uuid.uuid4()),
        "product_id": target.id,
        "h1_title": (new_h1 or "")[:255] if new_h1 else None,
        "url_handle": (new_handle or "")[:255] if new_handle else None,
        "description_html": description_html,
        "llm_used": "manual",
        "status": "manual_edit",
        "published_at": datetime.now(timezone.utc) if "current_description_html" in changed else None,
        "published_to_shopify": False,
        # Pack the list of changed fields into prompts_used so the dashboard can
        # show "this edit changed: title, handle" without a new column.
        "prompts_used": changed,
        "libraries_used": [],
        "image_types": [],
        "documents_retrieved": [],
        "chunks_retrieved": [],
        "alt_tags": [],
    }

    connection.execute(
        GenerationHistory.__table__.insert().values(**row)
    )


def register_listeners():
    """Idempotent — registration happens at import time. This function exists
    so callers can confirm listeners loaded (e.g. in tests or startup logs)."""
    return True
