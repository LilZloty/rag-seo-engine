"""Merge collection_optimizer_004 and solution_engine heads

Revision ID: d13133eb008b
Revises: add_solution_engine_tables, collection_optimizer_004
Create Date: 2026-02-20 16:23:13.439703

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd13133eb008b'
down_revision = ('add_solution_engine_tables', 'collection_optimizer_004')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
