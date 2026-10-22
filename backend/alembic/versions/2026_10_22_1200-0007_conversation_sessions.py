"""conversation sessions: limite de inatividade por Company e início da Session na Conversation

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'companies',
        sa.Column('session_timeout_minutes', sa.Integer(), nullable=False, server_default='180'),
    )
    op.add_column('conversations', sa.Column('session_started_at', sa.DateTime(timezone=True), nullable=True))

    # Conversations existentes: a Session atual começa na última Message precedida por uma pausa maior que o
    # padrão de 3 h (ou na primeira Message). Sem Messages, fica NULL e a próxima Message abre a Session.
    op.execute(
        sa.text(
            "UPDATE conversations c SET session_started_at = s.started_at FROM ("
            "  SELECT conversation_id, MAX(timestamp) FILTER (WHERE gap IS NULL OR gap > INTERVAL '180 minutes') AS started_at "
            "  FROM ("
            "    SELECT conversation_id, timestamp, "
            "           timestamp - LAG(timestamp) OVER (PARTITION BY conversation_id ORDER BY timestamp, id) AS gap "
            "    FROM messages WHERE conversation_id IS NOT NULL"
            "  ) m GROUP BY conversation_id"
            ") s WHERE s.conversation_id = c.id"
        )
    )


def downgrade() -> None:
    op.drop_column('conversations', 'session_started_at')
    op.drop_column('companies', 'session_timeout_minutes')
