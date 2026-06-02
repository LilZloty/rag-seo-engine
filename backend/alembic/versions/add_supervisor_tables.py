"""Add Supervisor agent tables (news_items, proposals, runs)

Revision ID: add_supervisor_tables
Revises: add_snapshot_shopify_state
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa


revision = 'add_supervisor_tables'
down_revision = 'add_snapshot_shopify_state'
branch_labels = None
depends_on = None


def upgrade():
    # supervisor_news_items: deduped + summarized SEO/AEO/GEO news
    op.create_table(
        'supervisor_news_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source', sa.String(length=80), nullable=False),
        sa.Column('source_kind', sa.String(length=20), nullable=True, server_default='rss'),
        sa.Column('guid', sa.String(length=500), nullable=True),
        sa.Column('url', sa.String(length=1000), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('raw_summary', sa.Text(), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('summary_bullets', sa.JSON(), nullable=True),
        sa.Column('tag', sa.String(length=20), nullable=True),
        sa.Column('relevance', sa.String(length=10), nullable=True),
        sa.Column('summarized_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('summary_model', sa.String(length=60), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'url', name='uq_news_source_url'),
    )
    op.create_index('ix_supervisor_news_items_source', 'supervisor_news_items', ['source'])
    op.create_index('ix_supervisor_news_items_published_at', 'supervisor_news_items', ['published_at'])
    op.create_index('ix_supervisor_news_items_tag', 'supervisor_news_items', ['tag'])
    op.create_index('ix_supervisor_news_items_fetched_at', 'supervisor_news_items', ['fetched_at'])
    op.create_index('ix_news_published_tag', 'supervisor_news_items', ['published_at', 'tag'])

    # supervisor_proposals: actions proposed for human review (reserved for Phase 4)
    op.create_table(
        'supervisor_proposals',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('kind', sa.String(length=40), nullable=False),
        sa.Column('target', sa.String(length=500), nullable=True),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('expected_impact', sa.Text(), nullable=True),
        sa.Column('confidence', sa.String(length=10), nullable=False, server_default='low'),
        sa.Column('tool_citations', sa.JSON(), nullable=True),
        sa.Column('proposed_action', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('shipped_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('human_notes', sa.Text(), nullable=True),
        sa.Column('outcome_metric_t14', sa.JSON(), nullable=True),
        sa.Column('outcome_verdict', sa.String(length=20), nullable=True),
        sa.Column('evaluated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('run_id', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_supervisor_proposals_created_at', 'supervisor_proposals', ['created_at'])
    op.create_index('ix_supervisor_proposals_kind', 'supervisor_proposals', ['kind'])
    op.create_index('ix_supervisor_proposals_status', 'supervisor_proposals', ['status'])
    op.create_index('ix_supervisor_proposals_shipped_at', 'supervisor_proposals', ['shipped_at'])
    op.create_index('ix_supervisor_proposals_run_id', 'supervisor_proposals', ['run_id'])

    # supervisor_runs: cost + status log per invocation
    op.create_table(
        'supervisor_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('mode', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='running'),
        sa.Column('model', sa.String(length=60), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('output_tokens', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('cost_usd', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('artifacts', sa.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_supervisor_runs_started_at', 'supervisor_runs', ['started_at'])
    op.create_index('ix_supervisor_runs_mode', 'supervisor_runs', ['mode'])


def downgrade():
    op.drop_index('ix_supervisor_runs_mode', table_name='supervisor_runs')
    op.drop_index('ix_supervisor_runs_started_at', table_name='supervisor_runs')
    op.drop_table('supervisor_runs')

    op.drop_index('ix_supervisor_proposals_run_id', table_name='supervisor_proposals')
    op.drop_index('ix_supervisor_proposals_shipped_at', table_name='supervisor_proposals')
    op.drop_index('ix_supervisor_proposals_status', table_name='supervisor_proposals')
    op.drop_index('ix_supervisor_proposals_kind', table_name='supervisor_proposals')
    op.drop_index('ix_supervisor_proposals_created_at', table_name='supervisor_proposals')
    op.drop_table('supervisor_proposals')

    op.drop_index('ix_news_published_tag', table_name='supervisor_news_items')
    op.drop_index('ix_supervisor_news_items_fetched_at', table_name='supervisor_news_items')
    op.drop_index('ix_supervisor_news_items_tag', table_name='supervisor_news_items')
    op.drop_index('ix_supervisor_news_items_published_at', table_name='supervisor_news_items')
    op.drop_index('ix_supervisor_news_items_source', table_name='supervisor_news_items')
    op.drop_table('supervisor_news_items')
