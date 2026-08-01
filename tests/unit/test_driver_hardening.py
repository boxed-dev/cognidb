"""Driver hardening (Contract 4, Module-B).

Covers the confirmed audit findings:

1. fetchall()-then-slice DoS killed by streaming cursors + fetchmany-to-cap.
   SQLite is tested for *real* behaviour (an effectively unbounded recursive
   CTE must not be materialised); Postgres/MySQL routing is unit-tested with
   mocks since no server runs locally.
2. SQLite statement timeout via connection.interrupt() watchdog.
3. TLS config assembly (PG sslmode=verify-full + sslrootcert; MySQL
   ssl_verify_identity) asserted on the constructed connect kwargs.
4. No raw DB error string leaks to the caller — messages are generic.

The two behavioural SQLite tests are self-bounding in the *green* state: the
interrupt watchdog aborts any runaway within ``query_timeout`` so a broken
implementation fails fast instead of hanging.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import mysql.connector
import psycopg2
import pytest

from cognidb.core.exceptions import ExecutionError
from cognidb.drivers import MySQLDriver, PostgreSQLDriver, SQLiteDriver

# A recursive CTE whose upper bound is so large it is effectively unbounded:
# a fetchall() would never return, so only a streaming cursor survives it.
_UNBOUNDED_CTE = (
    "WITH RECURSIVE r(x) AS ("
    "  SELECT 1 UNION ALL SELECT x + 1 FROM r WHERE x < 1000000000000"
    ") SELECT x FROM r"
)


def _bounded_cte(n: int) -> str:
    return (
        "WITH RECURSIVE r(x) AS ("
        f"  SELECT 1 UNION ALL SELECT x + 1 FROM r WHERE x < {n}"
        ") SELECT x FROM r"
    )


# --------------------------------------------------------------------------- #
# 1. SQLite — streaming row cap (real behaviour)                              #
# --------------------------------------------------------------------------- #


def test_sqlite_streaming_row_cap_does_not_materialize():
    """An unbounded CTE returns exactly the cap, fast — proof of streaming.

    Old code did ``cursor.fetchall()[:max]`` which never returns on this query.
    ``query_timeout`` is set so a regression can only *fail*, never hang.
    """
    drv = SQLiteDriver(
        {"database": ":memory:", "max_result_size": 50, "query_timeout": 10}
    )
    drv.connect()
    try:
        started = time.perf_counter()
        rows = drv.execute_native_query(_UNBOUNDED_CTE)
        elapsed = time.perf_counter() - started

        assert len(rows) == 50
        assert rows[0] == {"x": 1}
        assert rows[-1] == {"x": 50}
        # Streaming to the cap is effectively instant; materialising would
        # either hang (unbounded) or hit the 10s watchdog.
        assert elapsed < 2.0
    finally:
        drv.disconnect()


def test_sqlite_row_cap_exact_boundary():
    """fetchmany(cap + 1) yields exactly the cap; smaller sets pass through."""
    drv = SQLiteDriver({"database": ":memory:", "max_result_size": 100})
    drv.connect()
    try:
        capped = drv.execute_native_query(_bounded_cte(250))
        assert len(capped) == 100

        under = drv.execute_native_query(_bounded_cte(10))
        assert len(under) == 10
        assert under[-1] == {"x": 10}
    finally:
        drv.disconnect()


# --------------------------------------------------------------------------- #
# 2. SQLite — statement timeout watchdog                                      #
# --------------------------------------------------------------------------- #


def test_sqlite_query_timeout_interrupts_runaway():
    """A runaway aggregate over an unbounded CTE is interrupted ~query_timeout."""
    drv = SQLiteDriver(
        {"database": ":memory:", "query_timeout": 1, "max_result_size": 10}
    )
    drv.connect()
    try:
        runaway = (
            "WITH RECURSIVE r(x) AS ("
            "  SELECT 1 UNION ALL SELECT x + 1 FROM r WHERE x < 1000000000000"
            ") SELECT count(*) FROM r"
        )
        started = time.perf_counter()
        with pytest.raises(ExecutionError):
            drv.execute_native_query(runaway)
        elapsed = time.perf_counter() - started

        assert 0.5 < elapsed < 6.0
    finally:
        drv.disconnect()


# --------------------------------------------------------------------------- #
# 4. SQLite — generic error, no raw DB detail leaked                          #
# --------------------------------------------------------------------------- #


def test_sqlite_error_message_is_generic():
    """The raw SQLite error (a table name here) never reaches the caller."""
    drv = SQLiteDriver({"database": ":memory:"})
    drv.connect()
    try:
        with pytest.raises(ExecutionError) as excinfo:
            drv.execute_native_query("SELECT * FROM nonexistent_secret_table_xyz")
        message = str(excinfo.value)
        assert message == "query execution failed"
        assert "nonexistent_secret_table_xyz" not in message
        assert "no such table" not in message
    finally:
        drv.disconnect()


# --------------------------------------------------------------------------- #
# Contract 2 — SQLite param binding (sequence + mapping)                       #
# --------------------------------------------------------------------------- #


def test_sqlite_params_bound_via_dbapi():
    """Values are bound by the DBAPI, never string-formatted (no injection)."""
    drv = SQLiteDriver({"database": ":memory:"})
    drv.connect()
    try:
        drv.execute_native_query("CREATE TABLE t (id INTEGER, name TEXT)")
        evil = "Robert'); DROP TABLE t;--"
        drv.execute_native_query(
            "INSERT INTO t (id, name) VALUES (?, ?)", [1, evil]
        )

        by_seq = drv.execute_native_query(
            "SELECT name FROM t WHERE name = ?", [evil]
        )
        assert by_seq == [{"name": evil}]

        by_map = drv.execute_native_query(
            "SELECT name FROM t WHERE name = :n", {"n": evil}
        )
        assert by_map == [{"name": evil}]

        # The injection was inert: the table still exists.
        assert "t" in drv.fetch_schema()
    finally:
        drv.disconnect()


# --------------------------------------------------------------------------- #
# 3. Postgres — TLS config assembly (mocked, no server)                       #
# --------------------------------------------------------------------------- #


def test_postgres_connect_params_default_verify_full():
    drv = PostgreSQLDriver(
        {
            "host": "db.internal",
            "database": "app",
            "username": "svc",
            "password": "pw",
            "sslrootcert": "/etc/ssl/root.pem",
            "query_timeout": 45,
        }
    )
    params = drv._connect_params()

    assert params["sslmode"] == "verify-full"
    assert params["sslrootcert"] == "/etc/ssl/root.pem"
    assert "statement_timeout=45s" in params["options"]


def test_postgres_connect_params_never_silently_downgrade():
    """Legacy ssl_ca_cert still wires sslrootcert; default stays verify-full."""
    drv = PostgreSQLDriver(
        {
            "host": "h",
            "database": "d",
            "ssl_ca_cert": "/legacy/ca.pem",
        }
    )
    params = drv._connect_params()
    assert params["sslmode"] == "verify-full"
    assert params["sslrootcert"] == "/legacy/ca.pem"


# --------------------------------------------------------------------------- #
# 1. Postgres — server-side cursor + cap (mocked)                             #
# --------------------------------------------------------------------------- #


def test_postgres_select_uses_server_side_cursor_and_caps():
    drv = PostgreSQLDriver({"max_result_size": 5})
    conn = MagicMock()
    conn.closed = False
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    # One row beyond the cap so truncation is detected.
    cursor.fetchmany.return_value = [{"id": i} for i in range(6)]
    drv.connection = conn

    rows = drv._execute_with_timeout("SELECT id FROM t")

    assert len(rows) == 5
    conn.cursor.assert_called_once()
    _, kwargs = conn.cursor.call_args
    assert kwargs.get("name"), "expected a server-side (named) cursor"
    assert cursor.itersize == 5
    cursor.fetchmany.assert_called_once_with(6)


def test_postgres_non_select_uses_client_cursor():
    drv = PostgreSQLDriver({})
    conn = MagicMock()
    conn.closed = False
    cursor = MagicMock()
    cursor.rowcount = 3
    conn.cursor.return_value = cursor
    drv.connection = conn

    rows = drv._execute_with_timeout("INSERT INTO t (id) VALUES (1)")

    assert rows == [{"affected_rows": 3}]
    _, kwargs = conn.cursor.call_args
    assert "name" not in kwargs


def test_postgres_error_message_is_generic():
    drv = PostgreSQLDriver({})
    conn = MagicMock()
    conn.closed = False
    cursor = MagicMock()
    cursor.execute.side_effect = psycopg2.DatabaseError("SECRET_INTERNAL_PG detail")
    conn.cursor.return_value = cursor
    drv.connection = conn

    with pytest.raises(ExecutionError) as excinfo:
        drv._execute_with_timeout("SELECT 1")
    message = str(excinfo.value)
    assert message == "query execution failed"
    assert "SECRET_INTERNAL_PG" not in message


# --------------------------------------------------------------------------- #
# 3. MySQL — TLS config assembly (mocked, no server)                          #
# --------------------------------------------------------------------------- #


def test_mysql_pool_config_ssl_verify_identity():
    drv = MySQLDriver(
        {
            "host": "h",
            "database": "d",
            "ssl_enabled": True,
            "ssl_ca_cert": "/etc/ssl/ca.pem",
        }
    )
    cfg = drv._pool_config()

    assert cfg["ssl_disabled"] is False
    assert cfg["ssl_verify_cert"] is True
    assert cfg["ssl_verify_identity"] is True
    assert cfg["ca"] == "/etc/ssl/ca.pem"


def test_mysql_pool_config_ssl_disabled_when_off():
    drv = MySQLDriver({"host": "h", "database": "d"})
    cfg = drv._pool_config()
    assert "ssl_verify_identity" not in cfg


# --------------------------------------------------------------------------- #
# 1. MySQL — unbuffered cursor + cap, and param passthrough (mocked)          #
# --------------------------------------------------------------------------- #


def _mysql_mock_driver(cap: int = 5):
    drv = MySQLDriver({"max_result_size": cap, "query_timeout": 7})
    conn = MagicMock()
    conn.is_connected.return_value = True
    drv.connection = conn
    return drv, conn


def test_mysql_select_uses_unbuffered_cursor_and_caps():
    drv, conn = _mysql_mock_driver(cap=5)
    cursor = MagicMock()
    cursor.description = [("x",)]
    cursor.fetchmany.return_value = [{"x": i} for i in range(6)]
    conn.cursor.return_value = cursor

    rows = drv._execute_with_timeout("SELECT x FROM t")

    assert len(rows) == 5
    _, kwargs = conn.cursor.call_args
    assert kwargs.get("buffered") is False, "expected an unbuffered (streaming) cursor"
    cursor.fetchmany.assert_called_once_with(6)
    # MAX_EXECUTION_TIME (ms) session setting applied.
    joined = " ".join(str(c.args[0]) for c in conn.cmd_query.call_args_list)
    assert "MAX_EXECUTION_TIME=7000" in joined


def test_mysql_params_passed_through_unchanged():
    drv, conn = _mysql_mock_driver()
    cursor = MagicMock()
    cursor.description = [("x",)]
    cursor.fetchmany.return_value = []
    conn.cursor.return_value = cursor

    drv._execute_with_timeout("SELECT x FROM t WHERE x = %s", ("Ada",))
    cursor.execute.assert_called_once_with("SELECT x FROM t WHERE x = %s", ("Ada",))

    cursor.execute.reset_mock()
    mapping = {"name": "Ada"}
    drv._execute_with_timeout("SELECT x FROM t WHERE x = %(name)s", mapping)
    cursor.execute.assert_called_once_with(
        "SELECT x FROM t WHERE x = %(name)s", mapping
    )


def test_mysql_error_message_is_generic():
    drv, conn = _mysql_mock_driver()
    cursor = MagicMock()
    cursor.execute.side_effect = mysql.connector.Error("SECRET_INTERNAL_MYSQL detail")
    conn.cursor.return_value = cursor

    with pytest.raises(ExecutionError) as excinfo:
        drv._execute_with_timeout("SELECT 1")
    message = str(excinfo.value)
    assert message == "query execution failed"
    assert "SECRET_INTERNAL_MYSQL" not in message
