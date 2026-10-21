"""single agent per company

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-21 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('agents', sa.Column('company_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_agents_company_id'), 'agents', ['company_id'], unique=False)
    op.create_foreign_key('fk_agents_company_id', 'agents', 'companies', ['company_id'], ['id'])
    # Backfill: o Agent pertence à Company do dono. Sem dono (ou dono sem Company) fica NULL.
    op.execute(
        "UPDATE agents SET company_id = (SELECT users.company_id FROM users WHERE users.id = agents.owner_id)"
    )

    # O modelo vem do Gateway; a coluna só sobrescreve quando preenchida.
    op.alter_column('agents', 'model', existing_type=sa.String(), nullable=True)
    # Antes 0-100 (inteiro); agora a escala do Gateway, Float nullable.
    op.alter_column(
        'agents',
        'temperature',
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_nullable=True,
        postgresql_using='temperature / 100.0',
    )

    op.drop_column('agents', 'use_rag')
    op.drop_column('agents', 'agent_type')
    op.drop_column('conversations', 'active_agent_type')


def downgrade() -> None:
    # Recria as colunas como no baseline 0001. Os valores antigos não voltam.
    op.add_column(
        'conversations',
        sa.Column('active_agent_type', sa.String(), nullable=False, server_default='sales'),
    )
    op.alter_column('conversations', 'active_agent_type', server_default=None)
    op.add_column('agents', sa.Column('agent_type', sa.String(), nullable=False, server_default='sales'))
    op.alter_column('agents', 'agent_type', server_default=None)
    op.add_column('agents', sa.Column('use_rag', sa.Boolean(), nullable=True))

    op.alter_column(
        'agents',
        'temperature',
        existing_type=sa.Float(),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using='round(temperature * 100)::integer',
    )
    op.execute("UPDATE agents SET model = 'gpt-4-turbo-preview' WHERE model IS NULL")

    op.drop_constraint('fk_agents_company_id', 'agents', type_='foreignkey')
    op.drop_index(op.f('ix_agents_company_id'), table_name='agents')
    op.drop_column('agents', 'company_id')
