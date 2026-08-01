"""Database drivers module.

SQLite is always available (stdlib ``sqlite3``). The MySQL and PostgreSQL drivers
are imported **lazily** on first attribute access, so ``import cognidb`` — and any
SQLite-only usage — never requires the native ``psycopg2`` / ``mysql-connector``
packages. Install the matching extra to use them:

    pip install "cognidb[postgres]"   # PostgreSQL
    pip install "cognidb[mysql]"      # MySQL

MongoDB and DynamoDB are planned.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .sqlite_driver import SQLiteDriver

__all__ = [
    "MySQLDriver",
    "PostgreSQLDriver",
    "SQLiteDriver",
]

if TYPE_CHECKING:  # import for type-checkers only, never at runtime
    from .mysql_driver import MySQLDriver
    from .postgres_driver import PostgreSQLDriver


def __getattr__(name: str):  # PEP 562 lazy attribute loading
    if name == "PostgreSQLDriver":
        try:
            from .postgres_driver import PostgreSQLDriver
        except ImportError as e:  # pragma: no cover - exercised only without the extra
            raise ImportError(
                "PostgreSQL support requires psycopg2 — install `cognidb[postgres]`"
            ) from e
        return PostgreSQLDriver
    if name == "MySQLDriver":
        try:
            from .mysql_driver import MySQLDriver
        except ImportError as e:  # pragma: no cover - exercised only without the extra
            raise ImportError(
                "MySQL support requires mysql-connector-python — install `cognidb[mysql]`"
            ) from e
        return MySQLDriver
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
