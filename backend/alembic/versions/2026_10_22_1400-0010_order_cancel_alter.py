"""order cancel/alter: cancelamento do Order, estorno manual do Pix e Pix válido único

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-22 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None

VALID_PIX = "payment_method = 'pix' AND status IN ('pending', 'paid')"


def upgrade() -> None:
    op.add_column('customer_orders', sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('customer_orders', sa.Column('cancel_reason', sa.Text(), nullable=True))
    op.add_column('payment_records', sa.Column('refund_status', sa.String(length=20), nullable=True))
    op.add_column('payment_records', sa.Column('refund_flagged_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('payment_records', sa.Column('refunded_at', sa.DateTime(timezone=True), nullable=True))
    # O índice passa a cobrir só o Pix válido: o Pix invalidado (cancelled/superseded) convive com o novo.
    op.drop_index('uq_payment_records_order_pix', table_name='payment_records')
    op.create_index(
        'uq_payment_records_order_pix',
        'payment_records',
        ['order_id'],
        unique=True,
        postgresql_where=sa.text(VALID_PIX),
    )


def downgrade() -> None:
    # Voltar ao índice antigo exige um Pix por Order: os invalidados saem do caminho antes (mantêm o registro).
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE payment_records SET payment_method = 'pix_invalidated' "
            "WHERE payment_method = 'pix' AND status NOT IN ('pending', 'paid')"
        )
    )
    op.drop_index('uq_payment_records_order_pix', table_name='payment_records')
    op.create_index(
        'uq_payment_records_order_pix',
        'payment_records',
        ['order_id'],
        unique=True,
        postgresql_where=sa.text("payment_method = 'pix'"),
    )
    op.drop_column('payment_records', 'refunded_at')
    op.drop_column('payment_records', 'refund_flagged_at')
    op.drop_column('payment_records', 'refund_status')
    op.drop_column('customer_orders', 'cancel_reason')
    op.drop_column('customer_orders', 'cancelled_at')
