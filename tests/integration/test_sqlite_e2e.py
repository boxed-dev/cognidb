"""Offline SQLite E2E: real tables + FakeSQLGenerator + SecureQueryPipeline.

Fully offline — no network LLM. Fixtures are local to this module so they
do not conflict with a shared tests/conftest.py owned by another slice.
"""

from __future__ import annotations

import pytest

from cognidb.ai.fake_generator import FakeSQLGenerator
from cognidb.drivers import SQLiteDriver
from cognidb.pipeline import SecureQueryPipeline
from cognidb.security import InputSanitizer, QuerySecurityValidator, StatementMode, StatementPolicy


@pytest.fixture
def sqlite_driver():
    """Connected in-memory SQLite with a small customers table."""
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


def _pipeline(driver: SQLiteDriver, generator: FakeSQLGenerator) -> SecureQueryPipeline:
    return SecureQueryPipeline(
        driver=driver,
        generator=generator,
        validator=QuerySecurityValidator(),
        sanitizer=InputSanitizer(),
        schema=driver.fetch_schema(),
        policy=StatementPolicy(mode=StatementMode.READ),
        generation_mode="free_form",
        allow_dangerous_sql=True,
        enable_audit=False,
        repair_budget=1,
    )


def test_sqlite_e2e_pipeline_returns_real_rows(sqlite_driver):
    """Create tables → canned SELECT → pipeline run → assert real rows."""
    gen = FakeSQLGenerator("SELECT id, name FROM customers ORDER BY id")
    pipe = _pipeline(sqlite_driver, gen)

    result = pipe.run("list customers")

    assert result.success is True
    assert result.repaired is False
    assert result.row_count == 2
    assert result.results == [
        {"id": 1, "name": "Ada"},
        {"id": 2, "name": "Grace"},
    ]
    assert gen.calls == 1
    assert gen.repair_calls == 0


def test_sqlite_e2e_repair_after_real_column_error(sqlite_driver):
    """Wrong column fails on real SQLite; repair_sql succeeds with repaired=True."""
    bad_sql = "SELECT id, missing_column FROM customers"
    good_sql = "SELECT id, name FROM customers WHERE id = 1"
    gen = FakeSQLGenerator(bad_sql, repair_sql=good_sql)
    pipe = _pipeline(sqlite_driver, gen)

    result = pipe.run("show customer one")

    assert result.success is True, result.error
    assert result.repaired is True
    assert result.sql == good_sql
    assert result.results == [{"id": 1, "name": "Ada"}]
    assert gen.calls == 1
    assert gen.repair_calls == 1
