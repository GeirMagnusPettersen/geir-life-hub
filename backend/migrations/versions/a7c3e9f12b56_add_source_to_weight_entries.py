"""add source column to weight entries

Revision ID: a7c3e9f12b56
Revises: f1a9c6e2b3d4
Create Date: 2026-10-14 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c3e9f12b56'
down_revision: Union[str, None] = 'f1a9c6e2b3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'weight_entries',
        sa.Column('source', sa.String(length=32), nullable=False, server_default='manual'),
    )


def downgrade() -> None:
    op.drop_column('weight_entries', 'source')
