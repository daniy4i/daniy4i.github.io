"""add artifacts_json to jobs

Revision ID: 0002
Revises: 0001
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jobs", sa.Column("artifacts_json", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("jobs", "artifacts_json")
