"""Column allowlist enforcement in the secure query pipeline (Epic 2 / ADR 0005)."""

from __future__ import annotations

from cognidb.ai.fake_generator import FakeSQLGenerator
from cognidb.pipeline.secure_query import SecureQueryPipeline
from cognidb.security import (
    AccessController,
    InputSanitizer,
    Permission,
    QuerySecurityValidator,
    StatementPolicy,
    TablePermissions,
    UserPermissions,
)


class _Drv:
    def execute_native_query(self, query, params=None):
        return [{"ok": 1}]


def _pipe(sql, *, access, enable_ac=True):
    return SecureQueryPipeline(
        driver=_Drv(),
        generator=FakeSQLGenerator(sql),
        validator=QuerySecurityValidator(
            allowed_operations=["SELECT", "INSERT", "UPDATE", "DELETE"]
        ),
        sanitizer=InputSanitizer(),
        schema={"users": {"id": "int", "name": "text", "secret": "text"}},
        access_controller=access,
        enable_access_control=enable_ac,
        enable_audit=False,
        policy=StatementPolicy(),
        repair_budget=0,
        generation_mode="free_form",
        allow_dangerous_sql=True,
    )


def _analyst_with_columns(columns):
    ac = AccessController()
    user = UserPermissions(user_id="analyst")
    user.add_table_permission(
        TablePermissions(
            table_name="users",
            allowed_operations={Permission.SELECT},
            allowed_columns=set(columns),
        )
    )
    ac.add_user(user)
    return ac


def test_column_allowlist_denies_secret():
    """SELECT secret FROM users denied when allowlist is {id, name}."""
    ac = _analyst_with_columns({"id", "name"})
    r = _pipe("SELECT secret FROM users", access=ac).run(
        "show secrets", user_id="analyst"
    )
    assert r.success is False
    assert "Access denied" in (r.error or "")
    assert "secret" in (r.error or "").lower()


def test_column_allowlist_allows_id_name():
    ac = _analyst_with_columns({"id", "name"})
    r = _pipe("SELECT id, name FROM users", access=ac).run(
        "list users", user_id="analyst"
    )
    assert r.success is True


def test_select_star_rejected_when_column_allowlist_set():
    """Fail closed: SELECT * denied when a column allowlist is configured."""
    ac = _analyst_with_columns({"id", "name"})
    r = _pipe("SELECT * FROM users", access=ac).run("all columns", user_id="analyst")
    assert r.success is False
    err = (r.error or "").lower()
    assert "access denied" in err or "*" in err or "column" in err
