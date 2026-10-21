"""conversation memory: summaries and portuguese full-text index

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-21 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

FTS_INDEX = 'ix_messages_content_fts'


def upgrade() -> None:
    op.create_table('conversation_summaries',
    sa.Column('conversation_id', sa.String(), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('covered_until_message_id', sa.String(), nullable=False),
    sa.Column('message_count', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
    sa.ForeignKeyConstraint(['covered_until_message_id'], ['messages.id'], ),
    sa.PrimaryKeyConstraint('conversation_id')
    )
    # History Search (ADR 0003): a expressão tem de ser idêntica à de app.agent.memory.search_history.
    # SQLite (testes) não tem tsvector; lá a busca usa ILIKE e o índice é omitido.
    if op.get_context().dialect.name == 'postgresql':
        op.create_index(
            FTS_INDEX,
            'messages',
            [sa.text("to_tsvector('portuguese', coalesce(content,''))")],
            postgresql_using='gin',
        )


def downgrade() -> None:
    if op.get_context().dialect.name == 'postgresql':
        op.drop_index(FTS_INDEX, table_name='messages', postgresql_using='gin')
    op.drop_table('conversation_summaries')
