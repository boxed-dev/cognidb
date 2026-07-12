"""Extract table names from SQL for allowlist checks."""

from __future__ import annotations

import re
from typing import List, Set

import sqlparse
from sqlparse.tokens import Keyword, DML


_TABLE_KW = frozenset({
    "FROM", "JOIN", "INTO", "UPDATE", "TABLE",
    "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL JOIN", "CROSS JOIN",
})


def extract_tables(sql: str) -> List[str]:
    """Best-effort base table names (lowercased), not column names."""
    tables: Set[str] = set()
    # Primary: keyword-anchored regex (more reliable than walking all identifiers)
    pattern = re.compile(
        r"\b(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+([`\"\[\]]?)([A-Za-z_][A-Za-z0-9_]*)\1",
        re.IGNORECASE,
    )
    for m in pattern.finditer(sql):
        tables.add(m.group(2).lower())
    # sqlparse assist for odd quoting
    try:
        for statement in sqlparse.parse(sql):
            from_seen = False
            for token in statement.flatten():
                up = token.value.upper()
                if token.ttype is Keyword or token.ttype is DML:
                    if up in _TABLE_KW or up.endswith(" JOIN"):
                        from_seen = True
                    elif from_seen and token.ttype is Keyword:
                        from_seen = up in _TABLE_KW or up.endswith(" JOIN")
                    continue
                if from_seen and token.ttype is None and token.value.strip():
                    name = token.value.strip().strip('`"[]')
                    if name and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
                        tables.add(name.lower())
                    from_seen = False
    except Exception:
        pass
    return sorted(tables)


def extract_primary_operation(sql: str) -> str:
    """Return primary DML/DDL keyword uppercased."""
    parsed = sqlparse.parse(sql)
    if not parsed:
        return "UNKNOWN"
    for token in parsed[0].flatten():
        if token.ttype in (DML, Keyword) and token.value.upper() in {
            "SELECT", "INSERT", "UPDATE", "DELETE", "DROP", "CREATE",
            "ALTER", "TRUNCATE", "WITH",
        }:
            val = token.value.upper()
            return "SELECT" if val == "WITH" else val
    return "UNKNOWN"
