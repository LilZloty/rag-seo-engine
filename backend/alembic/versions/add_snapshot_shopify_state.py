"""
Add price/inventory/image/description columns to product_analytics_snapshots

Revision ID: add_snapshot_shopify_state
down_revision: add_seo_score_to_products
"""

from alembic import op
import sqlalchemy as sa


revision = 'add_snapshot_shopify_state'
down_revision = 'add_seo_score_to_products'
branch_labels = None
depends_on = None


def upgrade():
    # Capture Shopify product state in daily snapshots so we can detect
    # non-content changes (price moves, stockouts, image swaps) that would
    # otherwise be misattributed to the most recent content edit.
    op.add_column('product_analytics_snapshots',
                  sa.Column('price', sa.String(length=20), nullable=True))
    op.add_column('product_analytics_snapshots',
                  sa.Column('inventory_quantity', sa.Integer(), nullable=True))
    op.add_column('product_analytics_snapshots',
                  sa.Column('image_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('product_analytics_snapshots',
                  sa.Column('description_length', sa.Integer(), nullable=True, server_default='0'))


def downgrade():
    op.drop_column('product_analytics_snapshots', 'description_length')
    op.drop_column('product_analytics_snapshots', 'image_count')
    op.drop_column('product_analytics_snapshots', 'inventory_quantity')
    op.drop_column('product_analytics_snapshots', 'price')
