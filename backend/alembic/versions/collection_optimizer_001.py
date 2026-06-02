"""
Database migration for Collection Optimizer
Run this to create the tables
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# Revision identifiers
revision = 'collection_optimizer_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # CollectionOptimizer table
    op.create_table(
        'collection_optimizer',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('shopify_collection_id', sa.String(), unique=True, index=True),
        sa.Column('collection_handle', sa.String(), index=True),
        sa.Column('collection_title', sa.String()),
        sa.Column('collection_url', sa.String()),
        sa.Column('category', sa.String(), index=True),
        sa.Column('has_educational_content', sa.Boolean(), default=False),
        sa.Column('has_faq_section', sa.Boolean(), default=False),
        sa.Column('has_schema_markup', sa.Boolean(), default=False),
        sa.Column('metafield_description', sa.Text()),
        sa.Column('metafield_faq', sa.Text()),
        sa.Column('metafield_updated_at', sa.DateTime()),
        sa.Column('baseline_impressions', sa.Integer(), default=0),
        sa.Column('baseline_clicks', sa.Integer(), default=0),
        sa.Column('baseline_ctr', sa.Float(), default=0.0),
        sa.Column('baseline_position', sa.Float(), default=0.0),
        sa.Column('baseline_date', sa.DateTime()),
        sa.Column('current_impressions', sa.Integer(), default=0),
        sa.Column('current_clicks', sa.Integer(), default=0),
        sa.Column('current_ctr', sa.Float(), default=0.0),
        sa.Column('current_position', sa.Float(), default=0.0),
        sa.Column('last_analytics_sync', sa.DateTime()),
        sa.Column('optimization_status', sa.String(), default='pending'),
        sa.Column('optimization_priority', sa.Integer(), default=0),
        sa.Column('generated_content', sa.Text()),
        sa.Column('generated_faq', sqlite.JSON()),
        sa.Column('generated_schema', sa.Text()),
        sa.Column('content_generated_at', sa.DateTime()),
        sa.Column('ab_test_enabled', sa.Boolean(), default=False),
        sa.Column('ab_test_variant', sa.String()),
        sa.Column('ab_test_start_date', sa.DateTime()),
        sa.Column('ab_test_results', sqlite.JSON()),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # CollectionSearchQuery table
    op.create_table(
        'collection_search_queries',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('collection_id', sa.Integer(), sa.ForeignKey('collection_optimizer.id')),
        sa.Column('query', sa.String(), index=True),
        sa.Column('clicks', sa.Integer(), default=0),
        sa.Column('impressions', sa.Integer(), default=0),
        sa.Column('ctr', sa.Float(), default=0.0),
        sa.Column('position', sa.Float(), default=0.0),
        sa.Column('query_type', sa.String()),
        sa.Column('intent', sa.String()),
        sa.Column('priority_score', sa.Float(), default=0.0),
        sa.Column('date_recorded', sa.DateTime(), default=sa.func.now()),
    )
    
    # CollectionOptimizationHistory table
    op.create_table(
        'collection_optimization_history',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('collection_id', sa.Integer(), sa.ForeignKey('collection_optimizer.id'), nullable=True),
        sa.Column('action_type', sa.String()),
        sa.Column('action_status', sa.String()),
        sa.Column('action_details', sqlite.JSON()),
        sa.Column('content_before', sa.Text()),
        sa.Column('content_after', sa.Text()),
        sa.Column('impressions_change', sa.Integer()),
        sa.Column('clicks_change', sa.Integer()),
        sa.Column('ctr_change', sa.Float()),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
    )
    
    # CollectionContentTemplate table
    op.create_table(
        'collection_content_templates',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('template_name', sa.String(), unique=True),
        sa.Column('category', sa.String(), index=True),
        sa.Column('content_type', sa.String()),
        sa.Column('template_structure', sa.Text()),
        sa.Column('example_content', sa.Text()),
        sa.Column('placeholders', sqlite.JSON()),
        sa.Column('usage_count', sa.Integer(), default=0),
        sa.Column('avg_performance_score', sa.Float(), default=0.0),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
    )


def downgrade():
    op.drop_table('collection_content_templates')
    op.drop_table('collection_optimization_history')
    op.drop_table('collection_search_queries')
    op.drop_table('collection_optimizer')
