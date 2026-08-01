"""JSON intent contract for LLM structured output → QueryIntent.

The LLM is instructed to emit a single JSON object matching ``INTENT_JSON_CONTRACT``.
This module deserializes that JSON into a :class:`QueryIntent` **deterministically and
fail-closed** — anything malformed, or a write/DDL query type, raises ``ValueError``.
Nothing here renders SQL: the resulting intent is handed to the deterministic,
parameterized renderer (``cognidb.intent.render_sql``), so no LLM-produced text ever
reaches the database except as a bound parameter or a validated identifier.
"""

from __future__ import annotations

import json
from typing import Any

from ..core.query_intent import (
    AggregateFunction,
    Aggregation,
    Column,
    ComparisonOperator,
    Condition,
    ConditionGroup,
    JoinCondition,
    JoinType,
    LogicalOperator,
    OrderBy,
    QueryIntent,
    QueryType,
)

# Read-only by contract: the NL path never emits writes/DDL. Write mode is a
# deliberate, separately-gated feature — an LLM must not reach it by accident.
_READ_TYPES: frozenset[str] = frozenset({"SELECT", "AGGREGATE", "COUNT", "DISTINCT"})

# Compact spec embedded in the generation prompt. Kept terse on purpose: the model
# only needs the shape and the allowed enum tokens.
INTENT_JSON_CONTRACT = """Return ONLY a single JSON object (no prose, no fences) with this shape:
{
  "query_type": "SELECT" | "AGGREGATE" | "COUNT" | "DISTINCT",   // required
  "tables": ["table_name", ...],                                 // required, >= 1
  "columns": [ "col" | {"name": "col", "table": "t"?, "alias": "a"?}, ... ],
  "distinct": false,
  "conditions": {                                                // optional WHERE, may nest
    "operator": "AND" | "OR",
    "conditions": [
      {"column": "col", "operator": <OP>, "value": <literal>},
      { ...nested group with its own operator/conditions... }
    ]
  },
  "joins": [ {"join_type": <JOIN>, "left_table": "a", "right_table": "b",
              "left_column": "x", "right_column": "y"} ],
  "aggregations": [ {"function": <AGG>, "column": "col", "alias": "a"?} ],
  "group_by": [ "col" ],
  "having": { ...same shape as conditions... },
  "order_by": [ {"column": "col", "ascending": true} ],
  "limit": <int | null>,
  "offset": <int | null>
}
<OP>   = "=" "!=" ">" ">=" "<" "<=" "IN" "NOT IN" "LIKE" "NOT LIKE"
         "IS NULL" "IS NOT NULL" "BETWEEN"   (IN -> value is a list; BETWEEN -> [lo, hi])
<JOIN> = "INNER" "LEFT" "RIGHT" "FULL"
<AGG>  = "SUM" "AVG" "COUNT" "MIN" "MAX" "GROUP_CONCAT"
Rules: only reference tables/columns that exist in the schema. Put every user-supplied
literal in a "value" field (it becomes a bound parameter) -- never build raw SQL."""


def intent_from_json(text: str) -> QueryIntent:
    """Parse an LLM response (optionally fenced) into a validated QueryIntent."""
    return intent_from_dict(_loads(text))


def intent_from_dict(data: Any) -> QueryIntent:
    """Deserialize a JSON-intent dict into a QueryIntent, fail-closed on anything off."""
    if not isinstance(data, dict):
        raise ValueError("intent must be a JSON object")

    raw_type = data.get("query_type")
    if raw_type is None:
        raise ValueError("intent missing 'query_type'")
    type_name = str(raw_type).strip().upper()
    if type_name not in _READ_TYPES:
        raise ValueError(
            f"query_type {raw_type!r} not allowed; read-only: {sorted(_READ_TYPES)}"
        )

    try:
        query_type = QueryType[type_name]
        tables = data.get("tables") or []
        if not isinstance(tables, list):
            raise ValueError("'tables' must be a list")

        columns = [_column(c) for c in data.get("columns", [])]
        conditions = _group(data["conditions"]) if data.get("conditions") else None
        having = _group(data["having"]) if data.get("having") else None
        aggregations = [_aggregation(a) for a in data.get("aggregations", [])]
        group_by = [_column(c) for c in data.get("group_by", [])]
        order_by = [_order(o) for o in data.get("order_by", [])]
        joins = [_join(j) for j in data.get("joins", [])]
        limit = _int_or_none(data.get("limit"))
        offset = _int_or_none(data.get("offset"))
        distinct = bool(data.get("distinct", False))
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"invalid intent JSON: {e}") from e

    # QueryIntent.__post_init__ enforces its own invariants (>=1 table, GROUP BY
    # rules) and raises ValueError — the fail-closed boundary we want.
    return QueryIntent(
        query_type=query_type,
        tables=list(tables),
        columns=columns,
        conditions=conditions,
        joins=joins,
        aggregations=aggregations,
        group_by=group_by,
        having=having,
        order_by=order_by,
        limit=limit,
        offset=offset,
        distinct=distinct,
    )


def _loads(text: str) -> Any:
    """json.loads, tolerating a ```json ... ``` fence around the object."""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1] if s.count("```") >= 2 else s.strip("`")
        if s.lstrip().lower().startswith("json"):
            s = s.lstrip()[4:]
        s = s.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError as e:
        raise ValueError(f"intent is not valid JSON: {e}") from e


def _column(x: Any) -> Column:
    if isinstance(x, str):
        return Column(x)
    if isinstance(x, dict):
        name = x.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("column requires a non-empty string 'name'")
        return Column(name=name, table=x.get("table"), alias=x.get("alias"))
    raise ValueError(f"column must be a string or object, got {type(x).__name__}")


def _group(d: Any) -> ConditionGroup:
    if not isinstance(d, dict):
        raise ValueError("condition group must be an object")
    items = d.get("conditions")
    if not isinstance(items, list):
        raise ValueError("condition group requires a 'conditions' list")
    op = LogicalOperator(str(d.get("operator", "AND")).upper())
    conds: list[Condition | ConditionGroup] = []
    for it in items:
        if isinstance(it, dict) and isinstance(it.get("conditions"), list):
            conds.append(_group(it))
        else:
            conds.append(_condition(it))
    return ConditionGroup(conds, op)


def _condition(d: Any) -> Condition:
    if not isinstance(d, dict):
        raise ValueError("condition must be an object")
    col = _column(d["column"])
    op = ComparisonOperator(str(d["operator"]).upper())
    return Condition(col, op, d.get("value"))


def _aggregation(d: Any) -> Aggregation:
    if not isinstance(d, dict):
        raise ValueError("aggregation must be an object")
    fn = AggregateFunction(str(d["function"]).upper())
    return Aggregation(fn, _column(d["column"]), alias=d.get("alias"))


def _join(d: Any) -> JoinCondition:
    if not isinstance(d, dict):
        raise ValueError("join must be an object")
    jt = JoinType(str(d["join_type"]).upper())
    return JoinCondition(
        join_type=jt,
        left_table=str(d["left_table"]),
        right_table=str(d["right_table"]),
        left_column=str(d["left_column"]),
        right_column=str(d["right_column"]),
    )


def _order(d: Any) -> OrderBy:
    if not isinstance(d, dict):
        raise ValueError("order_by entry must be an object")
    return OrderBy(_column(d["column"]), bool(d.get("ascending", True)))


def _int_or_none(v: Any) -> int | None:
    return None if v is None else int(v)
