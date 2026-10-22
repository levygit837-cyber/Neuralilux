"""handoff exit: company timeout, ticket closed_at and attendant activity

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'companies',
        sa.Column('handoff_timeout_hours', sa.Integer(), nullable=False, server_default='4'),
    )
    op.add_column('tickets', sa.Column('attendant_activity_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('tickets', sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True))
    # Tickets já fechados ganham o instante de fechamento aproximado pela última atualização.
    op.execute("UPDATE tickets SET closed_at = COALESCE(updated_at, created_at) WHERE status = 'closed'")


def downgrade() -> None:
    op.drop_column('tickets', 'closed_at')
    op.drop_column('tickets', 'attendant_activity_at')
    op.drop_column('companies', 'handoff_timeout_hours')
