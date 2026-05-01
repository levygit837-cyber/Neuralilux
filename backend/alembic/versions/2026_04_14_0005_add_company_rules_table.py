"""Add company_rules table for RAG."""
from alembic import op
import sqlalchemy as sa

revision = 'add_company_rules'
down_revision = '2026_04_14_0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'company_rules',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('company_id', sa.String(), sa.ForeignKey('companies.id'), nullable=False, index=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('category', sa.String(50), nullable=False, server_default='general'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index('ix_company_rules_company_id', 'company_rules', ['company_id'])


def downgrade() -> None:
    op.drop_index('ix_company_rules_company_id', 'company_rules')
    op.drop_table('company_rules')
