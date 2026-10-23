"""instruções da Company: agents.system_prompt passa a aceitar vazio e perde o legado "Atendente de X"

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-23 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('agents', 'system_prompt', existing_type=sa.Text(), nullable=True)
    # O seed gravava "Atendente de <nome da Company>" só para satisfazer o NOT NULL; agora o campo é a instrução
    # da Company e esse valor passaria a ir para o prompt. Só esse padrão exato (e texto vazio) é limpo.
    op.execute(
        "UPDATE agents SET system_prompt = NULL "
        "WHERE TRIM(system_prompt) = '' "
        "OR system_prompt = 'Atendente de ' || (SELECT companies.name FROM companies WHERE companies.id = agents.company_id)"
    )


def downgrade() -> None:
    op.execute("UPDATE agents SET system_prompt = '' WHERE system_prompt IS NULL")
    op.alter_column('agents', 'system_prompt', existing_type=sa.Text(), nullable=False)
