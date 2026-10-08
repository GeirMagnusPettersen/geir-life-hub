"""add source column to fluid/coffee/health_observation entries

Revision ID: b2d6f4a9c8e1
Revises: a7c3e9f12b56
Create Date: 2026-10-21 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2d6f4a9c8e1'
down_revision: Union[str, None] = 'a7c3e9f12b56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'fluid_entries',
        sa.Column('source', sa.String(length=32), nullable=False, server_default='manual'),
    )
    op.add_column(
        'coffee_entries',
        sa.Column('source', sa.String(length=32), nullable=False, server_default='manual'),
    )
    op.add_column(
        'health_observations',
        sa.Column('source', sa.String(length=32), nullable=False, server_default='manual'),
    )


def downgrade() -> None:
    op.drop_column('health_observations', 'source')
    op.drop_column('coffee_entries', 'source')
    op.drop_column('fluid_entries', 'source')
