"""Extract column references from SQL for allowlist checks (ADR 0005).

Backed entirely by :func:`cognidb.security.sql_guard.analyze` — the single AST
source of truth — so there is exactly one parser and no bypassable regex. A
permissive operation superset is used purely so extraction never gates on the
operation; the real gating happens in the validator/pipeline.
"""

from __future__ import annotations

from . import sql_guard

# Permissive superset: extraction must work for any read/write shape without
# rejecting on operation. Security gating is enforced elsewhere by the guard.
_ALL_OPERATIONS = frozenset({"SELECT", "INSERT", "UPDATE", "DELETE", "MERGE"})


def extract_columns(sql: str, dialect: str | None = None) -> list[str]:
    """
    Flat list of referenced column names (lowercased) across all tables.

    ``SELECT *`` yields ``["*"]``. Unparseable or non-analyzable SQL fails
    closed to ``[]``.
    """
    by_table = _columns_by_table(sql, dialect)
    if not by_table:
        return []
    out: list[str] = []
    for cols in by_table.values():
        for col in cols:
            if col not in out:
                out.append(col)
    return out


def extract_columns_by_table(
    sql: str, tables: list[str], dialect: str | None = None
) -> dict[str, list[str]]:
    """
    Map each requested table to the columns the guard attributed to it.

    Qualified columns are attributed precisely; ``SELECT *`` surfaces ``"*"`` so
    a column allowlist can fail closed. Unparseable SQL yields an empty column
    list per table.
    """
    if not tables:
        return {}
    by_table = _columns_by_table(sql, dialect)
    if by_table is None:
        return {table: [] for table in tables}
    return {table: list(_lookup(by_table, table)) for table in tables}


def _columns_by_table(
    sql: str, dialect: str | None
) -> dict[str, tuple[str, ...]] | None:
    """Return the guard's ``columns_by_table`` or ``None`` on any GuardError."""
    try:
        result = sql_guard.analyze(
            sql, dialect=dialect, allowed_operations=_ALL_OPERATIONS
        )
    except sql_guard.GuardError:
        return None
    return result.columns_by_table


def _lookup(by_table: dict[str, tuple[str, ...]], table: str) -> tuple[str, ...]:
    """Match a base table name against guard keys (which may be schema-qualified)."""
    if table in by_table:
        return by_table[table]
    for key, cols in by_table.items():
        if key.rsplit(".", 1)[-1] == table:
            return cols
    return ()
