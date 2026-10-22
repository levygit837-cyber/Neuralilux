"""order recap: impressão, Turn e entrega da recapitulação que o Contact viu antes de fechar o Order

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-22 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('customer_orders', sa.Column('recap_signature', sa.String(length=64), nullable=True))
    op.add_column('customer_orders', sa.Column('recap_turn_id', sa.String(length=32), nullable=True))
    op.add_column('customer_orders', sa.Column('recap_delivered_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('customer_orders', 'recap_delivered_at')
    op.drop_column('customer_orders', 'recap_turn_id')
    op.drop_column('customer_orders', 'recap_signature')
