"""merge super agent and agent enabled

Revision ID: 0786eca9ce47
Revises: add_agent_enabled_001, a1b2c3d4e5f6
Create Date: 2026-03-27 21:04:13.562284

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0786eca9ce47'
down_revision = ('add_agent_enabled_001', 'a1b2c3d4e5f6')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
