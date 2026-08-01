"""PostgreSQL driver integration — real server, security-critical behavior.

Skipped cleanly (no failure, no hang) unless a connection URL env var is set:

  COGNIDB_PG_URL / DATABASE_URL
  e.g. postgresql://postgres:postgres@localhost:5432/cognidb

CI runs this under the ``postgres-integration`` job with a postgres:16 service.

Covers, against a *real* Postgres:
  - connect / disconnect lifecycle
  - parameterized ``execute_native_query`` binds values (no interpolation)
  - ``fetchmany`` row-cap truncation actually caps a large result set
  - statement timeout aborts a deliberately slow query
  - ``fetch_schema`` returns created tables/columns
  - non-row-returning statements report affected rows
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Any
from urllib.parse import unquote, urlparse

import pytest

from cognidb.core.exceptions import ExecutionError
from cognidb.drivers import PostgreSQLDriver

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (os.environ.get("COGNIDB_PG_URL") or os.environ.get("DATABASE_URL")),
        reason="Set DATABASE_URL or COGNIDB_PG_URL to run Postgres integration tests",
    ),
]

_TABLE = "cognidb_pg_integration"


def _pg_url() -> str:
    url = os.environ.get("COGNIDB_PG_URL") or os.environ.get("DATABASE_URL")
    assert url, "COGNIDB_PG_URL / DATABASE_URL must be set"
    return url


def _config(**overrides: Any) -> dict[str, Any]:
    parsed = urlparse(_pg_url())
    if parsed.scheme not in ("postgres", "postgresql"):
        raise ValueError(f"Unsupported Postgres URL scheme: {parsed.scheme!r}")
    config: dict[str, Any] = {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "database": (parsed.path or "/").lstrip("/") or "postgres",
        "username": unquote(parsed.username) if parsed.username else "postgres",
        "password": unquote(parsed.password) if parsed.password else "",
        # Local CI / docker Postgres typically has no TLS.
        "ssl_enabled": False,
        "sslmode": "disable",
        "max_result_size": 1000,
        "pool_size": 2,
        "query_timeout": 30,
        "connection_timeout": 10,
    }
    config.update(overrides)
    return config


@contextmanager
def _connected_driver(**overrides: Any):
    """A standalone connected driver for tests needing non-default config."""
    drv = PostgreSQLDriver(_config(**overrides))
    drv.connect()
    try:
        yield drv
    finally:
        drv.disconnect()


@pytest.fixture
def pg_driver():
    """Connected driver with a dedicated throwaway table, cleaned up after."""
    with _connected_driver() as drv:
        drv.execute_native_query(f"DROP TABLE IF EXISTS {_TABLE}")
        drv.execute_native_query(
            f"CREATE TABLE {_TABLE} (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
        )
        drv.execute_native_query(
            f"INSERT INTO {_TABLE} (id, name) VALUES (1, 'Ada'), (2, 'Grace')"
        )
        try:
            yield drv
        finally:
            try:
                drv.execute_native_query(f"DROP TABLE IF EXISTS {_TABLE}")
            except Exception:
                pass


def test_connect_and_disconnect():
    drv = PostgreSQLDriver(_config())
    drv.connect()
    assert drv.connection is not None
    assert drv.ping() is True

    drv.disconnect()
    assert drv.connection is None
    assert drv.pool is None


def test_select_returns_real_rows(pg_driver):
    rows = pg_driver.execute_native_query(f"SELECT id, name FROM {_TABLE} ORDER BY id")
    assert rows == [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Grace"}]


def test_parameterized_query_binds_values_not_interpolated(pg_driver):
    """A hostile value round-trips as inert data — never as SQL."""
    evil = "Robert'); DROP TABLE " + _TABLE + ";--"
    pg_driver.execute_native_query(
        f"INSERT INTO {_TABLE} (id, name) VALUES (%(id)s, %(name)s)",
        {"id": 3, "name": evil},
    )

    rows = pg_driver.execute_native_query(
        f"SELECT name FROM {_TABLE} WHERE name = %(name)s", {"name": evil}
    )
    assert rows == [{"name": evil}]

    # The injection attempt was inert: the table is still there with all rows.
    schema = pg_driver.fetch_schema()
    assert _TABLE in schema
    all_rows = pg_driver.execute_native_query(f"SELECT id FROM {_TABLE} ORDER BY id")
    assert len(all_rows) == 3


def test_fetchmany_row_cap_truncates_large_result():
    """A recursive CTE producing far more rows than the cap is truncated."""
    with _connected_driver(max_result_size=50) as drv:
        rows = drv.execute_native_query(
            "WITH RECURSIVE r(x) AS ("
            "  SELECT 1 UNION ALL SELECT x + 1 FROM r WHERE x < 5000"
            ") SELECT x FROM r"
        )
        assert len(rows) == 50
        assert rows[0] == {"x": 1}
        assert rows[-1] == {"x": 50}


def test_query_timeout_aborts_slow_query():
    """A deliberately slow query is aborted by the server-side statement timeout."""
    with _connected_driver(query_timeout=1) as drv:
        started = time.perf_counter()
        with pytest.raises(ExecutionError):
            drv.execute_native_query("SELECT pg_sleep(5)")
        elapsed = time.perf_counter() - started
        assert elapsed < 4.0


def test_fetch_schema_returns_created_tables_and_columns(pg_driver):
    schema = pg_driver.fetch_schema()
    assert _TABLE in schema
    assert "id" in schema[_TABLE]
    assert "name" in schema[_TABLE]
    assert "PRIMARY KEY" in schema[_TABLE]["id"]


def test_non_row_returning_statement_reports_affected_rows(pg_driver):
    result = pg_driver.execute_native_query(f"UPDATE {_TABLE} SET name = 'Updated'")
    assert result == [{"affected_rows": 2}]

    result = pg_driver.execute_native_query(f"DELETE FROM {_TABLE} WHERE id = 1")
    assert result == [{"affected_rows": 1}]
