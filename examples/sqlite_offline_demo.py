"""Offline SQLite demo — no network LLM.

Run from repo root (with package installed)::

    python examples/sqlite_offline_demo.py
"""

from cognidb.ai.fake_generator import FakeSQLGenerator
from cognidb.drivers import SQLiteDriver
from cognidb.pipeline import SecureQueryPipeline
from cognidb.security import InputSanitizer, QuerySecurityValidator, StatementMode, StatementPolicy


def main() -> None:
    drv = SQLiteDriver({"database": ":memory:"})
    drv.connect()
    try:
        drv.execute_native_query(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
        )
        drv.execute_native_query("INSERT INTO users (id, name) VALUES (1, 'Ada')")

        pipe = SecureQueryPipeline(
            driver=drv,
            generator=FakeSQLGenerator("SELECT id, name FROM users"),
            validator=QuerySecurityValidator(),
            sanitizer=InputSanitizer(),
            schema=drv.fetch_schema(),
            policy=StatementPolicy(mode=StatementMode.READ),
            enable_audit=False,
        )
        result = pipe.run("list users")
        print(result.to_dict())
    finally:
        drv.disconnect()


if __name__ == "__main__":
    main()
