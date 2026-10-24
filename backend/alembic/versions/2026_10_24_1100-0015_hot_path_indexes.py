"""índices do caminho quente e unicidade de Contact/Conversation, com fusão das duplicatas existentes

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-24 11:00:00.000000

Contact `(instance_id, remote_jid)` e Conversation `(instance_id, contact_id)` eram SELECT-then-INSERT sem unique:
o history sync, em paralelo ao consumer, podia duplicar os dois. Antes de criar as unicidades a migração funde as
duplicatas que já existem: fica o registro mais antigo, todo filho que aponta para um duplicado é reapontado
(descoberto pelas FKs do banco, sem lista fixa) e os campos que carregam estado são mesclados. A fusão NÃO é
desfeita no downgrade.
"""
import logging
from itertools import groupby

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

_PRIORITY_RANK = {"low": 0, "normal": 1, "high": 2, "urgent": 3}


def _first(rows, column):
    return next((row[column] for row in rows if row[column] is not None), None)


def _latest(rows, column):
    values = [row[column] for row in rows if row[column] is not None]
    return max(values) if values else None


def _combine_contact(rows) -> dict:
    """`rows[0]` é o Contact mais antigo (o que fica). Os demais só preenchem o que ele não tem."""
    survivor = rows[0]

    def is_real_name(row):
        return bool(row["name"]) and row["name"] != row["phone_number"]

    named = next((row for row in rows if is_real_name(row)), survivor)
    return {
        "name": named["name"] if is_real_name(named) else survivor["name"],
        "push_name": _first(rows, "push_name"),
        "profile_pic_url": _first(rows, "profile_pic_url"),
        "is_blocked": any(row["is_blocked"] for row in rows),
        "is_business": any(row["is_business"] for row in rows),
        "last_seen": _latest(rows, "last_seen"),
        "notes": _first(rows, "notes"),
        "updated_at": _latest(rows, "updated_at"),
    }


def _combine_conversation(rows) -> dict:
    """`rows[0]` é a Conversation mais antiga (a que fica).

    - `unread_count`: soma (cada duplicada contou as próprias Messages não lidas).
    - `last_message_*` e as datas de Session: da Conversation com a Message mais recente.
    - Handoff: `human_in_loop` se qualquer uma tinha; `human_handoff_reason` e `ticket_id` vêm da mesma
      Conversation, preferindo a que tem Ticket (a mais antiga entre elas), para o par nunca se separar.
    """
    newest = max(rows, key=lambda row: (row["last_message_at"] is not None, row["last_message_at"] or 0))
    in_handoff = [row for row in rows if row["human_in_loop"]]
    handoff = next((row for row in in_handoff if row["ticket_id"]), in_handoff[0] if in_handoff else None)
    priority = max((row["priority"] for row in rows if row["priority"]), key=lambda p: _PRIORITY_RANK.get(p, 1), default=None)
    return {
        "is_active": any(row["is_active"] for row in rows),
        "is_archived": all(row["is_archived"] for row in rows),
        "is_group": any(row["is_group"] for row in rows),
        "unread_count": sum(row["unread_count"] or 0 for row in rows),
        "last_message_at": newest["last_message_at"],
        "last_message_preview": newest["last_message_preview"],
        "session_started_at": newest["session_started_at"],
        "previous_session_started_at": newest["previous_session_started_at"],
        "assigned_agent_id": _first(rows, "assigned_agent_id"),
        "human_in_loop": handoff is not None,
        "human_handoff_reason": handoff["human_handoff_reason"] if handoff else None,
        "ticket_id": handoff["ticket_id"] if handoff else None,
        "tags": _first(rows, "tags"),
        "priority": priority,
        "rating": _first(rows, "rating"),
        "updated_at": _latest(rows, "updated_at"),
    }


def _child_references(inspector, target: str) -> list[tuple[str, str, bool]]:
    """(tabela, coluna, é_única) de cada FK de coluna única para `target.id`, lida do banco."""
    found = []
    for table in inspector.get_table_names():
        unique_sets = [set(inspector.get_pk_constraint(table).get("constrained_columns") or [])]
        unique_sets += [set(c["column_names"]) for c in inspector.get_unique_constraints(table)]
        unique_sets += [
            set(i["column_names"])
            for i in inspector.get_indexes(table)
            if i.get("unique") and not i.get("dialect_options", {}).get("postgresql_where")
        ]
        for fk in inspector.get_foreign_keys(table):
            if fk["referred_table"] == target and fk["referred_columns"] == ["id"] and len(fk["constrained_columns"]) == 1:
                column = fk["constrained_columns"][0]
                found.append((table, column, {column} in unique_sets))
    return found


def _repoint(bind, merge_map, table: str, column: str, unique: bool, groups) -> None:
    child = sa.table(table, sa.column(column))
    if unique:
        # No máximo uma linha por pai (ex.: o Summary da Conversation): fica a da Conversation mais antiga que tinha uma.
        present = {row[0] for row in bind.execute(sa.select(child.c[column]).where(child.c[column].in_(
            [row["id"] for rows in groups for row in rows]
        )))}
        for rows in groups:
            owners = [row["id"] for row in rows if row["id"] in present]
            for extra in owners[1:]:
                bind.execute(sa.delete(child).where(child.c[column] == extra))
            if owners and owners[0] != rows[0]["id"]:
                bind.execute(sa.update(child).where(child.c[column] == owners[0]).values({column: rows[0]["id"]}))
        return
    survivor = sa.select(merge_map.c.survivor_id).where(merge_map.c.loser_id == child.c[column]).scalar_subquery()
    bind.execute(
        sa.update(child)
        .where(child.c[column].in_(sa.select(merge_map.c.loser_id)))
        .values({column: survivor})
    )


def _merge_duplicates(bind, table_name: str, key_columns: list[str], combine) -> int:
    """Funde as linhas de `table_name` com a mesma chave natural; devolve quantas linhas foram removidas."""
    table = sa.Table(table_name, sa.MetaData(), autoload_with=bind)
    key = [table.c[name] for name in key_columns]
    duplicated = sa.select(*key).group_by(*key).having(sa.func.count() > 1)
    rows = bind.execute(
        sa.select(table)
        .where(sa.tuple_(*key).in_(duplicated))
        .order_by(*key, table.c.created_at.asc().nullslast(), table.c.id.asc())
    ).mappings().all()
    groups = [list(group) for _, group in groupby(rows, key=lambda row: tuple(row[name] for name in key_columns))]
    if not groups:
        return 0

    merge_map = sa.Table(
        f"_merge_{table_name}",
        sa.MetaData(),
        sa.Column("loser_id", sa.String, primary_key=True),
        sa.Column("survivor_id", sa.String, nullable=False),
        prefixes=["TEMPORARY"],
    )
    merge_map.create(bind)
    try:
        bind.execute(
            sa.insert(merge_map),
            [{"loser_id": loser["id"], "survivor_id": group[0]["id"]} for group in groups for loser in group[1:]],
        )
        for child_table, column, unique in _child_references(sa.inspect(bind), table_name):
            _repoint(bind, merge_map, child_table, column, unique, groups)

        merged = [(group[0]["id"], combine(group)) for group in groups]
        for survivor_id, values in merged:
            bind.execute(sa.update(table).where(table.c.id == survivor_id).values(values))
        removed = bind.execute(sa.delete(table).where(table.c.id.in_(sa.select(merge_map.c.loser_id)))).rowcount
    finally:
        merge_map.drop(bind)
    return removed


def upgrade() -> None:
    bind = op.get_bind()
    # Contacts primeiro: reapontar as Conversations de um Contact duplicado é o que gera Conversations duplicadas.
    contacts = _merge_duplicates(bind, 'contacts', ['instance_id', 'remote_jid'], _combine_contact)
    conversations = _merge_duplicates(bind, 'conversations', ['instance_id', 'contact_id'], _combine_conversation)
    (log.warning if contacts or conversations else log.info)(
        "0015: fundiu %d Contact(s) e %d Conversation(s) duplicados "
        "(ficou o registro mais antigo; Messages, Orders, Tickets e demais filhos foram reapontados)",
        contacts,
        conversations,
    )

    op.create_unique_constraint('uq_contacts_instance_remote_jid', 'contacts', ['instance_id', 'remote_jid'])
    op.create_unique_constraint('uq_conversations_instance_contact', 'conversations', ['instance_id', 'contact_id'])
    op.create_index('ix_conversations_contact_id', 'conversations', ['contact_id'], unique=False)
    op.create_index(
        'ix_conversations_instance_last_message_at',
        'conversations',
        ['instance_id', sa.text('last_message_at DESC NULLS LAST')],
        unique=False,
    )
    op.create_index('ix_messages_conversation_timestamp', 'messages', ['conversation_id', 'timestamp', 'id'], unique=False)
    op.create_index('ix_messages_instance_timestamp', 'messages', ['instance_id', 'timestamp'], unique=False)


def downgrade() -> None:
    # Só remove índices e unicidades. As duplicatas fundidas no upgrade não voltam: os registros removidos e o
    # estado que tinham antes da mesclagem não são guardados em lugar nenhum.
    op.drop_index('ix_messages_instance_timestamp', table_name='messages')
    op.drop_index('ix_messages_conversation_timestamp', table_name='messages')
    op.drop_index('ix_conversations_instance_last_message_at', table_name='conversations')
    op.drop_index('ix_conversations_contact_id', table_name='conversations')
    op.drop_constraint('uq_conversations_instance_contact', 'conversations', type_='unique')
    op.drop_constraint('uq_contacts_instance_remote_jid', 'contacts', type_='unique')
