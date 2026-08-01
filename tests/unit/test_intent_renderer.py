"""Intent -> SQL renderer — public seam: render_sql(QueryIntent, dialect=...).

Contract 2: the renderer NEVER interpolates a value into SQL. It returns a
RenderedSQL(sql, params); every value is a bound parameter using the dialect
placeholder (``?`` for sqlite, ``%s`` for postgres/mysql). Only structural
integers (LIMIT/OFFSET) are inlined. Identifiers are validated, never bound.
"""

import pytest

from cognidb.core.query_intent import (
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
from cognidb.intent import render_sql
from cognidb.intent.renderer import RenderedSQL, IntentRenderError


def test_simple_select_has_no_params():
    intent = QueryIntent(query_type=QueryType.SELECT, tables=["users"],
                         columns=[Column("id"), Column("name")])
    r = render_sql(intent, dialect="sqlite")
    assert isinstance(r, RenderedSQL)
    assert r.sql == "SELECT id, name FROM users"
    assert r.params == ()


def test_where_int_value_is_parameterized_not_inlined():
    intent = QueryIntent(query_type=QueryType.SELECT, tables=["users"],
                         columns=[Column("id")],
                         conditions=ConditionGroup([Condition(Column("id"), ComparisonOperator.EQ, 1)]))
    r = render_sql(intent, dialect="sqlite")
    assert r.sql == "SELECT id FROM users WHERE id = ?"
    assert r.params == (1,)


def test_string_value_never_appears_in_sql_text():
    intent = QueryIntent(query_type=QueryType.SELECT, tables=["users"],
                         columns=[Column("name")],
                         conditions=ConditionGroup([Condition(Column("name"), ComparisonOperator.EQ, "Ada")]))
    r = render_sql(intent, dialect="postgres")
    assert r.sql == "SELECT name FROM users WHERE name = %s"
    assert r.params == ("Ada",)
    assert "Ada" not in r.sql


def test_injection_payload_is_bound_not_interpreted():
    # The audit's MySQL backslash breakout / classic tautology are impossible now:
    # the value is data, never SQL text.
    payload = "x' OR 1=1 --"
    intent = QueryIntent(query_type=QueryType.SELECT, tables=["users"],
                         columns=[Column("id")],
                         conditions=ConditionGroup([Condition(Column("name"), ComparisonOperator.EQ, payload)]))
    r = render_sql(intent, dialect="mysql")
    assert r.sql == "SELECT id FROM users WHERE name = %s"
    assert r.params == (payload,)
    assert "OR 1=1" not in r.sql


def test_backslash_value_is_bound():
    intent = QueryIntent(query_type=QueryType.SELECT, tables=["t"],
                         columns=[Column("id")],
                         conditions=ConditionGroup([Condition(Column("name"), ComparisonOperator.EQ, "\\")]))
    r = render_sql(intent, dialect="mysql")
    assert r.params == ("\\",)
    assert "\\" not in r.sql


def test_and_conditions_bind_in_order():
    intent = QueryIntent(query_type=QueryType.SELECT, tables=["users"],
                         columns=[Column("id")],
                         conditions=ConditionGroup(
                             [Condition(Column("id"), ComparisonOperator.EQ, 1),
                              Condition(Column("name"), ComparisonOperator.EQ, "Ada")],
                             operator=LogicalOperator.AND))
    r = render_sql(intent, dialect="sqlite")
    assert r.sql == "SELECT id FROM users WHERE id = ? AND name = ?"
    assert r.params == (1, "Ada")


def test_in_list_is_parameterized_per_element():
    intent = QueryIntent(query_type=QueryType.SELECT, tables=["t"], columns=[Column("id")],
                         conditions=ConditionGroup([Condition(Column("id"), ComparisonOperator.IN, [1, 2, 3])]))
    r = render_sql(intent, dialect="sqlite")
    assert r.sql == "SELECT id FROM t WHERE id IN (?, ?, ?)"
    assert r.params == (1, 2, 3)


def test_between_is_parameterized():
    intent = QueryIntent(query_type=QueryType.SELECT, tables=["t"], columns=[Column("id")],
                         conditions=ConditionGroup([Condition(Column("age"), ComparisonOperator.BETWEEN, (18, 65))]))
    r = render_sql(intent, dialect="postgres")
    assert r.sql == "SELECT id FROM t WHERE age BETWEEN %s AND %s"
    assert r.params == (18, 65)


def test_is_null_has_no_param():
    intent = QueryIntent(query_type=QueryType.SELECT, tables=["t"], columns=[Column("id")],
                         conditions=ConditionGroup([Condition(Column("deleted_at"), ComparisonOperator.IS_NULL, None)]))
    r = render_sql(intent, dialect="sqlite")
    assert r.sql == "SELECT id FROM t WHERE deleted_at IS NULL"
    assert r.params == ()


def test_limit_is_inlined_integer_not_a_param():
    intent = QueryIntent(query_type=QueryType.SELECT, tables=["users"], columns=[Column("id")], limit=10)
    r = render_sql(intent, dialect="sqlite")
    assert r.sql == "SELECT id FROM users LIMIT 10"
    assert r.params == ()


def test_insert_values_are_parameterized():
    intent = QueryIntent(query_type=QueryType.INSERT, tables=["users"],
                         columns=[Column("id"), Column("name")],
                         values={"id": 7, "name": "Ada"})
    r = render_sql(intent, dialect="postgres")
    assert r.sql == "INSERT INTO users (id, name) VALUES (%s, %s)"
    assert r.params == (7, "Ada")
    assert "Ada" not in r.sql


def test_invalid_identifier_is_rejected():
    intent = QueryIntent(query_type=QueryType.SELECT, tables=["users"],
                         columns=[Column("id; DROP TABLE users --")])
    with pytest.raises(IntentRenderError):
        render_sql(intent, dialect="sqlite")


def test_invalid_table_identifier_is_rejected():
    intent = QueryIntent(query_type=QueryType.SELECT, tables=["users; DROP TABLE x"],
                         columns=[Column("id")])
    with pytest.raises(IntentRenderError):
        render_sql(intent, dialect="sqlite")


@pytest.mark.parametrize("forbidden_name", ["DROP", "CREATE", "ALTER", "TRUNCATE"])
def test_rejects_forbidden_ddl_shaped_intent(forbidden_name):
    intent = QueryIntent(query_type=QueryType.SELECT, tables=["users"], columns=[Column("id")])
    intent.query_type = type("ForbiddenType", (), {"name": forbidden_name})()
    with pytest.raises(IntentRenderError, match="(?i)(ddl|forbidden|not supported|not allowed)"):
        render_sql(intent, dialect="sqlite")


def test_count_intent_renders_as_select():
    intent = QueryIntent(query_type=QueryType.COUNT, tables=["users"], columns=[Column("id")])
    r = render_sql(intent, dialect="sqlite")
    assert r.sql.upper().startswith("SELECT")
    assert "DROP" not in r.sql.upper()


def test_join_renders_validated_identifiers():
    intent = QueryIntent(
        query_type=QueryType.SELECT, tables=["orders"], columns=[Column("id")],
        joins=[JoinCondition(JoinType.INNER, "orders", "users", "user_id", "id")])
    r = render_sql(intent, dialect="sqlite")
    assert r.sql == "SELECT id FROM orders INNER JOIN users ON orders.user_id = users.id"
    assert r.params == ()


def test_aggregation_with_alias_renders():
    intent = QueryIntent(
        query_type=QueryType.AGGREGATE, tables=["orders"], columns=[],
        aggregations=[Aggregation(AggregateFunction.SUM, Column("amount"), alias="total")])
    r = render_sql(intent, dialect="postgres")
    assert r.sql == "SELECT SUM(amount) AS total FROM orders"


def test_group_by_and_having_are_parameterized():
    intent = QueryIntent(
        query_type=QueryType.AGGREGATE, tables=["orders"], columns=[Column("user_id")],
        aggregations=[Aggregation(AggregateFunction.COUNT, Column("id"), alias="cnt")],
        group_by=[Column("user_id")],
        having=ConditionGroup([Condition(Column("total"), ComparisonOperator.EQ, 5)]))
    r = render_sql(intent, dialect="sqlite")
    assert "GROUP BY user_id" in r.sql
    assert "HAVING total = ?" in r.sql
    assert r.params == (5,)


def test_order_by_direction_renders():
    intent = QueryIntent(
        query_type=QueryType.SELECT, tables=["t"], columns=[Column("id")],
        order_by=[OrderBy(Column("name"), ascending=False)])
    r = render_sql(intent, dialect="sqlite")
    assert r.sql == "SELECT id FROM t ORDER BY name DESC"


def test_distinct_select_renders():
    intent = QueryIntent(query_type=QueryType.SELECT, tables=["t"], columns=[Column("city")],
                         distinct=True)
    r = render_sql(intent, dialect="sqlite")
    assert r.sql == "SELECT DISTINCT city FROM t"


def test_limit_and_offset_are_inlined_integers():
    intent = QueryIntent(query_type=QueryType.SELECT, tables=["t"], columns=[Column("id")],
                         limit=10, offset=20)
    r = render_sql(intent, dialect="sqlite")
    assert r.sql == "SELECT id FROM t LIMIT 10 OFFSET 20"
    assert r.params == ()


def test_not_in_list_is_parameterized():
    intent = QueryIntent(query_type=QueryType.SELECT, tables=["t"], columns=[Column("id")],
                         conditions=ConditionGroup(
                             [Condition(Column("id"), ComparisonOperator.NOT_IN, [1, 2])]))
    r = render_sql(intent, dialect="postgres")
    assert r.sql == "SELECT id FROM t WHERE id NOT IN (%s, %s)"
    assert r.params == (1, 2)


def test_nested_condition_group_renders_with_parens():
    inner = ConditionGroup(
        [Condition(Column("a"), ComparisonOperator.EQ, 1),
         Condition(Column("b"), ComparisonOperator.EQ, 2)],
        operator=LogicalOperator.OR)
    outer = ConditionGroup([Condition(Column("c"), ComparisonOperator.EQ, 3), inner],
                           operator=LogicalOperator.AND)
    intent = QueryIntent(query_type=QueryType.SELECT, tables=["t"], columns=[Column("id")],
                         conditions=outer)
    r = render_sql(intent, dialect="sqlite")
    assert r.sql == "SELECT id FROM t WHERE c = ? AND (a = ? OR b = ?)"
    assert r.params == (3, 1, 2)


def test_unsupported_dialect_rejected():
    intent = QueryIntent(query_type=QueryType.SELECT, tables=["t"], columns=[Column("id")])
    with pytest.raises(IntentRenderError):
        render_sql(intent, dialect="oracle")
