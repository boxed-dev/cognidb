"""PostgreSQL driver integration — skipped unless a URL env var is set.

Env (either):
  DATABASE_URL / COGNIDB_PG_URL
  e.g. postgresql://postgres:postgres@localhost:5432/cognidb

CI runs this under a dedicated job with a postgres:16 service.
"""

from __future__ import annotations

import os
from typing import Any, Dict
from urllib.parse import unquote, urlparse

import pytest

from cognidb.drivers import PostgreSQLDriver

_PG_URL = os.environ.get("COGNIDB_PG_URL") or os.environ.get("DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not _PG_URL,
    reason="Set DATABASE_URL or COGNIDB_PG_URL to run Postgres integration tests",
)


def _config_from_url(url: str) -> Dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme not in ("postgres", "postgresql"):
        raise ValueError(f"Unsupported DATABASE_URL scheme: {parsed.scheme!r}")
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "database": (parsed.path or "/").lstrip("/") or "postgres",
        "username": unquote(parsed.username) if parsed.username else "postgres",
        "password": unquote(parsed.password) if parsed.password else "",
        # Local CI / docker Postgres typically has no TLS.
        "ssl_enabled": False,
        "max_result_size": 100,
        "pool_size": 2,
        "query_timeout": 30,
        "connection_timeout": 10,
    }


@pytest.fixture
def pg_driver():
    assert _PG_URL
    drv = PostgreSQLDriver(_config_from_url(_PG_URL))
    drv.connect()
    try:
        # Isolate from other suites: drop/create a dedicated table.
        drv.execute_native_query("DROP TABLE IF EXISTS cognidb_pg_smoke")
        drv.execute_native_query(
            "CREATE TABLE cognidb_pg_smoke ("
            "id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
        )
        drv.execute_native_query(
            "INSERT INTO cognidb_pg_smoke (id, name) VALUES (1, 'Ada')"
        )
        yield drv
    finally:
        try:
            drv.execute_native_query("DROP TABLE IF EXISTS cognidb_pg_smoke")
        except Exception:
            pass
        drv.disconnect()


def test_postgres_connect_schema_and_select(pg_driver):
    rows = pg_driver.execute_native_query(
        "SELECT id, name FROM cognidb_pg_smoke ORDER BY id"
    )
    assert rows == [{"id": 1, "name": "Ada"}]

    schema = pg_driver.fetch_schema()
    assert "cognidb_pg_smoke" in schema
    assert "name" in schema["cognidb_pg_smoke"]
