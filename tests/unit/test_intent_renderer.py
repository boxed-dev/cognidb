"""Intent → SQL renderer (Epic 1.1 / 1.2) — public seam: render_sql(QueryIntent)."""

import pytest

from cognidb.core.query_intent import (
    Column,
    ComparisonOperator,
    Condition,
    ConditionGroup,
    LogicalOperator,
    QueryIntent,
    QueryType,
)


def test_renders_simple_select():
    from cognidb.intent import render_sql

    intent = QueryIntent(
        query_type=QueryType.SELECT,
        tables=["users"],
        columns=[Column("id"), Column("name")],
    )
    assert render_sql(intent) == "SELECT id, name FROM users"


@pytest.mark.parametrize(
    "intent,expected",
    [
        pytest.param(
            QueryIntent(
                query_type=QueryType.SELECT,
                tables=["users"],
                columns=[Column("id"), Column("name")],
                conditions=ConditionGroup(
                    [
                        Condition(
                            Column("id"),
                            ComparisonOperator.EQ,
                            1,
                        )
                    ]
                ),
            ),
            "SELECT id, name FROM users WHERE id = 1",
            id="where_eq",
        ),
        pytest.param(
            QueryIntent(
                query_type=QueryType.SELECT,
                tables=["users"],
                columns=[Column("id"), Column("name")],
                conditions=ConditionGroup(
                    [
                        Condition(Column("id"), ComparisonOperator.EQ, 1),
                        Condition(Column("name"), ComparisonOperator.EQ, "Ada"),
                    ],
                    operator=LogicalOperator.AND,
                ),
            ),
            "SELECT id, name FROM users WHERE id = 1 AND name = 'Ada'",
            id="where_and",
        ),
        pytest.param(
            QueryIntent(
                query_type=QueryType.SELECT,
                tables=["users"],
                columns=[Column("id"), Column("name")],
                limit=10,
            ),
            "SELECT id, name FROM users LIMIT 10",
            id="limit",
        ),
    ],
)
def test_renders_select_variants(intent, expected):
    from cognidb.intent import render_sql

    assert render_sql(intent) == expected


@pytest.mark.parametrize("forbidden_name", ["DROP", "CREATE", "ALTER", "TRUNCATE"])
def test_rejects_forbidden_ddl_shaped_intent(forbidden_name):
    """Renderer must refuse DDL-shaped intents with a clear error."""
    from cognidb.intent import render_sql
    from cognidb.intent.renderer import IntentRenderError

    intent = QueryIntent(
        query_type=QueryType.SELECT,
        tables=["users"],
        columns=[Column("id")],
    )
    # Simulate a DDL-shaped intent type (QueryType has no DDL members by design)
    intent.query_type = type("ForbiddenType", (), {"name": forbidden_name})()

    with pytest.raises(IntentRenderError, match="(?i)(ddl|forbidden|not supported|not allowed)"):
        render_sql(intent)


def test_count_intent_renders_as_select_not_ddl():
    from cognidb.intent import render_sql

    intent = QueryIntent(
        query_type=QueryType.COUNT,
        tables=["users"],
        columns=[Column("id")],
    )
    sql = render_sql(intent)
    assert "DROP" not in sql.upper()
    assert "CREATE" not in sql.upper()
    assert sql.upper().startswith("SELECT")
