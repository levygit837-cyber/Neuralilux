"""remove a pilha legada de Products: derruba products e product_types

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-24 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(op.f('ix_products_sku'), table_name='products')
    op.drop_table('products')
    op.drop_index(op.f('ix_product_types_slug'), table_name='product_types')
    op.drop_table('product_types')


def downgrade() -> None:
    # Recria as tabelas vazias; os dados de Products não voltam (o catálogo real é MenuItem/MenuCategory).
    op.create_table('product_types',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('slug', sa.String(length=50), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('icon', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_product_types_slug'), 'product_types', ['slug'], unique=True)
    op.create_table('products',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('company_id', sa.String(), nullable=False),
    sa.Column('product_type_id', sa.String(), nullable=True),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('image_url', sa.String(length=500), nullable=True),
    sa.Column('sku', sa.String(length=50), nullable=True),
    sa.Column('is_available', sa.Boolean(), nullable=True),
    sa.Column('stock_quantity', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.ForeignKeyConstraint(['product_type_id'], ['product_types.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_products_sku'), 'products', ['sku'], unique=True)
