"""Add human_in_loop support to conversations

Revision ID: human_in_loop
Revises: add_company_rules
Create Date: 2025-01-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'human_in_loop'
down_revision = 'add_company_rules'
branch_labels = None
depends_on = None


def upgrade():
    # Add human_in_loop fields to conversations table
    op.add_column('conversations', sa.Column('human_in_loop', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('conversations', sa.Column('human_handoff_reason', sa.Text(), nullable=True))
    op.add_column('conversations', sa.Column('ticket_id', sa.String(), nullable=True))
    
    # Create index on human_in_loop for faster queries
    op.create_index('ix_conversations_human_in_loop', 'conversations', ['human_in_loop'])


def downgrade():
    # Remove indexes
    op.drop_index('ix_conversations_human_in_loop', table_name='conversations')
    
    # Remove columns
    op.drop_column('conversations', 'ticket_id')
    op.drop_column('conversations', 'human_handoff_reason')
    op.drop_column('conversations', 'human_in_loop')
