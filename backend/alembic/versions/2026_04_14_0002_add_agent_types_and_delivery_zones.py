"""add agent types and delivery zones

Revision ID: g2h3i4j5k6l7
Revises: f1e2d3c4b5a6
Create Date: 2026-04-14 00:02:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "g2h3i4j5k6l7"
down_revision: Union[str, None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    # Add agent_type column to agents table
    agents_columns = {column["name"] for column in inspector.get_columns("agents")}
    if "agent_type" not in agents_columns:
        op.add_column(
            "agents",
            sa.Column("agent_type", sa.String(), nullable=False, server_default="sales"),
        )
    
    # Add active_agent_type column to conversations table
    conversations_columns = {column["name"] for column in inspector.get_columns("conversations")}
    if "active_agent_type" not in conversations_columns:
        op.add_column(
            "conversations",
            sa.Column("active_agent_type", sa.String(), nullable=False, server_default="sales"),
        )
    
    # Create delivery_zones table
    op.create_table(
        "delivery_zones",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("neighborhoods", postgresql.JSONB(), nullable=False),
        sa.Column("delivery_fee", sa.Numeric(10, 2), nullable=False),
        sa.Column("minimum_order_value", sa.Numeric(10, 2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id")
    )
    
    # Insert sample delivery zones
    op.execute("""
        INSERT INTO delivery_zones (id, name, neighborhoods, delivery_fee, minimum_order_value, is_active)
        VALUES 
            ('zone_001', 'Centro', '["Centro", "Centro Histórico"]', 5.00, 30.00, true),
            ('zone_002', 'Zona Norte', '["Vila Nova", "Jardim das Flores", "Parque Industrial"]', 8.00, 30.00, true),
            ('zone_003', 'Zona Sul', '["Vila Maria", "Jardim América", "Parque das Nações"]', 10.00, 30.00, true)
    """)


def downgrade() -> None:
    # Drop delivery_zones table
    op.drop_table("delivery_zones")
    
    # Remove active_agent_type from conversations
    op.drop_column("conversations", "active_agent_type")
    
    # Remove agent_type from agents
    op.drop_column("agents", "agent_type")
