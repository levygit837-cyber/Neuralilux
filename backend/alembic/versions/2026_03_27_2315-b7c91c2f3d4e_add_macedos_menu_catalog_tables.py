"""add macedos menu catalog tables

Revision ID: b7c91c2f3d4e
Revises: 8f3d1b2c4a6e
Create Date: 2026-03-27 23:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b7c91c2f3d4e"
down_revision: Union[str, None] = "8f3d1b2c4a6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "menu_catalogs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("company_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column("source_file", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "name", name="uq_menu_catalog_company_name"),
    )
    op.create_index(op.f("ix_menu_catalogs_company_id"), "menu_catalogs", ["company_id"], unique=False)

    op.create_table(
        "menu_categories",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("catalog_id", sa.String(), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["catalog_id"], ["menu_catalogs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("catalog_id", "external_id", name="uq_menu_category_catalog_external"),
    )
    op.create_index(op.f("ix_menu_categories_catalog_id"), "menu_categories", ["catalog_id"], unique=False)
    op.create_index(op.f("ix_menu_categories_external_id"), "menu_categories", ["external_id"], unique=False)

    op.create_table(
        "menu_items",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("catalog_id", sa.String(), nullable=False),
        sa.Column("category_id", sa.String(), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("is_available", sa.Boolean(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["catalog_id"], ["menu_catalogs.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["menu_categories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("catalog_id", "external_id", name="uq_menu_item_catalog_external"),
    )
    op.create_index(op.f("ix_menu_items_catalog_id"), "menu_items", ["catalog_id"], unique=False)
    op.create_index(op.f("ix_menu_items_category_id"), "menu_items", ["category_id"], unique=False)
    op.create_index(op.f("ix_menu_items_external_id"), "menu_items", ["external_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_menu_items_external_id"), table_name="menu_items")
    op.drop_index(op.f("ix_menu_items_category_id"), table_name="menu_items")
    op.drop_index(op.f("ix_menu_items_catalog_id"), table_name="menu_items")
    op.drop_table("menu_items")

    op.drop_index(op.f("ix_menu_categories_external_id"), table_name="menu_categories")
    op.drop_index(op.f("ix_menu_categories_catalog_id"), table_name="menu_categories")
    op.drop_table("menu_categories")

    op.drop_index(op.f("ix_menu_catalogs_company_id"), table_name="menu_catalogs")
    op.drop_table("menu_catalogs")
