"""resumo_do_atendimento vira Text (era String(500), estourava em teste real)

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-09-23 02:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('atendimentos', 'resumo_do_atendimento', type_=sa.Text(), existing_type=sa.String(500))


def downgrade() -> None:
    op.alter_column('atendimentos', 'resumo_do_atendimento', type_=sa.String(500), existing_type=sa.Text())
