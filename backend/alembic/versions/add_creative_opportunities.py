"""Add creative_opportunities table

Revision ID: add_creative_opportunities
Revises: add_supervisor_tables
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa


revision = 'add_creative_opportunities'
down_revision = 'add_supervisor_tables'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'creative_opportunities',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),

        sa.Column('opportunity_type', sa.String(length=50), nullable=False),
        sa.Column('priority', sa.String(length=20), nullable=False, server_default='medium'),

        sa.Column('target_type', sa.String(length=20), nullable=False),
        sa.Column('target_transmission_code', sa.String(length=30), nullable=True),
        sa.Column('target_vehicle_brand', sa.String(length=50), nullable=True),
        sa.Column('target_product_id', sa.String(), nullable=True),
        sa.Column('target_query', sa.String(length=255), nullable=True),

        sa.Column('signal_data', sa.JSON(), nullable=True),

        sa.Column('opportunity_score', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('estimated_monthly_sessions', sa.Integer(), nullable=True),
        sa.Column('estimated_monthly_revenue', sa.Float(), nullable=True),

        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('recommended_action', sa.Text(), nullable=True),
        sa.Column('action_steps', sa.JSON(), nullable=True),

        sa.Column('status', sa.String(length=20), nullable=False, server_default='open'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=True),

        sa.Column('signal_hash', sa.String(length=64), nullable=False),

        sa.ForeignKeyConstraint(['target_product_id'], ['products.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('signal_hash', name='uq_creative_opp_signal_hash'),
    )

    op.create_index('ix_creative_opportunities_created_at', 'creative_opportunities', ['created_at'])
    op.create_index('ix_creative_opportunities_last_seen_at', 'creative_opportunities', ['last_seen_at'])
    op.create_index('ix_creative_opportunities_opportunity_type', 'creative_opportunities', ['opportunity_type'])
    op.create_index('ix_creative_opportunities_priority', 'creative_opportunities', ['priority'])
    op.create_index('ix_creative_opportunities_status', 'creative_opportunities', ['status'])
    op.create_index('ix_creative_opportunities_target_transmission_code', 'creative_opportunities', ['target_transmission_code'])
    op.create_index('ix_creative_opportunities_target_vehicle_brand', 'creative_opportunities', ['target_vehicle_brand'])
    op.create_index('ix_creative_opportunities_target_product_id', 'creative_opportunities', ['target_product_id'])
    op.create_index('ix_creative_opportunities_opportunity_score', 'creative_opportunities', ['opportunity_score'])
    op.create_index('ix_creative_opportunities_signal_hash', 'creative_opportunities', ['signal_hash'])

    # Composite indexes — back the dashboard's "filter by type + status" and
    # "rank by score within status" queries without scanning the whole table.
    op.create_index('ix_creative_opp_type_status', 'creative_opportunities', ['opportunity_type', 'status'])
    op.create_index('ix_creative_opp_score_status', 'creative_opportunities', ['opportunity_score', 'status'])


def downgrade():
    op.drop_index('ix_creative_opp_score_status', table_name='creative_opportunities')
    op.drop_index('ix_creative_opp_type_status', table_name='creative_opportunities')
    op.drop_index('ix_creative_opportunities_signal_hash', table_name='creative_opportunities')
    op.drop_index('ix_creative_opportunities_opportunity_score', table_name='creative_opportunities')
    op.drop_index('ix_creative_opportunities_target_product_id', table_name='creative_opportunities')
    op.drop_index('ix_creative_opportunities_target_vehicle_brand', table_name='creative_opportunities')
    op.drop_index('ix_creative_opportunities_target_transmission_code', table_name='creative_opportunities')
    op.drop_index('ix_creative_opportunities_status', table_name='creative_opportunities')
    op.drop_index('ix_creative_opportunities_priority', table_name='creative_opportunities')
    op.drop_index('ix_creative_opportunities_opportunity_type', table_name='creative_opportunities')
    op.drop_index('ix_creative_opportunities_last_seen_at', table_name='creative_opportunities')
    op.drop_index('ix_creative_opportunities_created_at', table_name='creative_opportunities')
    op.drop_table('creative_opportunities')
