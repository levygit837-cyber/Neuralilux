"""add agent_enabled to instances

Revision ID: add_agent_enabled_001
Revises: b7c91c2f3d4e
Create Date: 2026-03-27 21:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_agent_enabled_001'
down_revision: Union[str, None] = 'b7c91c2f3d4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('instances', sa.Column('agent_enabled', sa.Boolean(), nullable=True, server_default='true'))


def downgrade() -> None:
    op.drop_column('instances', 'agent_enabled')