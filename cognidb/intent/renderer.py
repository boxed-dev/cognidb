"""Deterministic QueryIntent → SQL renderer (ADR 0006).

Deep module: small public surface (`render_sql`), large internal formatting logic.
"""

from __future__ import annotations

from typing import Any, FrozenSet, Union

from ..core.query_intent import (
    Column,
    ComparisonOperator,
    Condition,
    ConditionGroup,
    LogicalOperator,
    QueryIntent,
    QueryType,
)

# Read-oriented types + INSERT for write-mode intent path (ADR 0003/0006)
_ALLOWED_QUERY_TYPES: FrozenSet[str] = frozenset({
    "SELECT",
    "AGGREGATE",
    "COUNT",
    "DISTINCT",
    "INSERT",
})

_DDL_FORBIDDEN: FrozenSet[str] = frozenset({
    "DROP",
    "CREATE",
    "ALTER",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "RENAME",
    "REPLACE",
    "MERGE",
})


class IntentRenderError(ValueError):
    """Raised when a QueryIntent cannot be safely rendered to SQL."""


def render_sql(intent: QueryIntent) -> str:
    """
    Render a QueryIntent to a single SQL statement string.

    Only SELECT-family and INSERT intents are supported. DDL-shaped types are
    rejected fail-closed with IntentRenderError.
    """
    type_name = _type_name(intent.query_type)

    if type_name in _DDL_FORBIDDEN:
        raise IntentRenderError(
            f"DDL/forbidden query type not allowed: {type_name}"
        )
    if type_name not in _ALLOWED_QUERY_TYPES:
        raise IntentRenderError(
            f"Query type not supported by intent renderer: {type_name}"
        )

    if type_name == "INSERT":
        return _render_insert(intent)

    return _render_select(intent, type_name)


def _type_name(query_type: Any) -> str:
    if hasattr(query_type, "name"):
        return str(query_type.name).upper()
    return str(query_type).upper()


def _render_select(intent: QueryIntent, type_name: str) -> str:
    columns = _format_columns(intent, type_name)
    tables = ", ".join(intent.tables)
    distinct = "DISTINCT " if intent.distinct or type_name == "DISTINCT" else ""

    parts = [f"SELECT {distinct}{columns} FROM {tables}"]

    if intent.joins:
        for join in intent.joins:
            parts.append(
                f"{join.join_type.value} JOIN {join.right_table} "
                f"ON {join.left_table}.{join.left_column} = "
                f"{join.right_table}.{join.right_column}"
            )

    if intent.conditions and intent.conditions.conditions:
        parts.append(f"WHERE {_format_condition_group(intent.conditions)}")

    if intent.group_by:
        parts.append("GROUP BY " + ", ".join(str(c) for c in intent.group_by))

    if intent.having and intent.having.conditions:
        parts.append(f"HAVING {_format_condition_group(intent.having)}")

    if intent.order_by:
        order_bits = []
        for ob in intent.order_by:
            direction = "ASC" if ob.ascending else "DESC"
            order_bits.append(f"{ob.column} {direction}")
        parts.append("ORDER BY " + ", ".join(order_bits))

    if intent.limit is not None:
        parts.append(f"LIMIT {int(intent.limit)}")
        if intent.offset:
            parts.append(f"OFFSET {int(intent.offset)}")

    return " ".join(parts)


def _format_columns(intent: QueryIntent, type_name: str) -> str:
    if type_name == "COUNT" and not intent.aggregations:
        # COUNT intent without explicit aggregation: COUNT(*)
        if len(intent.columns) == 1 and intent.columns[0].name == "*":
            return "COUNT(*)"
        if intent.columns:
            return f"COUNT({intent.columns[0]})"
        return "COUNT(*)"

    if intent.aggregations:
        agg_parts = []
        for agg in intent.aggregations:
            expr = f"{agg.function.value}({agg.column})"
            if agg.alias:
                expr = f"{expr} AS {agg.alias}"
            agg_parts.append(expr)
        # Include non-aggregated columns (expected in GROUP BY)
        col_parts = [str(c) for c in intent.columns]
        return ", ".join(col_parts + agg_parts) if col_parts else ", ".join(agg_parts)

    if not intent.columns:
        return "*"
    return ", ".join(str(c) for c in intent.columns)


def _render_insert(intent: QueryIntent) -> str:
    if len(intent.tables) != 1:
        raise IntentRenderError("INSERT intent requires exactly one table")
    table = intent.tables[0]
    cols = [c.name for c in intent.columns if c.name != "*"]
    if not cols:
        raise IntentRenderError("INSERT intent requires explicit columns")

    values = getattr(intent, "values", None)
    if values is None:
        raise IntentRenderError("INSERT intent requires values")

    if isinstance(values, dict):
        ordered = [_sql_literal(values[c]) for c in cols]
    elif isinstance(values, (list, tuple)):
        if len(values) != len(cols):
            raise IntentRenderError("INSERT values length must match columns")
        ordered = [_sql_literal(v) for v in values]
    else:
        raise IntentRenderError("INSERT values must be a dict or sequence")

    col_list = ", ".join(cols)
    val_list = ", ".join(ordered)
    return f"INSERT INTO {table} ({col_list}) VALUES ({val_list})"


def _format_condition_group(group: ConditionGroup) -> str:
    parts = []
    for item in group.conditions:
        if isinstance(item, ConditionGroup):
            parts.append(f"({_format_condition_group(item)})")
        else:
            parts.append(_format_condition(item))
    joiner = f" {group.operator.value} "
    return joiner.join(parts)


def _format_condition(cond: Condition) -> str:
    col = str(cond.column)
    op = cond.operator

    if op == ComparisonOperator.IS_NULL:
        return f"{col} IS NULL"
    if op == ComparisonOperator.IS_NOT_NULL:
        return f"{col} IS NOT NULL"
    if op == ComparisonOperator.IN:
        vals = ", ".join(_sql_literal(v) for v in cond.value)
        return f"{col} IN ({vals})"
    if op == ComparisonOperator.NOT_IN:
        vals = ", ".join(_sql_literal(v) for v in cond.value)
        return f"{col} NOT IN ({vals})"
    if op == ComparisonOperator.BETWEEN:
        lo, hi = cond.value
        return f"{col} BETWEEN {_sql_literal(lo)} AND {_sql_literal(hi)}"

    return f"{col} {op.value} {_sql_literal(cond.value)}"


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    # Escape single quotes for string literals
    text = str(value).replace("'", "''")
    return f"'{text}'"
