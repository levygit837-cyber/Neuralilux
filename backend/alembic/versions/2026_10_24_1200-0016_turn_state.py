"""estado durável do Turn por Message do Contact (resposta durável, #91)

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Colunas nullable e sem default: no Postgres 15 é só catálogo (ACCESS EXCLUSIVE por instantes, sem reescrever
    # `messages`). As linhas que já existem ficam NULL = "sem Turn a fazer": nada do histórico é retomado.
    op.add_column('messages', sa.Column('turn_state', sa.String(length=16), nullable=True))
    op.add_column('messages', sa.Column('turn_reason', sa.String(length=32), nullable=True))
    op.add_column('messages', sa.Column('turn_claimed_at', sa.DateTime(timezone=True), nullable=True))
    # Parcial: nenhuma linha existente entra, mas o CREATE INDEX ainda faz uma varredura de `messages` com SHARE
    # (bloqueia escrita) até o commit. Veja docs/agents/migrations.md.
    op.create_index(
        'ix_messages_turn_pending',
        'messages',
        ['timestamp'],
        unique=False,
        postgresql_where=sa.text("turn_state = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index('ix_messages_turn_pending', table_name='messages', postgresql_where=sa.text("turn_state = 'pending'"))
    op.drop_column('messages', 'turn_claimed_at')
    op.drop_column('messages', 'turn_reason')
    op.drop_column('messages', 'turn_state')
