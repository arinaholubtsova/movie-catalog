"""add poster url

Revision ID: a4f9218c67ad
Revises: f787d7663e28
"""
from alembic import op
import sqlalchemy as sa


revision = "a4f9218c67ad"
down_revision = "f787d7663e28"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("movies", sa.Column("poster_url", sa.String(length=1000), nullable=True))


def downgrade():
    op.drop_column("movies", "poster_url")
