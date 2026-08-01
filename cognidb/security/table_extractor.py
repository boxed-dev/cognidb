"""Extract table names / primary operation from SQL for allowlist checks.

Thin delegation to :mod:`cognidb.security.sql_guard`, the single AST source of
truth. No regex or sqlparse: the audit proved textual table extraction
bypassable (comma-joins, schema-qualified and bracket-quoted identifiers hid
tables from the old regex). sqlglot's parse tree cannot be fooled the same way.
"""

from __future__ import annotations

from . import sql_guard


def extract_tables(sql: str, dialect: str | None = None) -> list[str]:
    """
    Lowercased base-table names (CTE aliases and derived-table aliases excluded).

    Fails closed to ``[]`` on unparseable SQL, preserving the historical
    never-raise contract. In the pipeline the validator rejects unparseable SQL
    before this is ever reached.
    """
    try:
        refs = sql_guard.extract_table_refs(sql, dialect)
    except sql_guard.GuardError:
        return []
    out: list[str] = []
    for ref in refs:
        if ref.name and ref.name not in out:
            out.append(ref.name)
    return out


def extract_primary_operation(sql: str, dialect: str | None = None) -> str:
    """
    Primary operation keyword of the first statement.

    SELECT/INSERT/UPDATE/DELETE/MERGE for those, or the node type name uppercased
    (e.g. DROP, ALTER, COMMAND) for anything else. Returns ``"UNKNOWN"`` on
    unparseable SQL, preserving the historical never-raise contract.
    """
    try:
        return sql_guard.primary_operation(sql, dialect)
    except sql_guard.GuardError:
        return "UNKNOWN"
