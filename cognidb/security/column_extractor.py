"""Extract column references from SQL for allowlist checks (ADR 0005)."""

from __future__ import annotations

import re
from typing import Dict, List, Tuple


def extract_columns(sql: str) -> List[str]:
    """
    Extract projected / declared column names (lowercased).

    SELECT * yields ``['*']``. INSERT without an explicit column list also
    yields ``['*']`` so allowlists can fail closed.
    """
    sql = (sql or "").strip()
    if not sql:
        return []

    op_m = re.match(r"^\s*(SELECT|INSERT|UPDATE|DELETE)\b", sql, re.IGNORECASE)
    if not op_m:
        return []

    op = op_m.group(1).upper()
    if op == "SELECT":
        return _select_columns(sql)
    if op == "INSERT":
        return _insert_columns(sql)
    return []


def extract_columns_by_table(sql: str, tables: List[str]) -> Dict[str, List[str]]:
    """
    Map each table to columns for allowlist checks.

    Single-table queries attribute all projected columns to that table.
    Multi-table queries use qualified ``table.col`` refs when present;
    otherwise every table is checked against the full projection (fail-closed).
    """
    cols = extract_columns(sql)
    if not tables:
        return {}
    if len(tables) == 1:
        return {tables[0]: cols}

    result: Dict[str, List[str]] = {t: [] for t in tables}
    qualified = _qualified_select_columns(sql)
    if qualified:
        for table, col in qualified:
            if table in result:
                result[table].append(col)
            else:
                for t in tables:
                    result[t].append(col)
        return result

    for t in tables:
        result[t] = list(cols)
    return result


def _select_columns(sql: str) -> List[str]:
    m = re.search(
        r"\bSELECT\s+(?:DISTINCT\s+)?(.+?)\s+FROM\b",
        sql,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return []
    proj = m.group(1).strip()
    if proj == "*":
        return ["*"]
    out: List[str] = []
    for part in proj.split(","):
        part = re.sub(r"\s+AS\s+[A-Za-z_][A-Za-z0-9_]*$", "", part, flags=re.IGNORECASE)
        part = part.strip().strip('`"[]')
        if not part:
            continue
        if "." in part:
            part = part.split(".")[-1].strip().strip('`"[]')
        out.append("*" if part == "*" else part.lower())
    return out


def _insert_columns(sql: str) -> List[str]:
    m = re.search(
        r"\bINSERT\s+INTO\s+[A-Za-z_][A-Za-z0-9_]*\s*\(([^)]+)\)",
        sql,
        re.IGNORECASE,
    )
    if not m:
        return ["*"]
    return [
        c.strip().strip('`"[]').lower()
        for c in m.group(1).split(",")
        if c.strip()
    ]


def _qualified_select_columns(sql: str) -> List[Tuple[str, str]]:
    m = re.search(
        r"\bSELECT\s+(?:DISTINCT\s+)?(.+?)\s+FROM\b",
        sql,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return []
    out: List[Tuple[str, str]] = []
    for part in m.group(1).split(","):
        part = re.sub(r"\s+AS\s+[A-Za-z_][A-Za-z0-9_]*$", "", part, flags=re.IGNORECASE)
        part = part.strip().strip('`"[]')
        qm = re.match(
            r"^([A-Za-z_][A-Za-z0-9_]*)\s*\.\s*([A-Za-z_][A-Za-z0-9_]*|\*)$",
            part,
        )
        if qm:
            col = qm.group(2)
            out.append((qm.group(1).lower(), "*" if col == "*" else col.lower()))
    return out
