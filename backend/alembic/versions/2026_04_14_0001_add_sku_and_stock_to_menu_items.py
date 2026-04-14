"""add sku and stock quantity to menu items

Revision ID: f1e2d3c4b5a6
Revises: 8f3d1b2c4a6e
Create Date: 2026-04-14 00:01:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "f1e2d3c4b5a6"
down_revision: Union[str, None] = "8f3d1b2c4a6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("menu_items")}

    # Add sku column if it doesn't exist
    if "sku" not in existing_columns:
        op.add_column(
            "menu_items",
            sa.Column("sku", sa.String(50), nullable=True),
        )
        op.create_index("ix_menu_items_sku", "menu_items", ["sku"], unique=True)
    
    # Add stock_quantity column if it doesn't exist
    if "stock_quantity" not in existing_columns:
        op.add_column(
            "menu_items",
            sa.Column("stock_quantity", sa.Integer(), nullable=True, server_default="0"),
        )
        # Set default value for existing rows
        op.execute("UPDATE menu_items SET stock_quantity = 0 WHERE stock_quantity IS NULL")
        op.alter_column("menu_items", "stock_quantity", nullable=False, server_default="0")


def downgrade() -> None:
    op.drop_index("ix_menu_items_sku", table_name="menu_items")
    op.drop_column("menu_items", "sku")
    op.drop_column("menu_items", "stock_quantity")
