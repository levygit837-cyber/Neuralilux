"""add rating to conversations

Revision ID: f5a6b7c8d9e0
Revises: e4f1a2b3c4d5
Create Date: 2026-04-09 00:01:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, None] = "e4f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("rating", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "rating")
