"""add missing message columns

Revision ID: 8f3d1b2c4a6e
Revises: 426b4265a918
Create Date: 2026-03-27 19:55:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8f3d1b2c4a6e"
down_revision: Union[str, None] = "426b4265a918"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("conversation_id", sa.String(), nullable=True))
    op.add_column(
        "messages",
        sa.Column("message_type", sa.String(), nullable=True, server_default="text"),
    )
    op.add_column("messages", sa.Column("caption", sa.Text(), nullable=True))
    op.add_column("messages", sa.Column("latitude", sa.Numeric(10, 8), nullable=True))
    op.add_column("messages", sa.Column("longitude", sa.Numeric(11, 8), nullable=True))
    op.create_foreign_key(
        "messages_conversation_id_fkey",
        "messages",
        "conversations",
        ["conversation_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("messages_conversation_id_fkey", "messages", type_="foreignkey")
    op.drop_column("messages", "longitude")
    op.drop_column("messages", "latitude")
    op.drop_column("messages", "caption")
    op.drop_column("messages", "message_type")
    op.drop_column("messages", "conversation_id")
