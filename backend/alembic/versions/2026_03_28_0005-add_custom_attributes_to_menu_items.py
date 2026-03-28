"""add custom attributes to menu items

Revision ID: d9e8f7a6b5c4
Revises: a1b2c3d4e5f6
Create Date: 2026-03-28 00:05:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "d9e8f7a6b5c4"
down_revision: Union[str, None] = "0786eca9ce47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("menu_items")}

    if "custom_attributes" in existing_columns:
        op.execute("UPDATE menu_items SET custom_attributes = '[]'::jsonb WHERE custom_attributes IS NULL")
        op.alter_column("menu_items", "custom_attributes", nullable=False)
        return

    op.add_column(
        "menu_items",
        sa.Column(
            "custom_attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.execute("UPDATE menu_items SET custom_attributes = '[]'::jsonb WHERE custom_attributes IS NULL")
    op.alter_column("menu_items", "custom_attributes", nullable=False)


def downgrade() -> None:
    op.drop_column("menu_items", "custom_attributes")
