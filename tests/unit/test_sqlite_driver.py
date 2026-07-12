"""SQLite driver is a real second adapter for the DatabaseDriver seam."""

from cognidb.drivers import SQLiteDriver


def test_sqlite_memory_schema_and_query():
    drv = SQLiteDriver({"database": ":memory:", "max_result_size": 100})
    drv.connect()
    try:
        drv.execute_native_query(
            "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT)"
        )
        drv.execute_native_query(
            "INSERT INTO customers (name) VALUES ('Ada')"
        )
        # re-run as select path
        rows = drv.execute_native_query("SELECT id, name FROM customers")
        assert rows[0]["name"] == "Ada"
        schema = drv.fetch_schema()
        assert "customers" in schema
        assert "name" in schema["customers"]
    finally:
        drv.disconnect()
