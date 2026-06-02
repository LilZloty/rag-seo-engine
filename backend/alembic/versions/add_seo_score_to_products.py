"""
Add seo_score column to products table
Revision ID: add_seo_score_to_products
down_revision: d13133eb008b
"""

from alembic import op
import sqlalchemy as sa

# Revision identifiers
revision = 'add_seo_score_to_products'
down_revision = 'd13133eb008b'
branch_labels = None
depends_on = None


def upgrade():
    # Add seo_score column to products table
    op.add_column(
        'products',
        sa.Column('seo_score', sa.Integer(), nullable=True, server_default='0')
    )


def downgrade():
    op.drop_column('products', 'seo_score')
