"""Offline E2E of the DEFAULT (intent) path — the real go-live path.

NL string → real QueryGenerator.generate_intent (LLM stubbed to a JSON intent) →
deterministic parameterized render → sqlglot AST guard → real SQLite execute.
Proves values are BOUND (never interpolated) and rows come back. No network.

Wired the same way cognidb/client.py wires SecureQueryPipeline, so this is the
end-to-end contract behind `CogniDB.query()`.
"""

from __future__ import annotations

import json

import pytest

from cognidb.ai.query_generator import QueryGenerator
from cognidb.drivers import SQLiteDriver
from cognidb.pipeline import SecureQueryPipeline
from cognidb.security import InputSanitizer, QuerySecurityValidator


class _StubLLM:
    """Returns a canned JSON intent as `.content` — stands in for LLMManager."""

    def __init__(self, intent_dict: dict):
        self._content = json.dumps(intent_dict)

    def generate(self, prompt: str, **kwargs):
        class _R:
            content = self._content

        return _R()


@pytest.fixture
def driver():
    drv = SQLiteDriver({"database": ":memory:", "max_result_size": 100})
    drv.connect()
    drv.execute_native_query(
        "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
    )
    drv.execute_native_query("INSERT INTO customers (id, name) VALUES (1, 'Ada')")
    drv.execute_native_query("INSERT INTO customers (id, name) VALUES (2, 'Grace')")
    try:
        yield drv
    finally:
        drv.disconnect()


def _pipeline(driver: SQLiteDriver, intent_dict: dict) -> SecureQueryPipeline:
    generator = QueryGenerator(_StubLLM(intent_dict), database_type="sqlite")
    return SecureQueryPipeline(
        driver=driver,
        generator=generator,
        validator=QuerySecurityValidator(),
        sanitizer=InputSanitizer(),
        schema=driver.fetch_schema(),
        enable_audit=False,
        # generation_mode defaults to "intent"; dialect auto-inferred as sqlite.
    )


def test_intent_path_binds_value_and_returns_rows(driver):
    pipe = _pipeline(
        driver,
        {
            "query_type": "SELECT",
            "tables": ["customers"],
            "columns": ["id", "name"],
            "conditions": {
                "conditions": [
                    {"column": "name", "operator": "=", "value": "Ada"}
                ]
            },
        },
    )

    result = pipe.run("find the customer named Ada")

    assert result.success is True, result.error
    # Value is a bound parameter — the literal 'Ada' never appears in the SQL text.
    assert result.sql == "SELECT id, name FROM customers WHERE name = ?"
    assert "Ada" not in result.sql
    assert result.results == [{"id": 1, "name": "Ada"}]


def test_intent_path_aggregate_order_limit(driver):
    pipe = _pipeline(
        driver,
        {
            "query_type": "AGGREGATE",
            "tables": ["customers"],
            "columns": [],
            "aggregations": [
                {"function": "COUNT", "column": "id", "alias": "n"}
            ],
        },
    )

    result = pipe.run("how many customers are there")

    assert result.success is True, result.error
    assert result.results == [{"n": 2}]


def test_intent_path_rejects_injection_value_as_bound_param(driver):
    # A classic injection payload as a *value* is harmless: it's bound, not parsed.
    pipe = _pipeline(
        driver,
        {
            "query_type": "SELECT",
            "tables": ["customers"],
            "columns": ["id", "name"],
            "conditions": {
                "conditions": [
                    {"column": "name", "operator": "=", "value": "x'; DROP TABLE customers;--"}
                ]
            },
        },
    )

    result = pipe.run("find a weird name")

    assert result.success is True, result.error
    assert result.results == []  # no such customer; table intact
    # Table still exists and still has both rows.
    rows = driver.execute_native_query("SELECT COUNT(*) AS c FROM customers")
    assert rows[0]["c"] == 2
