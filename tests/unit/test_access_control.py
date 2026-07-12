"""AccessController coverage for column allowlists and helpers (Epic 2)."""

import pytest

from cognidb.core.exceptions import SecurityError
from cognidb.security import (
    AccessController,
    Permission,
    TablePermissions,
    UserPermissions,
)


def test_check_column_access_denies_and_allows():
    ac = AccessController()
    ac.create_restricted_user(
        "analyst",
        {"users": {"operations": ["SELECT"], "columns": ["id", "name"]}},
    )
    ac.check_column_access("analyst", "users", ["id", "name"])
    with pytest.raises(SecurityError, match="secret"):
        ac.check_column_access("analyst", "users", ["secret"])


def test_star_denied_when_allowlist_set():
    ac = AccessController()
    ac.create_restricted_user(
        "analyst",
        {"users": {"operations": ["SELECT"], "columns": ["id"]}},
    )
    with pytest.raises(SecurityError, match=r"SELECT \*"):
        ac.check_column_access("analyst", "users", ["*"])


def test_star_allowed_when_no_column_allowlist():
    ac = AccessController()
    ac.create_read_only_user("reader", ["users"])
    ac.check_column_access("reader", "users", ["*"])


def test_admin_bypasses_column_checks():
    ac = AccessController()
    ac.add_user(UserPermissions(user_id="admin", is_admin=True))
    ac.check_column_access("admin", "users", ["secret", "*"])


def test_check_operation_and_row_filters():
    ac = AccessController()
    user = UserPermissions(user_id="u1")
    user.add_table_permission(
        TablePermissions(
            table_name="users",
            allowed_operations={Permission.SELECT},
            row_filter="department = 'sales'",
        )
    )
    ac.add_user(user)
    ac.check_operation("u1", Permission.SELECT, ["users"])
    with pytest.raises(SecurityError):
        ac.check_operation("u1", Permission.DELETE, ["users"])
    assert ac.get_row_filters("u1", "users") == "department = 'sales'"
    assert ac.get_resource_limits("u1")["max_rows"] == 10000
