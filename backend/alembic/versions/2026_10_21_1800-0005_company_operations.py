"""company operations: business hours, timezone, minimum order, zones per company

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-21 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('companies', sa.Column('business_hours', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column(
        'companies',
        sa.Column('timezone', sa.String(length=64), nullable=False, server_default='America/Sao_Paulo'),
    )
    op.add_column('companies', sa.Column('minimum_order', sa.Numeric(precision=10, scale=2), nullable=True))

    op.add_column('delivery_zones', sa.Column('company_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_delivery_zones_company_id'), 'delivery_zones', ['company_id'], unique=False)
    op.create_foreign_key('fk_delivery_zones_company_id', 'delivery_zones', 'companies', ['company_id'], ['id'])

    # Dados da entrega do Order (tipo, taxa da zona e troco) para o total e o fechamento do pedido.
    op.add_column('customer_orders', sa.Column('delivery_type', sa.String(length=20), nullable=True))
    op.add_column(
        'customer_orders',
        sa.Column('delivery_fee', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0'),
    )
    op.add_column('customer_orders', sa.Column('change_for', sa.Numeric(precision=10, scale=2), nullable=True))

    # Backfill: as zonas existentes não tinham dono. Só atribuímos quando não há ambiguidade
    # (exatamente uma Company `restaurant`); senão ficam NULL e o Pack as ignora.
    bind = op.get_bind()
    restaurant_ids = [
        row[0]
        for row in bind.execute(
            sa.text(
                "SELECT c.id FROM companies c JOIN business_types bt ON bt.id = c.business_type_id "
                "WHERE bt.slug = 'restaurant' ORDER BY c.created_at, c.id"
            )
        )
    ]
    if len(restaurant_ids) == 1:
        bind.execute(
            sa.text("UPDATE delivery_zones SET company_id = :company_id WHERE company_id IS NULL"),
            {"company_id": restaurant_ids[0]},
        )


def downgrade() -> None:
    op.drop_column('customer_orders', 'change_for')
    op.drop_column('customer_orders', 'delivery_fee')
    op.drop_column('customer_orders', 'delivery_type')
    op.drop_constraint('fk_delivery_zones_company_id', 'delivery_zones', type_='foreignkey')
    op.drop_index(op.f('ix_delivery_zones_company_id'), table_name='delivery_zones')
    op.drop_column('delivery_zones', 'company_id')
    op.drop_column('companies', 'minimum_order')
    op.drop_column('companies', 'timezone')
    op.drop_column('companies', 'business_hours')
