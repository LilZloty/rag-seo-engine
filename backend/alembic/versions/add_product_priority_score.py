"""
Add priority_score columns to products table.

Documentation-only. Alembic isn't wired into the running container — the
actual migration was applied manually with:

    docker exec rag-seo-postgres psql -U raguser -d rag_seo -c "
      ALTER TABLE products
        ADD COLUMN priority_score FLOAT DEFAULT 0,
        ADD COLUMN priority_components JSON,
        ADD COLUMN priority_computed_at TIMESTAMP WITH TIME ZONE;
      CREATE INDEX IF NOT EXISTS ix_products_priority_score
        ON products (priority_score DESC NULLS LAST);
    "

Revision ID: add_product_priority_score
"""

from alembic import op
import sqlalchemy as sa

revision = 'add_product_priority_score'
down_revision = 'add_snapshot_shopify_state'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('products', sa.Column('priority_score', sa.Float(), server_default='0', nullable=True))
    op.add_column('products', sa.Column('priority_components', sa.JSON(), nullable=True))
    op.add_column('products', sa.Column('priority_computed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_products_priority_score', 'products', ['priority_score'], unique=False)


def downgrade():
    op.drop_index('ix_products_priority_score', table_name='products')
    op.drop_column('products', 'priority_computed_at')
    op.drop_column('products', 'priority_components')
    op.drop_column('products', 'priority_score')
