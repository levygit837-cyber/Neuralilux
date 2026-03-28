"""create super agent tables

Revision ID: a1b2c3d4e5f6
Revises: b7c91c2f3d4e
Create Date: 2026-03-27 23:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "b7c91c2f3d4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Super Agent Sessions
    op.create_table(
        "super_agent_sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("company_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("interaction_count", sa.Integer(), nullable=True),
        sa.Column("last_checkpoint_at", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_super_agent_sessions_company_id"), "super_agent_sessions", ["company_id"], unique=False)
    op.create_index(op.f("ix_super_agent_sessions_user_id"), "super_agent_sessions", ["user_id"], unique=False)

    # Super Agent Messages
    op.create_table(
        "super_agent_messages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("tool_name", sa.String(length=100), nullable=True),
        sa.Column("tool_input", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tool_output", sa.Text(), nullable=True),
        sa.Column("thinking_content", sa.Text(), nullable=True),
        sa.Column("extra_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["super_agent_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_super_agent_messages_session_id"), "super_agent_messages", ["session_id"], unique=False)

    # Super Agent Checkpoints
    op.create_table(
        "super_agent_checkpoints",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("interaction_number", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("context_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["super_agent_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "interaction_number", name="uq_checkpoint_session_number"),
    )
    op.create_index(op.f("ix_super_agent_checkpoints_session_id"), "super_agent_checkpoints", ["session_id"], unique=False)

    # Super Agent Knowledge
    op.create_table(
        "super_agent_knowledge",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("company_id", sa.String(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("source_session_id", sa.String(), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=True),
        sa.Column("access_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["source_session_id"], ["super_agent_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "category", "key", name="uq_knowledge_company_category_key"),
    )
    op.create_index(op.f("ix_super_agent_knowledge_company_id"), "super_agent_knowledge", ["company_id"], unique=False)
    op.create_index(op.f("ix_super_agent_knowledge_category"), "super_agent_knowledge", ["category"], unique=False)

    # Super Agent Documents
    op.create_table(
        "super_agent_documents",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("company_id", sa.String(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("content_base64", sa.Text(), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["super_agent_sessions.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_super_agent_documents_session_id"), "super_agent_documents", ["session_id"], unique=False)
    op.create_index(op.f("ix_super_agent_documents_company_id"), "super_agent_documents", ["company_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_super_agent_documents_company_id"), table_name="super_agent_documents")
    op.drop_index(op.f("ix_super_agent_documents_session_id"), table_name="super_agent_documents")
    op.drop_table("super_agent_documents")

    op.drop_index(op.f("ix_super_agent_knowledge_category"), table_name="super_agent_knowledge")
    op.drop_index(op.f("ix_super_agent_knowledge_company_id"), table_name="super_agent_knowledge")
    op.drop_table("super_agent_knowledge")

    op.drop_index(op.f("ix_super_agent_checkpoints_session_id"), table_name="super_agent_checkpoints")
    op.drop_table("super_agent_checkpoints")

    op.drop_index(op.f("ix_super_agent_messages_session_id"), table_name="super_agent_messages")
    op.drop_table("super_agent_messages")

    op.drop_index(op.f("ix_super_agent_sessions_user_id"), table_name="super_agent_sessions")
    op.drop_index(op.f("ix_super_agent_sessions_company_id"), table_name="super_agent_sessions")
    op.drop_table("super_agent_sessions")