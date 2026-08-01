"""JSON intent contract <-> QueryIntent deserialization (LLM structured output)."""

from __future__ import annotations

import pytest

from cognidb.ai.intent_schema import intent_from_dict, intent_from_json
from cognidb.core.query_intent import (
    AggregateFunction,
    ComparisonOperator,
    JoinType,
    LogicalOperator,
    QueryType,
)


def test_minimal_select():
    intent = intent_from_dict({"query_type": "SELECT", "tables": ["users"]})
    assert intent.query_type is QueryType.SELECT
    assert intent.tables == ["users"]
    # __post_init__ defaults columns to *
    assert intent.columns[0].name == "*"


def test_columns_and_conditions():
    intent = intent_from_dict(
        {
            "query_type": "SELECT",
            "tables": ["users"],
            "columns": [{"name": "id"}, {"name": "name", "alias": "n"}],
            "conditions": {
                "operator": "AND",
                "conditions": [
                    {"column": {"name": "name"}, "operator": "=", "value": "Ada"},
                    {"column": {"name": "age"}, "operator": ">=", "value": 18},
                ],
            },
        }
    )
    assert [c.name for c in intent.columns] == ["id", "name"]
    assert intent.columns[1].alias == "n"
    assert intent.conditions.operator is LogicalOperator.AND
    c0, c1 = intent.conditions.conditions
    assert c0.operator is ComparisonOperator.EQ
    assert c0.value == "Ada"
    assert c1.operator is ComparisonOperator.GTE
    assert c1.value == 18


def test_bare_string_column_accepted():
    intent = intent_from_dict(
        {"query_type": "SELECT", "tables": ["t"], "columns": ["a", "b"]}
    )
    assert [c.name for c in intent.columns] == ["a", "b"]


def test_in_operator_list_value():
    intent = intent_from_dict(
        {
            "query_type": "SELECT",
            "tables": ["users"],
            "conditions": {
                "conditions": [
                    {"column": "status", "operator": "IN", "value": ["a", "b"]}
                ]
            },
        }
    )
    cond = intent.conditions.conditions[0]
    assert cond.operator is ComparisonOperator.IN
    assert cond.value == ["a", "b"]


def test_nested_condition_group():
    intent = intent_from_dict(
        {
            "query_type": "SELECT",
            "tables": ["users"],
            "conditions": {
                "operator": "OR",
                "conditions": [
                    {"column": "a", "operator": "=", "value": 1},
                    {
                        "operator": "AND",
                        "conditions": [
                            {"column": "b", "operator": "=", "value": 2},
                            {"column": "c", "operator": "=", "value": 3},
                        ],
                    },
                ],
            },
        }
    )
    assert intent.conditions.operator is LogicalOperator.OR
    inner = intent.conditions.conditions[1]
    assert inner.operator is LogicalOperator.AND
    assert len(inner.conditions) == 2


def test_aggregation_group_order_limit():
    intent = intent_from_dict(
        {
            "query_type": "AGGREGATE",
            "tables": ["orders"],
            "columns": [{"name": "country"}],
            "aggregations": [
                {"function": "SUM", "column": {"name": "revenue"}, "alias": "total"}
            ],
            "group_by": [{"name": "country"}],
            "order_by": [{"column": {"name": "total"}, "ascending": False}],
            "limit": 10,
            "offset": 5,
        }
    )
    assert intent.query_type is QueryType.AGGREGATE
    agg = intent.aggregations[0]
    assert agg.function is AggregateFunction.SUM
    assert agg.column.name == "revenue"
    assert agg.alias == "total"
    assert intent.group_by[0].name == "country"
    assert intent.order_by[0].ascending is False
    assert intent.limit == 10
    assert intent.offset == 5


def test_join():
    intent = intent_from_dict(
        {
            "query_type": "SELECT",
            "tables": ["a"],
            "columns": ["a.id"],
            "joins": [
                {
                    "join_type": "INNER",
                    "left_table": "a",
                    "right_table": "b",
                    "left_column": "b_id",
                    "right_column": "id",
                }
            ],
        }
    )
    join = intent.joins[0]
    assert join.join_type is JoinType.INNER
    assert join.right_table == "b"


def test_distinct_flag():
    intent = intent_from_dict(
        {"query_type": "DISTINCT", "tables": ["t"], "columns": ["x"], "distinct": True}
    )
    assert intent.distinct is True


def test_from_json_strips_code_fence():
    intent = intent_from_json(
        '```json\n{"query_type": "SELECT", "tables": ["t"]}\n```'
    )
    assert intent.tables == ["t"]


@pytest.mark.parametrize(
    "bad",
    [
        {"tables": ["t"]},  # missing query_type
        {"query_type": "SELECT"},  # missing tables (QueryIntent rejects empty)
        {"query_type": "DELETE", "tables": ["t"]},  # unknown/forbidden type
        {"query_type": "SELECT", "tables": ["t"], "conditions": {
            "conditions": [{"column": "a", "operator": "NOPE", "value": 1}]
        }},  # bad operator
        {"query_type": "SELECT", "tables": ["t"], "aggregations": [
            {"function": "HACK", "column": "x"}
        ]},  # bad aggregate function
    ],
)
def test_fail_closed_on_bad_input(bad):
    with pytest.raises(ValueError):
        intent_from_dict(bad)


def test_from_json_invalid_json_raises():
    with pytest.raises(ValueError):
        intent_from_json("not json at all")
