"""message sent_by: marca os avisos da API (status do Order, #34) para o eco do webhook não virar atividade de Attendant

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-22 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('sent_by', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('messages', 'sent_by')
