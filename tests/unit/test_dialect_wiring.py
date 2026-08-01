"""Drivers advertise their sqlglot dialect so the pipeline/guard/renderer can
target the right engine (intent mode requires a concrete dialect)."""

from cognidb.drivers import SQLiteDriver, PostgreSQLDriver, MySQLDriver
from cognidb.pipeline.secure_query import _infer_dialect


def test_drivers_expose_dialect():
    assert SQLiteDriver.dialect == "sqlite"
    assert PostgreSQLDriver.dialect == "postgres"
    assert MySQLDriver.dialect == "mysql"


def test_pipeline_infers_dialect_from_driver():
    assert _infer_dialect(SQLiteDriver({"database": ":memory:"})) == "sqlite"


def test_postgres_pool_submodule_is_imported():
    # `import psycopg2` does not bind psycopg2.pool; connect() references the
    # pool module, so a missing `from psycopg2 import pool` regresses only
    # against a live server. Catch it here with no DB.
    from cognidb.drivers import postgres_driver

    assert hasattr(postgres_driver.pool, "ThreadedConnectionPool")
