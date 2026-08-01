"""Deterministic QueryIntent -> parameterized SQL renderer (ADR 0006, Contract 2).

Deep module: small public surface (`render_sql`), large internal formatting logic.

Security invariant: **no value is ever interpolated into the SQL string.** Every
value becomes a bound parameter using the dialect placeholder; only structural
integers (LIMIT/OFFSET) are inlined. Identifiers cannot be bound, so each is
validated against a strict pattern and rejected fail-closed if malformed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..core.query_intent import (
    ComparisonOperator,
    Condition,
    ConditionGroup,
    QueryIntent,
)

_ALLOWED_QUERY_TYPES: frozenset[str] = frozenset({
    "SELECT", "AGGREGATE", "COUNT", "DISTINCT", "INSERT",
})

_DDL_FORBIDDEN: frozenset[str] = frozenset({
    "DROP", "CREATE", "ALTER", "TRUNCATE", "GRANT", "REVOKE",
    "RENAME", "REPLACE", "MERGE",
})

_PLACEHOLDER = {"sqlite": "?", "postgres": "%s", "mysql": "%s"}

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class IntentRenderError(ValueError):
    """Raised when a QueryIntent cannot be safely rendered to SQL."""


@dataclass(frozen=True)
class RenderedSQL:
    """A parameterized statement: SQL text with placeholders + ordered params."""

    sql: str
    params: tuple[Any, ...] = ()


def render_sql(intent: QueryIntent, *, dialect: str) -> RenderedSQL:
    """Render a QueryIntent to a single parameterized SQL statement.

    Args:
        intent: the query intent to render.
        dialect: target engine — ``sqlite`` (``?``) or ``postgres``/``mysql`` (``%s``).
    """
    placeholder = _PLACEHOLDER.get(dialect)
    if placeholder is None:
        raise IntentRenderError(f"Unsupported dialect: {dialect!r}")

    type_name = _type_name(intent.query_type)
    if type_name in _DDL_FORBIDDEN:
        raise IntentRenderError(f"DDL/forbidden query type not allowed: {type_name}")
    if type_name not in _ALLOWED_QUERY_TYPES:
        raise IntentRenderError(f"Query type not supported by intent renderer: {type_name}")

    params: list[Any] = []
    if type_name == "INSERT":
        sql = _render_insert(intent, placeholder, params)
    else:
        sql = _render_select(intent, type_name, placeholder, params)
    return RenderedSQL(sql=sql, params=tuple(params))


def _type_name(query_type: Any) -> str:
    if hasattr(query_type, "name"):
        return str(query_type.name).upper()
    return str(query_type).upper()


def _ident(raw: Any) -> str:
    """Validate an identifier (optionally dotted, ``*`` allowed) or fail closed."""
    s = str(raw).strip()
    if s == "*":
        return "*"
    if not s:
        raise IntentRenderError("Empty identifier")
    for part in s.split("."):
        if part == "*":
            continue
        if not _IDENT_RE.match(part):
            raise IntentRenderError(f"Invalid identifier: {raw!r}")
    return s


def _func(raw: Any) -> str:
    s = str(raw).strip().upper()
    if not re.match(r"^[A-Z_]+$", s):
        raise IntentRenderError(f"Invalid function name: {raw!r}")
    return s


def _render_select(intent: QueryIntent, type_name: str, ph: str, params: list[Any]) -> str:
    columns = _format_columns(intent, type_name)
    tables = ", ".join(_ident(t) for t in intent.tables)
    distinct = "DISTINCT " if intent.distinct or type_name == "DISTINCT" else ""

    # Identifiers are pre-validated by _ident(); every value is a bound parameter,
    # so this f-string interpolates only trusted structural tokens.
    parts = [f"SELECT {distinct}{columns} FROM {tables}"]  # noqa: S608  # nosec B608

    for join in intent.joins:
        parts.append(
            f"{join.join_type.value} JOIN {_ident(join.right_table)} "
            f"ON {_ident(join.left_table)}.{_ident(join.left_column)} = "
            f"{_ident(join.right_table)}.{_ident(join.right_column)}"
        )

    if intent.conditions and intent.conditions.conditions:
        parts.append(f"WHERE {_format_condition_group(intent.conditions, ph, params)}")

    if intent.group_by:
        parts.append("GROUP BY " + ", ".join(_ident(c) for c in intent.group_by))

    if intent.having and intent.having.conditions:
        parts.append(f"HAVING {_format_condition_group(intent.having, ph, params)}")

    if intent.order_by:
        order_bits = []
        for ob in intent.order_by:
            direction = "ASC" if ob.ascending else "DESC"
            order_bits.append(f"{_ident(ob.column)} {direction}")
        parts.append("ORDER BY " + ", ".join(order_bits))

    if intent.limit is not None:
        parts.append(f"LIMIT {int(intent.limit)}")
        if intent.offset:
            parts.append(f"OFFSET {int(intent.offset)}")

    return " ".join(parts)


def _format_columns(intent: QueryIntent, type_name: str) -> str:
    if type_name == "COUNT" and not intent.aggregations:
        if len(intent.columns) == 1 and intent.columns[0].name == "*":
            return "COUNT(*)"
        if intent.columns:
            return f"COUNT({_ident(intent.columns[0])})"
        return "COUNT(*)"

    if intent.aggregations:
        agg_parts = []
        for agg in intent.aggregations:
            expr = f"{_func(agg.function.value)}({_ident(agg.column)})"
            if agg.alias:
                expr = f"{expr} AS {_ident(agg.alias)}"
            agg_parts.append(expr)
        col_parts = [_ident(c) for c in intent.columns]
        return ", ".join(col_parts + agg_parts) if col_parts else ", ".join(agg_parts)

    if not intent.columns:
        return "*"
    return ", ".join(_ident(c) for c in intent.columns)


def _render_insert(intent: QueryIntent, ph: str, params: list[Any]) -> str:
    if len(intent.tables) != 1:
        raise IntentRenderError("INSERT intent requires exactly one table")
    table = _ident(intent.tables[0])
    cols = [_ident(c.name) for c in intent.columns if c.name != "*"]
    if not cols:
        raise IntentRenderError("INSERT intent requires explicit columns")

    raw_cols = [c.name for c in intent.columns if c.name != "*"]
    values = getattr(intent, "values", None)
    if values is None:
        raise IntentRenderError("INSERT intent requires values")

    if isinstance(values, dict):
        ordered = [values[c] for c in raw_cols]
    elif isinstance(values, (list, tuple)):
        if len(values) != len(cols):
            raise IntentRenderError("INSERT values length must match columns")
        ordered = list(values)
    else:
        raise IntentRenderError("INSERT values must be a dict or sequence")

    params.extend(ordered)
    placeholders = ", ".join([ph] * len(ordered))
    # table/cols are pre-validated by _ident(); placeholders are bind markers and
    # every value is bound, so no value is interpolated into this SQL string.
    return f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"  # noqa: S608  # nosec B608


def _format_condition_group(group: ConditionGroup, ph: str, params: list[Any]) -> str:
    parts = []
    for item in group.conditions:
        if isinstance(item, ConditionGroup):
            parts.append(f"({_format_condition_group(item, ph, params)})")
        else:
            parts.append(_format_condition(item, ph, params))
    joiner = f" {group.operator.value} "
    return joiner.join(parts)


def _format_condition(cond: Condition, ph: str, params: list[Any]) -> str:
    col = _ident(cond.column)
    op = cond.operator

    if op == ComparisonOperator.IS_NULL:
        return f"{col} IS NULL"
    if op == ComparisonOperator.IS_NOT_NULL:
        return f"{col} IS NOT NULL"
    if op in (ComparisonOperator.IN, ComparisonOperator.NOT_IN):
        vals = list(cond.value)
        params.extend(vals)
        placeholders = ", ".join([ph] * len(vals))
        keyword = "IN" if op == ComparisonOperator.IN else "NOT IN"
        return f"{col} {keyword} ({placeholders})"
    if op == ComparisonOperator.BETWEEN:
        lo, hi = cond.value
        params.extend([lo, hi])
        return f"{col} BETWEEN {ph} AND {ph}"

    params.append(cond.value)
    return f"{col} {op.value} {ph}"
