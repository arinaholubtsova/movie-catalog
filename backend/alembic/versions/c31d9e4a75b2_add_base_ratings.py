"""add base catalog ratings

Revision ID: c31d9e4a75b2
Revises: a4f9218c67ad
"""
from alembic import op
import sqlalchemy as sa


revision = "c31d9e4a75b2"
down_revision = "a4f9218c67ad"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("movies", sa.Column("base_rating", sa.Float(), nullable=False, server_default="0"))
    op.add_column("movies", sa.Column("base_rating_count", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("movies", "base_rating_count")
    op.drop_column("movies", "base_rating")
