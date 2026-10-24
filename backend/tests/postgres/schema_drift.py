"""Comparador entre a metadata dos models e o schema de um banco migrado (Alembic autogenerate)."""
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import MetaData
from sqlalchemy.engine import Connection


def _describe(diff) -> list[str]:
    """Uma linha legível por diferença; `modify_*` chega como lista de tuplas."""
    if isinstance(diff, list):
        return [line for part in diff for line in _describe(part)]
    op, *rest = diff
    if op in ("add_column", "remove_column"):
        _schema, table, column = rest
        return [f"{op}: {table}.{column.name}"]
    if op in ("add_table", "remove_table"):
        return [f"{op}: {rest[0].name}"]
    if op in ("add_index", "remove_index", "add_constraint", "remove_constraint", "add_fk", "remove_fk"):
        obj = rest[0]
        table = getattr(obj, "table", None)
        return [f"{op}: {obj.name} em {table.name if table is not None else '?'}"]
    if op.startswith("modify_"):
        _schema, table, column, _kwargs, existing, new = rest
        return [f"{op}: {table}.{column} no banco={existing!r}, no model={new!r}"]
    return [f"{op}: {rest!r}"]


def schema_diff(connection: Connection, metadata: MetaData) -> list[str]:
    """Diferenças entre `metadata` e o schema real; lista vazia quando batem (tipos e defaults inclusos)."""
    context = MigrationContext.configure(
        connection, opts={"compare_type": True, "compare_server_default": True}
    )
    return [line for diff in compare_metadata(context, metadata) for line in _describe(diff)]
