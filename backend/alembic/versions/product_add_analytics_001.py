"""
Add analytics fields to products table for GA4 and Search Console data
Revision ID: product_add_analytics_001
"""

from alembic import op
import sqlalchemy as sa

# Revision identifiers
revision = 'product_add_analytics_001'
down_revision = None  # Update this based on your migration history
branch_labels = None
depends_on = None


def upgrade():
    # GA4 Analytics Fields
    op.add_column('products', sa.Column('ga4_sessions', sa.Integer(), nullable=True, default=0))
    op.add_column('products', sa.Column('ga4_engagement_time', sa.Float(), nullable=True, default=0.0))
    op.add_column('products', sa.Column('ga4_bounce_rate', sa.Float(), nullable=True, default=0.0))
    op.add_column('products', sa.Column('ga4_revenue', sa.Float(), nullable=True, default=0.0))
    
    # Search Console Fields
    op.add_column('products', sa.Column('gsc_impressions', sa.Integer(), nullable=True, default=0))
    op.add_column('products', sa.Column('gsc_clicks', sa.Integer(), nullable=True, default=0))
    op.add_column('products', sa.Column('gsc_ctr', sa.Float(), nullable=True, default=0.0))
    op.add_column('products', sa.Column('gsc_position', sa.Float(), nullable=True, default=0.0))
    
    # Calculated Fields
    op.add_column('products', sa.Column('performance_score', sa.Integer(), nullable=True, default=0))
    op.add_column('products', sa.Column('opportunity_level', sa.String(20), nullable=True, default='low'))
    
    # Timestamps
    op.add_column('products', sa.Column('last_analytics_sync', sa.DateTime(timezone=True), nullable=True))
    
    # Add indexes for frequently queried fields
    op.create_index('ix_products_opportunity_level', 'products', ['opportunity_level'])
    op.create_index('ix_products_performance_score', 'products', ['performance_score'])


def downgrade():
    # Remove indexes
    op.drop_index('ix_products_opportunity_level', table_name='products')
    op.drop_index('ix_products_performance_score', table_name='products')
    
    # Remove columns
    columns_to_remove = [
        'ga4_sessions',
        'ga4_engagement_time',
        'ga4_bounce_rate',
        'ga4_revenue',
        'gsc_impressions',
        'gsc_clicks',
        'gsc_ctr',
        'gsc_position',
        'performance_score',
        'opportunity_level',
        'last_analytics_sync'
    ]
    
    for column in columns_to_remove:
        op.drop_column('products', column)
