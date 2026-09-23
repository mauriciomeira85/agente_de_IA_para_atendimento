"""numero_de_reaberturas (substitui foi_reaberto, base p/ cobrança por ciclo)

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-09-23 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'atendimentos',
        sa.Column('numero_de_reaberturas', sa.Integer(), nullable=False, server_default='0'),
    )
    # Backfill: quem já tinha foi_reaberto=True vira 1 reabertura contada
    # (não dá pra saber QUANTAS foram antes desta correção, já que só
    # existia um booleano — 1 é a melhor aproximação possível).
    op.execute("UPDATE atendimentos SET numero_de_reaberturas = 1 WHERE foi_reaberto IS TRUE")
    op.drop_column('atendimentos', 'foi_reaberto')


def downgrade() -> None:
    op.add_column('atendimentos', sa.Column('foi_reaberto', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE atendimentos SET foi_reaberto = (numero_de_reaberturas > 0)")
    op.drop_column('atendimentos', 'numero_de_reaberturas')
