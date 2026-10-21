"""remove super agent, RAG and documents

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-21 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM gateway_assignments WHERE agent_type = 'super_agent'")

    # Filhas antes de super_agent_sessions (FKs).
    op.drop_index(op.f('ix_super_agent_messages_session_id'), table_name='super_agent_messages')
    op.drop_table('super_agent_messages')
    op.drop_index(op.f('ix_super_agent_knowledge_company_id'), table_name='super_agent_knowledge')
    op.drop_index(op.f('ix_super_agent_knowledge_category'), table_name='super_agent_knowledge')
    op.drop_table('super_agent_knowledge')
    op.drop_index(op.f('ix_super_agent_documents_session_id'), table_name='super_agent_documents')
    op.drop_index(op.f('ix_super_agent_documents_company_id'), table_name='super_agent_documents')
    op.drop_table('super_agent_documents')
    op.drop_index(op.f('ix_super_agent_checkpoints_session_id'), table_name='super_agent_checkpoints')
    op.drop_table('super_agent_checkpoints')
    op.drop_index(op.f('ix_super_agent_sessions_user_id'), table_name='super_agent_sessions')
    op.drop_index(op.f('ix_super_agent_sessions_company_id'), table_name='super_agent_sessions')
    op.drop_table('super_agent_sessions')

    op.drop_table('documents')
    op.drop_index(op.f('ix_company_rules_company_id'), table_name='company_rules')
    op.drop_table('company_rules')


def downgrade() -> None:
    # Recria as tabelas como estavam no baseline 0001. Os dados nao voltam.
    op.create_table('company_rules',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('company_id', sa.String(), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('category', sa.String(length=50), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_company_rules_company_id'), 'company_rules', ['company_id'], unique=False)
    op.create_table('documents',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('agent_id', sa.String(), nullable=True),
    sa.Column('filename', sa.String(), nullable=False),
    sa.Column('file_path', sa.String(), nullable=False),
    sa.Column('file_type', sa.String(), nullable=True),
    sa.Column('file_size', sa.Integer(), nullable=True),
    sa.Column('is_processed', sa.Boolean(), nullable=True),
    sa.Column('chunk_count', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('super_agent_sessions',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('company_id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('interaction_count', sa.Integer(), nullable=True),
    sa.Column('last_checkpoint_at', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_super_agent_sessions_company_id'), 'super_agent_sessions', ['company_id'], unique=False)
    op.create_index(op.f('ix_super_agent_sessions_user_id'), 'super_agent_sessions', ['user_id'], unique=False)
    op.create_table('super_agent_checkpoints',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('session_id', sa.String(), nullable=False),
    sa.Column('interaction_number', sa.Integer(), nullable=False),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('context_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['session_id'], ['super_agent_sessions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('session_id', 'interaction_number', name='uq_checkpoint_session_number')
    )
    op.create_index(op.f('ix_super_agent_checkpoints_session_id'), 'super_agent_checkpoints', ['session_id'], unique=False)
    op.create_table('super_agent_documents',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('session_id', sa.String(), nullable=False),
    sa.Column('company_id', sa.String(), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('file_type', sa.String(length=20), nullable=False),
    sa.Column('content', sa.Text(), nullable=True),
    sa.Column('content_base64', sa.Text(), nullable=True),
    sa.Column('file_size', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.ForeignKeyConstraint(['session_id'], ['super_agent_sessions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_super_agent_documents_company_id'), 'super_agent_documents', ['company_id'], unique=False)
    op.create_index(op.f('ix_super_agent_documents_session_id'), 'super_agent_documents', ['session_id'], unique=False)
    op.create_table('super_agent_knowledge',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('company_id', sa.String(), nullable=False),
    sa.Column('category', sa.String(length=100), nullable=False),
    sa.Column('key', sa.String(length=200), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.Column('source_session_id', sa.String(), nullable=True),
    sa.Column('confidence', sa.Integer(), nullable=True),
    sa.Column('access_count', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.ForeignKeyConstraint(['source_session_id'], ['super_agent_sessions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('company_id', 'category', 'key', name='uq_knowledge_company_category_key')
    )
    op.create_index(op.f('ix_super_agent_knowledge_category'), 'super_agent_knowledge', ['category'], unique=False)
    op.create_index(op.f('ix_super_agent_knowledge_company_id'), 'super_agent_knowledge', ['company_id'], unique=False)
    op.create_table('super_agent_messages',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('session_id', sa.String(), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('content', sa.Text(), nullable=True),
    sa.Column('tool_name', sa.String(length=100), nullable=True),
    sa.Column('tool_input', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('tool_output', sa.Text(), nullable=True),
    sa.Column('thinking_content', sa.Text(), nullable=True),
    sa.Column('extra_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['session_id'], ['super_agent_sessions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_super_agent_messages_session_id'), 'super_agent_messages', ['session_id'], unique=False)
