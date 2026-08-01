"""SQL and result comparison helpers for the benchmark harness."""

from __future__ import annotations

import re
import statistics
from collections.abc import Iterable, Sequence
from typing import Any

import sqlparse
from sqlparse.sql import Identifier, IdentifierList, Token
from sqlparse.tokens import Keyword, Name, Whitespace

_WS_RE = re.compile(r"\s+")
_KEYWORD_RE = re.compile(
    r"\b(select|from|where|and|or|not|in|is|null|as|on|join|inner|left|right|"
    r"full|outer|group|by|order|having|limit|offset|distinct|union|all|between|"
    r"like|asc|desc|count|sum|avg|min|max|case|when|then|else|end|insert|into|"
    r"values|update|set|delete|with|exists|true|false)\b",
    re.IGNORECASE,
)


def normalize_sql(sql: str) -> str:
    """Collapse insignificant whitespace and normalize keyword case."""
    if not sql:
        return ""
    formatted = sqlparse.format(
        sql.strip().rstrip(";"),
        keyword_case="upper",
        identifier_case=None,
        strip_comments=True,
        reindent=False,
    )
    return _WS_RE.sub(" ", formatted).strip()


def exact_sql_match(expected: str, actual: str) -> bool:
    return normalize_sql(expected) == normalize_sql(actual)


def _cell(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 6)
    return value


def normalize_rows(
    rows: Sequence[dict[str, Any]],
    *,
    sort_rows: bool = True,
) -> list[dict[str, Any]]:
    """Normalize result rows for order-tolerant comparison when safe."""
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            out.append({"_value": _cell(row)})
            continue
        cleaned = {str(k): _cell(v) for k, v in row.items()}
        out.append(cleaned)
    if sort_rows and out:
        def sort_key(r: dict[str, Any]) -> tuple:
            keys = sorted(r.keys())
            return tuple((k, repr(r.get(k))) for k in keys)

        out = sorted(out, key=sort_key)
    return out


def result_match(
    expected: Sequence[dict[str, Any]],
    actual: Sequence[dict[str, Any]],
    *,
    ordered: bool = False,
) -> bool:
    exp = normalize_rows(expected, sort_rows=not ordered)
    act = normalize_rows(actual, sort_rows=not ordered)
    return exp == act


def _collect_identifiers(token: Token, names: set[str]) -> None:
    if isinstance(token, IdentifierList):
        for child in token.get_identifiers():
            _collect_identifiers(child, names)
        return
    if isinstance(token, Identifier):
        real = token.get_real_name()
        if real:
            names.add(real.lower())
        return
    if token.ttype in (Name, Name.Placeholder) and token.value:
        names.add(str(token.value).lower())


def extract_table_column_hints(sql: str) -> tuple[set[str], set[str]]:
    """Best-effort table/column name sets for soft match (not a full parser)."""
    tables: set[str] = set()
    columns: set[str] = set()
    parsed = sqlparse.parse(sql)
    if not parsed:
        return tables, columns
    tokens = list(parsed[0].flatten())
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.ttype is Keyword and tok.normalized in {
            "FROM",
            "JOIN",
            "INTO",
            "UPDATE",
            "TABLE",
        }:
            j = i + 1
            while j < len(tokens) and tokens[j].ttype in (Whitespace, None):
                if str(tokens[j]).strip() == "":
                    j += 1
                    continue
                break
            if j < len(tokens):
                name = tokens[j].value.strip('"`[]')
                if name and tokens[j].ttype not in (Keyword,):
                    tables.add(name.lower())
        i += 1
    # Columns: crude split of SELECT list before FROM
    m = re.search(
        r"\bSELECT\b\s+(DISTINCT\s+)?(.+?)\s+\bFROM\b",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m:
        select_list = m.group(2)
        for part in select_list.split(","):
            part = part.strip()
            if not part or part == "*":
                if part == "*":
                    columns.add("*")
                continue
            part = re.sub(r"\s+AS\s+\w+$", "", part, flags=re.IGNORECASE).strip()
            # drop aggregates wrapper for soft match of inner col when simple
            inner = re.sub(
                r"^(COUNT|SUM|AVG|MIN|MAX)\s*\(\s*(?:DISTINCT\s+)?(.+?)\s*\)$",
                r"\2",
                part,
                flags=re.IGNORECASE,
            )
            col = inner.split(".")[-1].strip('"`[] ')
            if col and not re.match(r"^\d+$", col):
                columns.add(col.lower())
    return tables, columns


def soft_match(expected_sql: str, actual_sql: str) -> bool:
    et, ec = extract_table_column_hints(expected_sql)
    at, ac = extract_table_column_hints(actual_sql)
    if not et or not at:
        return False
    return et.issubset(at) or at.issubset(et)


def percentile(values: Sequence[float], p: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return float(values[0])
    ordered = sorted(float(v) for v in values)
    if p <= 0:
        return ordered[0]
    if p >= 100:
        return ordered[-1]
    k = (len(ordered) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def latency_stats(ms: Iterable[float]) -> dict[str, float | None]:
    data = list(ms)
    if not data:
        return {"count": 0, "p50_ms": None, "p95_ms": None, "mean_ms": None}
    return {
        "count": len(data),
        "p50_ms": round(percentile(data, 50) or 0.0, 3),
        "p95_ms": round(percentile(data, 95) or 0.0, 3),
        "mean_ms": round(float(statistics.mean(data)), 3),
    }
