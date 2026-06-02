"""
Add dataforseo_organic_results JSON column for permanent SERP caching
Revision ID: collection_optimizer_004
"""

from alembic import op
import sqlalchemy as sa

# Revision identifiers
revision = 'collection_optimizer_004'
down_revision = 'collection_optimizer_003'
branch_labels = None
depends_on = None


def upgrade():
    # Add permanent storage for top 10 organic SERP results
    op.add_column(
        'collection_optimizer',
        sa.Column('dataforseo_organic_results', sa.JSON(), nullable=True)
    )


def downgrade():
    op.drop_column('collection_optimizer', 'dataforseo_organic_results')
