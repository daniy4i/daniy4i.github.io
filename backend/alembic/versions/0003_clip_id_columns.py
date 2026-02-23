"""add clip_id columns

Revision ID: 0003
Revises: 0002
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tracks", sa.Column("clip_id", sa.String(length=64), nullable=True))
    op.add_column("events", sa.Column("clip_id", sa.String(length=64), nullable=True))
    op.add_column("analytics_windows", sa.Column("clip_id", sa.String(length=64), nullable=True))
    op.create_index("ix_tracks_clip_id", "tracks", ["clip_id"])
    op.create_index("ix_events_clip_id", "events", ["clip_id"])
    op.create_index("ix_analytics_windows_clip_id", "analytics_windows", ["clip_id"])


def downgrade():
    op.drop_index("ix_analytics_windows_clip_id", table_name="analytics_windows")
    op.drop_index("ix_events_clip_id", table_name="events")
    op.drop_index("ix_tracks_clip_id", table_name="tracks")
    op.drop_column("analytics_windows", "clip_id")
    op.drop_column("events", "clip_id")
    op.drop_column("tracks", "clip_id")
