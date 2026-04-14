"""merge sku_stock and agent_types

Revision ID: h3i4j5k6l8m9
Revises: f1e2d3c4b5a6, g2h3i4j5k6l7
Create Date: 2026-04-14 00:03:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "h3i4j5k6l8m9"
down_revision: Union[str, None] = ("f1e2d3c4b5a6", "g2h3i4j5k6l7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Migration de merge - não precisa de alterações
    pass


def downgrade() -> None:
    # Para downgrade, precisamos remover as migrations que foram mergeadas
    # Isso geralmente não é recomendado, mas está aqui para completude
    pass
