"""Merge heads

Revision ID: f5806b208ad5
Revises: collection_optimizer_002, product_add_analytics_001
Create Date: 2026-02-09 16:19:01.423459

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f5806b208ad5'
down_revision = ('collection_optimizer_002', 'product_add_analytics_001')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
