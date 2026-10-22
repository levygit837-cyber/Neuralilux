"""order cancel/alter: cancelamento do Order, estorno manual do Pix, Pix válido único e snapshot da alteração

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-22 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None

VALID_PIX = "payment_method = 'pix' AND status IN ('pending', 'paid')"
INVALIDATED = 'pix_invalidated'  # marca de downgrade nos Pix invalidados; o upgrade devolve a `pix`


def upgrade() -> None:
    op.add_column('customer_orders', sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('customer_orders', sa.Column('cancel_reason', sa.Text(), nullable=True))
    op.add_column('customer_orders', sa.Column('confirmed_snapshot', postgresql.JSONB(), nullable=True))
    op.add_column('conversations', sa.Column('previous_session_started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('payment_records', sa.Column('txid', sa.String(length=25), nullable=True))
    op.add_column('payment_records', sa.Column('refund_status', sa.String(length=20), nullable=True))
    op.add_column('payment_records', sa.Column('refund_flagged_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('payment_records', sa.Column('refunded_at', sa.DateTime(timezone=True), nullable=True))
    # O índice passa a cobrir só o Pix válido: o Pix invalidado (cancelled/superseded) convive com o novo.
    op.drop_index('uq_payment_records_order_pix', table_name='payment_records')
    # Pix que um downgrade desta migração renomeou volta a ser `pix`. O status invalidado (superseded/cancelled/expired)
    # ficou intacto no downgrade, então os registros voltam fora do índice, sem colidir com o Pix válido do Order.
    op.execute(f"UPDATE payment_records SET payment_method = 'pix' WHERE payment_method = '{INVALIDATED}'")
    op.create_index(
        'uq_payment_records_order_pix',
        'payment_records',
        ['order_id'],
        unique=True,
        postgresql_where=sa.text(VALID_PIX),
    )


def downgrade() -> None:
    # Perdas assumidas: `cancelled_at`, `cancel_reason`, `confirmed_snapshot`, `previous_session_started_at`, `txid` e as
    # colunas de estorno somem e o upgrade seguinte não as reconstrói. O Pix invalidado não é apagado: só é renomeado
    # (`pix_invalidated`) para caber no índice antigo (um Pix por Order), e o upgrade o devolve como `pix`.
    op.execute(
        f"UPDATE payment_records SET payment_method = '{INVALIDATED}' "
        "WHERE payment_method = 'pix' AND status NOT IN ('pending', 'paid')"
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
    op.drop_column('payment_records', 'txid')
    op.drop_column('conversations', 'previous_session_started_at')
    op.drop_column('customer_orders', 'confirmed_snapshot')
    op.drop_column('customer_orders', 'cancel_reason')
    op.drop_column('customer_orders', 'cancelled_at')
