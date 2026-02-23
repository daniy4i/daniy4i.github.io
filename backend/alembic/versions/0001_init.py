"""init
Revision ID: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('jobs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('duration_s', sa.Float(), nullable=True),
        sa.Column('fps_sampled', sa.Integer(), nullable=True),
        sa.Column('settings_json', sa.JSON(), nullable=False),
        sa.Column('storage_key', sa.String(length=512), nullable=False),
        sa.Column('logs_summary', sa.Text(), nullable=False),
    )

def downgrade():
    op.drop_table('jobs')
