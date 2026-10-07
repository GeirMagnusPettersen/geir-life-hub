"""add heart rate fields and workout sessions

Revision ID: f1a9c6e2b3d4
Revises: d3932fb678e5
Create Date: 2026-10-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a9c6e2b3d4'
down_revision: Union[str, None] = 'd3932fb678e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sleep_activity_summaries', sa.Column('resting_heart_rate', sa.Integer(), nullable=True))
    op.add_column('sleep_activity_summaries', sa.Column('avg_heart_rate', sa.Integer(), nullable=True))

    op.create_table(
        'workout_sessions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('external_id', sa.String(length=128), nullable=False),
        sa.Column('activity_type', sa.String(length=64), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('calories', sa.Float(), nullable=True),
        sa.Column('avg_heart_rate', sa.Integer(), nullable=True),
        sa.Column('distance_meters', sa.Float(), nullable=True),
        sa.Column('source', sa.String(length=32), nullable=False),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'source', 'external_id', name='uq_workout_user_source_external_id'),
    )


def downgrade() -> None:
    op.drop_table('workout_sessions')
    op.drop_column('sleep_activity_summaries', 'avg_heart_rate')
    op.drop_column('sleep_activity_summaries', 'resting_heart_rate')
