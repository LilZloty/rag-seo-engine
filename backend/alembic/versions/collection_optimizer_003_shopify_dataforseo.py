"""
Add Shopify attribution and DataForSEO fields to collection_optimizer table
Revision ID: collection_optimizer_003
"""

from alembic import op
import sqlalchemy as sa

# Revision identifiers
revision = 'collection_optimizer_003'
down_revision = 'collection_optimizer_002'
branch_labels = None
depends_on = None


def upgrade():
    # --- Shopify Attribution ---
    op.add_column('collection_optimizer', sa.Column('shopify_attributed_revenue', sa.Float(), nullable=True))
    op.add_column('collection_optimizer', sa.Column('shopify_attributed_orders', sa.Integer(), nullable=True))
    op.add_column('collection_optimizer', sa.Column('shopify_llm_revenue', sa.Float(), nullable=True))
    op.add_column('collection_optimizer', sa.Column('shopify_llm_orders', sa.Integer(), nullable=True))
    op.add_column('collection_optimizer', sa.Column('last_shopify_sync', sa.DateTime(), nullable=True))

    # --- DataForSEO ---
    op.add_column('collection_optimizer', sa.Column('dataforseo_primary_keyword', sa.String(), nullable=True))
    op.add_column('collection_optimizer', sa.Column('dataforseo_volume', sa.Integer(), nullable=True))
    op.add_column('collection_optimizer', sa.Column('dataforseo_competition', sa.String(), nullable=True))
    op.add_column('collection_optimizer', sa.Column('dataforseo_cpc', sa.Float(), nullable=True))
    op.add_column('collection_optimizer', sa.Column('dataforseo_top_competitor', sa.String(), nullable=True))
    op.add_column('collection_optimizer', sa.Column('dataforseo_serp_features', sa.JSON(), nullable=True))
    op.add_column('collection_optimizer', sa.Column('dataforseo_people_also_ask', sa.JSON(), nullable=True))
    op.add_column('collection_optimizer', sa.Column('dataforseo_last_sync', sa.DateTime(), nullable=True))


def downgrade():
    columns_to_remove = [
        'shopify_attributed_revenue',
        'shopify_attributed_orders',
        'shopify_llm_revenue',
        'shopify_llm_orders',
        'last_shopify_sync',
        'dataforseo_primary_keyword',
        'dataforseo_volume',
        'dataforseo_competition',
        'dataforseo_cpc',
        'dataforseo_top_competitor',
        'dataforseo_serp_features',
        'dataforseo_people_also_ask',
        'dataforseo_last_sync',
    ]
    for column in columns_to_remove:
        op.drop_column('collection_optimizer', column)
