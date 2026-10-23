"""chat history sync: conversations.is_group e messages.sender_name

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-22 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'conversations',
        sa.Column('is_group', sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column('messages', sa.Column('sender_name', sa.String(length=200), nullable=True))
    # Grupos já gravados antes desta migração (não havia; o filtro os descartava) ficam corretos mesmo assim.
    op.execute("UPDATE conversations SET is_group = true WHERE remote_jid LIKE '%@g.us'")


def downgrade() -> None:
    op.drop_column('messages', 'sender_name')
    op.drop_column('conversations', 'is_group')
