"""Pipeline intent mode (Epic 1.3 / 1.4) — NL → intent → render_sql → enforce → execute."""

from __future__ import annotations

import pytest

from cognidb.ai.fake_generator import FakeIntentGenerator, FakeSQLGenerator
from cognidb.core.query_intent import Column, QueryIntent, QueryType
from cognidb.pipeline.secure_query import SecureQueryPipeline
from cognidb.security import (
    InputSanitizer,
    QuerySecurityValidator,
    StatementMode,
    StatementPolicy,
)


class _Drv:
    def __init__(self):
        self.calls = []

    def execute_native_query(self, query, params=None):
        self.calls.append(query)
        return [{"id": 1, "name": "Ada"}]


def _pipe(*, generation_mode="free_form", generator=None, policy=None, drv=None, schema=None):
    return SecureQueryPipeline(
        driver=drv or _Drv(),
        generator=generator or FakeSQLGenerator("SELECT id FROM users"),
        validator=QuerySecurityValidator(
            allowed_operations=["SELECT", "INSERT", "UPDATE", "DELETE"]
        ),
        sanitizer=InputSanitizer(),
        schema=schema or {"users": {"id": "int", "name": "text"}},
        enable_audit=False,
        policy=policy or StatementPolicy(),
        generation_mode=generation_mode,
        repair_budget=0,
    )


def test_intent_mode_renders_and_executes():
    intent = QueryIntent(
        query_type=QueryType.SELECT,
        tables=["users"],
        columns=[Column("id"), Column("name")],
    )
    gen = FakeIntentGenerator(intent)
    drv = _Drv()
    pipe = _pipe(generation_mode="intent", generator=gen, drv=drv)

    result = pipe.run("list users")

    assert result.success is True
    assert result.sql == "SELECT id, name FROM users"
    assert drv.calls == ["SELECT id, name FROM users"]
    assert gen.calls == 1


def test_free_form_remains_default():
    gen = FakeSQLGenerator("SELECT id FROM users")
    pipe = _pipe(generator=gen)
    result = pipe.run("list users")
    assert result.success is True
    assert result.sql == "SELECT id FROM users"
    assert gen.calls == 1


def test_intent_insert_blocked_in_read_mode():
    intent = QueryIntent(
        query_type=QueryType.INSERT,
        tables=["users"],
        columns=[Column("name")],
        values=["Ada"],
    )
    gen = FakeIntentGenerator(intent)
    result = _pipe(generation_mode="intent", generator=gen).run("add user Ada")
    assert result.success is False
    assert result.error
    assert "INSERT" in result.error or "not allowed" in result.error.lower()


def test_intent_insert_allowed_in_write_mode():
    intent = QueryIntent(
        query_type=QueryType.INSERT,
        tables=["users"],
        columns=[Column("name")],
        values=["Ada"],
    )
    gen = FakeIntentGenerator(intent)
    drv = _Drv()
    policy = StatementPolicy(mode=StatementMode.WRITE)
    result = _pipe(
        generation_mode="intent",
        generator=gen,
        policy=policy,
        drv=drv,
    ).run("add user Ada")

    assert result.success is True
    assert result.sql == "INSERT INTO users (name) VALUES ('Ada')"
    assert drv.calls == [result.sql]
