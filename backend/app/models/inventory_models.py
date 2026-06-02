"""
Inventory Intelligence Models — Phase 1
Tracks inventory snapshots, alerts, restock events, and raw order line items.
"""
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, Float, Numeric, ForeignKey, Index
from sqlalchemy.sql import func
from app.db.session import Base


class InventorySnapshot(Base):
    """Historical stock level records. One row per product per sync/webhook event."""
    __tablename__ = "inventory_snapshots"
    __table_args__ = (
        Index('ix_inv_snap_product_date', 'product_id', 'snapshot_date'),
    )

    id = Column(String, primary_key=True)
    product_id = Column(String, ForeignKey("products.id"), nullable=False, index=True)
    variant_id = Column(String(50), nullable=True)
    quantity = Column(Integer, nullable=False)
    status = Column(String(20))  # in_stock, out_of_stock, low_stock
    snapshot_date = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    snapshot_type = Column(String(10), default="auto")  # auto (scheduled), webhook, manual


class InventoryAlert(Base):
    """Alert rules and triggered inventory alerts."""
    __tablename__ = "inventory_alerts"

    id = Column(String, primary_key=True)
    alert_type = Column(String(30), nullable=False, index=True)
    # Types: low_stock, out_of_stock, back_in_stock, slow_moving, dead_stock, high_demand_oos
    product_id = Column(String, ForeignKey("products.id"), nullable=True, index=True)
    threshold = Column(Integer, nullable=True)  # e.g., quantity < 5
    message = Column(Text)
    severity = Column(String(10))  # critical, warning, info
    status = Column(String(20), default="active", index=True)  # active, acknowledged, resolved
    triggered_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class RestockEvent(Base):
    """Tracks when a product transitions from OOS back to in-stock."""
    __tablename__ = "restock_events"

    id = Column(String, primary_key=True)
    product_id = Column(String, ForeignKey("products.id"), nullable=False, index=True)
    variant_id = Column(String(50), nullable=True)
    previous_quantity = Column(Integer, default=0)
    new_quantity = Column(Integer, nullable=False)
    subscribers_notified = Column(Integer, default=0)  # Phase 2: filled when notifications sent
    restocked_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class OrderLineItem(Base):
    """
    Raw Shopify order line items — the source of truth for sales aggregates.

    Storing line items individually (instead of aggregating into product counters)
    enables incremental sync (only fetch orders updated since last sync), correct
    aging-out of time windows (a sale automatically leaves the 30d window after
    31 days via WHERE clauses), and richer queries (per-product order history,
    refund tracking, time-series velocity charts).

    Aggregates like sold_30d/90d/365d on Product become a denormalized cache
    refreshed from this table after each incremental sync.
    """
    __tablename__ = "order_line_items"
    __table_args__ = (
        # Critical index: powers all per-product time-window aggregations
        Index('ix_order_line_items_product_date', 'shopify_product_id', 'order_created_at'),
        # Powers incremental sync queries: WHERE order_updated_at > last_sync
        Index('ix_order_line_items_updated_at', 'order_updated_at'),
    )

    id = Column(String, primary_key=True)  # Shopify line_item id (globally unique)
    order_id = Column(String, nullable=False, index=True)  # Shopify order id
    order_name = Column(String(50), nullable=True)  # e.g., "#1042" — for UI display
    shopify_product_id = Column(String, nullable=False, index=True)  # joins to products.shopify_id
    shopify_variant_id = Column(String, nullable=True)
    sku = Column(String(100), nullable=True)
    title = Column(Text, nullable=True)  # Product title at time of sale (preserved for history)

    quantity = Column(Integer, nullable=False, default=0)
    current_quantity = Column(Integer, nullable=False, default=0)  # Post-refund quantity
    unit_price = Column(Numeric(12, 2), nullable=True)
    revenue = Column(Numeric(14, 2), nullable=True)  # quantity * unit_price (cached)

    # Order state — used to exclude cancelled/refunded line items from aggregates
    is_refunded = Column(Boolean, default=False, nullable=False)
    is_cancelled = Column(Boolean, default=False, nullable=False)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps from Shopify (NOT from our DB clock)
    order_created_at = Column(DateTime(timezone=True), nullable=False)
    order_updated_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # Our bookkeeping
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
