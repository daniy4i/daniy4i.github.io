"""org auth usage tables

Revision ID: 0004
Revises: 0003
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("username", sa.String(length=120), nullable=False),
        sa.Column("password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "api_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_api_tokens_token_hash", "api_tokens", ["token_hash"], unique=True)

    op.create_table(
        "org_usage_monthly",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("year_month", sa.String(length=7), nullable=False),
        sa.Column("processed_minutes", sa.Float(), nullable=False),
        sa.Column("jobs_total", sa.Integer(), nullable=False),
        sa.Column("exports_total", sa.Integer(), nullable=False),
    )

    op.add_column("jobs", sa.Column("org_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_jobs_org", "jobs", "organizations", ["org_id"], ["id"])


def downgrade():
    op.drop_constraint("fk_jobs_org", "jobs", type_="foreignkey")
    op.drop_column("jobs", "org_id")
    op.drop_table("org_usage_monthly")
    op.drop_index("ix_api_tokens_token_hash", table_name="api_tokens")
    op.drop_table("api_tokens")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
    op.drop_table("organizations")
