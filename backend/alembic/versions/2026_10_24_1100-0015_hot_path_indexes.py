"""índices do caminho quente e unicidade de Contact/Conversation, com fusão das duplicatas existentes

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-24 11:00:00.000000

Contact `(instance_id, remote_jid)` e Conversation `(instance_id, contact_id)` eram SELECT-then-INSERT sem unique:
o history sync, em paralelo ao consumer, podia duplicar os dois. Antes de criar as unicidades a migração funde as
duplicatas que já existem: fica o registro mais antigo, todo filho que aponta para um duplicado é reapontado
(descoberto pelas FKs do banco, sem lista fixa) e os campos que carregam estado são mesclados. A fusão NÃO é
desfeita no downgrade.

Fusão de Conversations:
- Summary (filho de chave única): fica o de maior `message_count`, reapontado para a Conversation que ficou. O
  `covered_until_message_id` dele passa a ser um cursor sobre as Messages intercaladas das Conversations fundidas
  (ordenadas por `timestamp`); como o cursor vinha de uma sequência só, pode sobrar uma lacuna de memória: Messages
  da outra Conversation anteriores ao cursor que o Summary nunca resumiu. O próximo `refresh_summary` recalcula.
- Dois Handoffs abertos: `ticket_id` fica com um (o da Conversation mais antiga em Handoff) e o outro Ticket aberto
  é fechado (`closed`, como o `release` faz), para não ficar Ticket aberto sem vínculo.

Locks e janela de manutenção: tudo roda numa transação só. Os `CREATE INDEX` de `messages` vêm primeiro (SHARE em
`messages`: bloqueia escrita) e os `ADD CONSTRAINT UNIQUE` por último (ACCESS EXCLUSIVE em contacts/conversations,
até o commit). Mesmo assim é REQUERIDA uma janela de manutenção: pare a API e o worker antes do `upgrade`. Um insert
concorrente pode recriar duplicata depois da fusão e fazer o `ADD CONSTRAINT` falhar, e a migração inteira sofre
rollback. O tempo cresce com o tamanho de `messages` (construção dos dois índices e reapontamento das Messages).
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
_OPEN_TICKET_STATUSES = ("open", "in_progress")  # os mesmos de `handoff_service.OPEN_STATUSES`
# Filho de chave única com mais de um candidato: vale o de maior valor nesta coluna (ADR 0003: o Summary que cobre mais).
_UNIQUE_CHILD_RANK = {"conversation_summaries": "message_count"}


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


def _repoint(bind, merge_map, table: str, column: str, unique: bool) -> None:
    """Reaponta `table.column` dos registros removidos para os que ficaram, via subquery na tabela de mapeamento."""
    if unique:
        _repoint_unique(bind, merge_map, table, column)
        return
    child = sa.table(table, sa.column(column))
    losers = sa.select(merge_map.c.member_id).where(merge_map.c.member_id != merge_map.c.survivor_id)
    survivor = sa.select(merge_map.c.survivor_id).where(merge_map.c.member_id == child.c[column]).scalar_subquery()
    bind.execute(sa.update(child).where(child.c[column].in_(losers)).values({column: survivor}))


def _repoint_unique(bind, merge_map, table: str, column: str) -> None:
    """Filho de chave única (no máximo uma linha por pai): sobra uma linha por grupo, com o pai que ficou.

    Vale a de maior `_UNIQUE_CHILD_RANK[table]`, se a tabela tiver ranking; empate (ou sem ranking) fica com a do
    registro mais antigo do grupo.
    """
    rank = _UNIQUE_CHILD_RANK.get(table)
    child = sa.table(table, sa.column(column), *([sa.column(rank)] if rank else []))
    owners = bind.execute(
        sa.select(child.c[column], merge_map.c.survivor_id, merge_map.c.ordem, *([child.c[rank]] if rank else []))
        .select_from(child.join(merge_map, child.c[column] == merge_map.c.member_id))
    ).mappings().all()
    by_survivor: dict = {}
    for row in owners:
        by_survivor.setdefault(row["survivor_id"], []).append(row)
    extras, moves = [], []
    for survivor_id, rows in by_survivor.items():
        winner = min(rows, key=lambda row: (-(row[rank] or 0) if rank else 0, row["ordem"]))
        extras += [row[column] for row in rows if row is not winner]
        if winner[column] != survivor_id:
            moves.append({"old_owner": winner[column], "new_owner": survivor_id})
    if extras:
        bind.execute(sa.delete(child).where(child.c[column] == sa.bindparam("owner")), [{"owner": x} for x in extras])
    if moves:
        bind.execute(
            sa.update(child).where(child.c[column] == sa.bindparam("old_owner")).values({column: sa.bindparam("new_owner")}),
            moves,
        )


def _close_orphan_tickets(bind, merge_map) -> None:
    """Fecha o Ticket aberto que ficou sem vínculo: duas Conversations em Handoff fundiam dois Tickets abertos e só
    um cabe em `conversations.ticket_id`. Mesmo estado que o `release` grava (`closed`, `closed_at`, `updated_at`)."""
    tickets = sa.table(
        "tickets", sa.column("id"), sa.column("conversation_id"), sa.column("status"),
        sa.column("closed_at"), sa.column("updated_at"),
    )
    conversations = sa.table("conversations", sa.column("id"), sa.column("ticket_id"))
    merged = sa.select(merge_map.c.survivor_id).where(merge_map.c.member_id != merge_map.c.survivor_id)
    kept = sa.select(conversations.c.ticket_id).where(conversations.c.id == tickets.c.conversation_id).scalar_subquery()
    bind.execute(
        sa.update(tickets)
        .where(
            tickets.c.conversation_id.in_(merged),
            tickets.c.status.in_(_OPEN_TICKET_STATUSES),
            sa.or_(kept.is_(None), tickets.c.id != kept),
        )
        .values(status="closed", closed_at=sa.func.now(), updated_at=sa.func.now())
    )


def _merge_duplicates(bind, table_name: str, key_columns: list[str], combine, finish=None) -> int:
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

    # Mapeamento membro -> quem fica (o mais antigo mapeia para si mesmo). Some no commit da migração.
    merge_map = sa.Table(
        f"_merge_{table_name}",
        sa.MetaData(),
        sa.Column("member_id", sa.String, primary_key=True),
        sa.Column("survivor_id", sa.String, nullable=False),
        sa.Column("ordem", sa.Integer, nullable=False),
        prefixes=["TEMPORARY"],
        postgresql_on_commit="DROP",
    )
    merge_map.create(bind)
    bind.execute(
        sa.insert(merge_map),
        [
            {"member_id": member["id"], "survivor_id": group[0]["id"], "ordem": ordem}
            for group in groups
            for ordem, member in enumerate(group)
        ],
    )
    for child_table, column, unique in _child_references(sa.inspect(bind), table_name):
        _repoint(bind, merge_map, child_table, column, unique)

    for group in groups:
        bind.execute(sa.update(table).where(table.c.id == group[0]["id"]).values(combine(group)))
    if finish:
        finish(bind, merge_map)
    losers = sa.select(merge_map.c.member_id).where(merge_map.c.member_id != merge_map.c.survivor_id)
    return bind.execute(sa.delete(table).where(table.c.id.in_(losers))).rowcount


def upgrade() -> None:
    bind = op.get_bind()
    # Os índices de `messages` (a tabela grande) vêm ANTES da fusão e das unicidades: cada `CREATE INDEX` segura
    # SHARE em `messages` até o commit, e o `ADD CONSTRAINT UNIQUE` segura ACCESS EXCLUSIVE em contacts/conversations
    # até o commit também. Nessa ordem o ACCESS EXCLUSIVE só começa no fim, depois do trabalho mais demorado.
    op.create_index('ix_messages_conversation_timestamp', 'messages', ['conversation_id', 'timestamp', 'id'], unique=False)
    op.create_index('ix_messages_instance_timestamp', 'messages', ['instance_id', 'timestamp'], unique=False)
    op.create_index('ix_conversations_contact_id', 'conversations', ['contact_id'], unique=False)
    op.create_index(
        'ix_conversations_instance_last_message_at',
        'conversations',
        ['instance_id', sa.text('last_message_at DESC NULLS LAST')],
        unique=False,
    )

    # Contacts primeiro: reapontar as Conversations de um Contact duplicado é o que gera Conversations duplicadas.
    contacts = _merge_duplicates(bind, 'contacts', ['instance_id', 'remote_jid'], _combine_contact)
    conversations = _merge_duplicates(
        bind, 'conversations', ['instance_id', 'contact_id'], _combine_conversation, finish=_close_orphan_tickets
    )
    (log.warning if contacts or conversations else log.info)(
        "0015: fundiu %d Contact(s) e %d Conversation(s) duplicados "
        "(ficou o registro mais antigo; Messages, Orders, Tickets e demais filhos foram reapontados)",
        contacts,
        conversations,
    )

    op.create_unique_constraint('uq_contacts_instance_remote_jid', 'contacts', ['instance_id', 'remote_jid'])
    op.create_unique_constraint('uq_conversations_instance_contact', 'conversations', ['instance_id', 'contact_id'])


def downgrade() -> None:
    # Só remove índices e unicidades. As duplicatas fundidas no upgrade não voltam: os registros removidos e o
    # estado que tinham antes da mesclagem não são guardados em lugar nenhum.
    op.drop_index('ix_messages_instance_timestamp', table_name='messages')
    op.drop_index('ix_messages_conversation_timestamp', table_name='messages')
    op.drop_index('ix_conversations_instance_last_message_at', table_name='conversations')
    op.drop_index('ix_conversations_contact_id', table_name='conversations')
    op.drop_constraint('uq_conversations_instance_contact', 'conversations', type_='unique')
    op.drop_constraint('uq_contacts_instance_remote_jid', 'contacts', type_='unique')
