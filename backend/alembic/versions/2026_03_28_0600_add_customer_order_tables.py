"""add customer order tables

Revision ID: e4f1a2b3c4d5
Revises: d9e8f7a6b5c4
Create Date: 2026-03-28 06:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4f1a2b3c4d5"
down_revision: Union[str, None] = "d9e8f7a6b5c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customer_orders",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("order_number", sa.String(length=50), nullable=False),
        sa.Column("conversation_id", sa.String(), nullable=False),
        sa.Column("instance_id", sa.String(), nullable=False),
        sa.Column("contact_id", sa.String(), nullable=False),
        sa.Column("remote_jid", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
        sa.Column("customer_name", sa.String(length=200), nullable=True),
        sa.Column("customer_address", sa.Text(), nullable=True),
        sa.Column("customer_phone", sa.String(length=30), nullable=True),
        sa.Column("payment_method", sa.String(length=100), nullable=True),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("export_path", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["instance_id"], ["instances.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_number"),
    )
    op.create_index(op.f("ix_customer_orders_order_number"), "customer_orders", ["order_number"], unique=False)
    op.create_index(op.f("ix_customer_orders_conversation_id"), "customer_orders", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_customer_orders_instance_id"), "customer_orders", ["instance_id"], unique=False)
    op.create_index(op.f("ix_customer_orders_contact_id"), "customer_orders", ["contact_id"], unique=False)
    op.create_index(op.f("ix_customer_orders_remote_jid"), "customer_orders", ["remote_jid"], unique=False)

    op.create_table(
        "customer_order_items",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("menu_item_id", sa.String(), nullable=True),
        sa.Column("item_name", sa.String(length=200), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("subtotal_price", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["menu_item_id"], ["menu_items.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["customer_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_customer_order_items_order_id"), "customer_order_items", ["order_id"], unique=False)
    op.create_index(op.f("ix_customer_order_items_menu_item_id"), "customer_order_items", ["menu_item_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_customer_order_items_menu_item_id"), table_name="customer_order_items")
    op.drop_index(op.f("ix_customer_order_items_order_id"), table_name="customer_order_items")
    op.drop_table("customer_order_items")

    op.drop_index(op.f("ix_customer_orders_remote_jid"), table_name="customer_orders")
    op.drop_index(op.f("ix_customer_orders_contact_id"), table_name="customer_orders")
    op.drop_index(op.f("ix_customer_orders_instance_id"), table_name="customer_orders")
    op.drop_index(op.f("ix_customer_orders_conversation_id"), table_name="customer_orders")
    op.drop_index(op.f("ix_customer_orders_order_number"), table_name="customer_orders")
    op.drop_table("customer_orders")
