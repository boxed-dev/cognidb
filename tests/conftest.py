"""Shared fixtures for CogniDB tests (Epic 0)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from cognidb.ai.fake_generator import FakeSQLGenerator
from cognidb.drivers import SQLiteDriver
from cognidb.security import (
    AccessController,
    InputSanitizer,
    QuerySecurityValidator,
    StatementMode,
    StatementPolicy,
    TablePermissions,
    UserPermissions,
    Permission,
)


SAMPLE_SCHEMA: Dict[str, Dict[str, str]] = {
    "users": {"id": "int", "name": "text", "email": "text", "secret": "text"},
    "orders": {"id": "int", "user_id": "int", "total": "int"},
}


@pytest.fixture
def sample_schema() -> Dict[str, Dict[str, str]]:
    """Minimal multi-table schema context for pipeline / linking tests."""
    return dict(SAMPLE_SCHEMA)


@pytest.fixture
def statement_policy_read() -> StatementPolicy:
    """Default read-mode statement policy."""
    return StatementPolicy(mode=StatementMode.READ)


@pytest.fixture
def statement_policy_write() -> StatementPolicy:
    """Write-mode statement policy (DML opt-in, no multi-statement)."""
    return StatementPolicy(mode=StatementMode.WRITE)


@pytest.fixture
def fake_sql_generator():
    """Factory for offline FakeSQLGenerator instances."""

    def _make(sql: str, *, repair_sql: Optional[str] = None) -> FakeSQLGenerator:
        return FakeSQLGenerator(sql, repair_sql=repair_sql)

    return _make


@pytest.fixture
def memory_sqlite():
    """
    In-memory SQLite helper with a seeded users table.

    Yields (driver, cleanup). Caller should use the driver while the fixture
    is active; disconnect happens on teardown.
    """
    drv = SQLiteDriver({"database": ":memory:", "max_result_size": 1000})
    drv.connect()
    drv.execute_native_query(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT, secret TEXT)"
    )
    drv.execute_native_query(
        "INSERT INTO users (id, name, email, secret) VALUES (1, 'Ada', 'ada@example.com', 'topsecret')"
    )
    drv.execute_native_query(
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, total INTEGER)"
    )
    try:
        yield drv
    finally:
        drv.disconnect()


@pytest.fixture
def default_validator() -> QuerySecurityValidator:
    return QuerySecurityValidator(
        allowed_operations=["SELECT", "INSERT", "UPDATE", "DELETE"]
    )


@pytest.fixture
def default_sanitizer() -> InputSanitizer:
    return InputSanitizer()


@pytest.fixture
def column_restricted_access() -> AccessController:
    """Caller 'analyst' may SELECT only id,name on users."""
    ac = AccessController()
    user = UserPermissions(user_id="analyst")
    user.add_table_permission(
        TablePermissions(
            table_name="users",
            allowed_operations={Permission.SELECT},
            allowed_columns={"id", "name"},
        )
    )
    ac.add_user(user)
    return ac
