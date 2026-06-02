"""Increase h1_title length to 100

Revision ID: 9175bbc98952
Revises: f5806b208ad5
Create Date: 2026-02-09 16:19:47.357888

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9175bbc98952'
down_revision = 'f5806b208ad5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite doesn't support ALTER COLUMN directly
    # We need to use batch operations for column type changes
    
    # Update content_drafts table
    with op.batch_alter_table('content_drafts', schema=None) as batch_op:
        batch_op.alter_column('h1_title',
               existing_type=sa.VARCHAR(length=60),
               type_=sa.String(length=100),
               existing_nullable=True)
    
    # Update generation_history table
    with op.batch_alter_table('generation_history', schema=None) as batch_op:
        batch_op.alter_column('h1_title',
               existing_type=sa.VARCHAR(length=60),
               type_=sa.String(length=100),
               existing_nullable=True)


def downgrade() -> None:
    # Revert changes
    with op.batch_alter_table('generation_history', schema=None) as batch_op:
        batch_op.alter_column('h1_title',
               existing_type=sa.String(length=100),
               type_=sa.VARCHAR(length=60),
               existing_nullable=True)
    
    with op.batch_alter_table('content_drafts', schema=None) as batch_op:
        batch_op.alter_column('h1_title',
               existing_type=sa.String(length=100),
               type_=sa.VARCHAR(length=60),
               existing_nullable=True)
