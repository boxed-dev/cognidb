"""Pipeline hardening invariants (Contracts 2, 3, 6).

- intent mode is the DEFAULT and passes BOUND PARAMETERS to the driver
- free-form (raw LLM SQL) requires an explicit allow_dangerous_sql opt-in
- access control fails CLOSED (enabled but no identity -> deny)
- the AST guard rejects a data-modifying CTE supplied as raw SQL
"""

import pytest

from cognidb.core.query_intent import Column, ComparisonOperator, Condition, ConditionGroup, QueryIntent, QueryType
from cognidb.ai.fake_generator import FakeIntentGenerator, FakeSQLGenerator
from cognidb.pipeline.secure_query import SecureQueryPipeline
from cognidb.security import QuerySecurityValidator, InputSanitizer, AccessController
from cognidb.security.statement_policy import StatementPolicy, StatementMode


class SpyDriver:
    def __init__(self):
        self.executed = []  # list of (sql, params)

    def execute_native_query(self, query, params=None):
        self.executed.append((query, params))
        return [{"id": 1}]

    def explain_query(self, sql, schema):
        return "ok"


SCHEMA = {"users": {"columns": {"id": {"type": "int"}, "name": {"type": "text"}}}}


def _intent_where_name_eq(value):
    return QueryIntent(
        query_type=QueryType.SELECT, tables=["users"], columns=[Column("id")],
        conditions=ConditionGroup([Condition(Column("name"), ComparisonOperator.EQ, value)]),
    )


def _pipe(generator, **kw):
    return SecureQueryPipeline(
        driver=SpyDriver(), generator=generator,
        validator=QuerySecurityValidator(), sanitizer=InputSanitizer(),
        schema=SCHEMA, dialect="sqlite", enable_audit=False, **kw,
    )


def test_default_mode_is_intent_and_binds_parameters():
    payload = "x' OR 1=1 --"
    pipe = _pipe(FakeIntentGenerator(_intent_where_name_eq(payload)))  # no generation_mode -> default
    r = pipe.run("find user")
    assert r.success is True, r.error
    sql, params = pipe.driver.executed[-1]
    assert sql == "SELECT id FROM users WHERE name = ?"
    assert params == (payload,)          # value is DATA, bound
    assert "OR 1=1" not in sql           # never in SQL text


def test_free_form_requires_explicit_opt_in():
    with pytest.raises(ValueError):
        _pipe(FakeSQLGenerator("SELECT id FROM users"), generation_mode="free_form")


def test_free_form_allowed_with_opt_in():
    pipe = _pipe(FakeSQLGenerator("SELECT id FROM users"),
                 generation_mode="free_form", allow_dangerous_sql=True)
    r = pipe.run("list")
    assert r.success is True
    assert pipe.driver.executed[-1][0] == "SELECT id FROM users"


def test_access_control_fails_closed_without_identity():
    pipe = _pipe(FakeIntentGenerator(_intent_where_name_eq("a")),
                 access_controller=AccessController(), enable_access_control=True)
    r = pipe.run("find user")  # no user_id
    assert r.success is False
    assert "access control" in (r.error or "").lower()
    assert pipe.driver.executed == []    # never executed


def test_data_modifying_cte_via_override_is_rejected():
    pipe = _pipe(FakeSQLGenerator("SELECT 1"), generation_mode="free_form", allow_dangerous_sql=True)
    r = pipe.run("x", sql_override="WITH t AS (DELETE FROM users RETURNING *) SELECT * FROM t")
    assert r.success is False
    assert pipe.driver.executed == []


# --- red-team regressions -----------------------------------------------------

def test_sql_override_requires_allow_dangerous_sql():
    # F6: sql_override is raw SQL; it must be gated like free-form.
    pipe = _pipe(FakeIntentGenerator(_intent_where_name_eq("a")))  # intent default, no opt-in
    r = pipe.run("x", sql_override="SELECT id FROM users")
    assert r.success is False
    assert pipe.driver.executed == []


def _acl_pipe(user_tables):
    ac = AccessController()
    ac.create_read_only_user("analyst", user_tables)
    return _pipe(FakeSQLGenerator("SELECT 1"), generation_mode="free_form", allow_dangerous_sql=True,
                 access_controller=ac, enable_access_control=True)


def test_acl_not_bypassed_by_cte_self_collision():
    # F2: `WITH secret AS (SELECT * FROM secret) SELECT * FROM secret` must not skip ACL.
    pipe = _acl_pipe(["orders"])
    r = pipe.run("x", user_id="analyst",
                 sql_override="WITH secret AS (SELECT * FROM secret) SELECT * FROM secret")
    assert r.success is False
    assert pipe.driver.executed == []


def test_acl_denies_schema_qualified_smuggle():
    # F5: a table in a different schema must not be authorized as the bare name.
    pipe = _acl_pipe(["users"])
    r = pipe.run("x", user_id="analyst", sql_override="SELECT * FROM secret_schema.users")
    assert r.success is False
    assert pipe.driver.executed == []
