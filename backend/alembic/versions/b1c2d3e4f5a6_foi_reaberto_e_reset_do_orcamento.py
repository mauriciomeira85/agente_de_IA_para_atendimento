"""foi_reaberto (taxa de reabertura do Dashboard)

Revision ID: b1c2d3e4f5a6
Revises: a9a261e130bf
Create Date: 2026-09-22 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'a9a261e130bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'atendimentos',
        sa.Column('foi_reaberto', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('atendimentos', 'foi_reaberto')
