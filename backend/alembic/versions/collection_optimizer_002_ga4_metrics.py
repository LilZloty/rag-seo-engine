"""
Add GA4 metrics to collection_optimizer table
Revision ID: collection_optimizer_002
"""

from alembic import op
import sqlalchemy as sa

# Revision identifiers
revision = 'collection_optimizer_002'
down_revision = 'collection_optimizer_001'
branch_labels = None
depends_on = None


def upgrade():
    # Add GA4 engagement metrics
    op.add_column('collection_optimizer', sa.Column('ga4_sessions', sa.Integer(), nullable=True, default=0))
    op.add_column('collection_optimizer', sa.Column('ga4_bounce_rate', sa.Float(), nullable=True, default=0.0))
    op.add_column('collection_optimizer', sa.Column('ga4_avg_engagement_time', sa.Float(), nullable=True, default=0.0))
    
    # Add GA4 conversion metrics
    op.add_column('collection_optimizer', sa.Column('ga4_conversions', sa.Integer(), nullable=True, default=0))
    op.add_column('collection_optimizer', sa.Column('ga4_conversion_rate', sa.Float(), nullable=True, default=0.0))
    op.add_column('collection_optimizer', sa.Column('ga4_revenue', sa.Float(), nullable=True, default=0.0))
    
    # Add AI/GEO tracking
    op.add_column('collection_optimizer', sa.Column('ga4_ai_referral_sessions', sa.Integer(), nullable=True, default=0))
    op.add_column('collection_optimizer', sa.Column('ga4_ai_referral_conversions', sa.Integer(), nullable=True, default=0))
    
    # Add baseline GA4 metrics for comparison
    op.add_column('collection_optimizer', sa.Column('baseline_ga4_sessions', sa.Integer(), nullable=True, default=0))
    op.add_column('collection_optimizer', sa.Column('baseline_ga4_conversions', sa.Integer(), nullable=True, default=0))
    op.add_column('collection_optimizer', sa.Column('baseline_ga4_revenue', sa.Float(), nullable=True, default=0.0))
    op.add_column('collection_optimizer', sa.Column('baseline_ga4_date', sa.DateTime(), nullable=True))
    
    # Add last GA4 sync timestamp
    op.add_column('collection_optimizer', sa.Column('last_ga4_sync', sa.DateTime(), nullable=True))


def downgrade():
    # Remove GA4 columns
    columns_to_remove = [
        'ga4_sessions',
        'ga4_bounce_rate',
        'ga4_avg_engagement_time',
        'ga4_conversions',
        'ga4_conversion_rate',
        'ga4_revenue',
        'ga4_ai_referral_sessions',
        'ga4_ai_referral_conversions',
        'baseline_ga4_sessions',
        'baseline_ga4_conversions',
        'baseline_ga4_revenue',
        'baseline_ga4_date',
        'last_ga4_sync'
    ]
    
    for column in columns_to_remove:
        op.drop_column('collection_optimizer', column)
