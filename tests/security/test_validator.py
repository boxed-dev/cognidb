"""Security validator regression tests (guard-backed contract).

``validate_native_query`` is now a thin delegation to ``sql_guard.analyze``.
The old textual denylist (tautologies, ``UNION SELECT``, time/file functions) is
DELETED by design: with a read-only role + parameter binding + ACL + row caps a
tautology only widens a SELECT within already-authorized tables. The validator's
job is now purely structural — reject anything that is not a gated read/write of
real tables, and let legitimate reads through so downstream layers defend them.
"""

import pytest

from cognidb.security import QuerySecurityValidator


# --- Real bypasses the structural guard must REJECT ------------------------


def test_rejects_drop():
    v = QuerySecurityValidator()
    ok, err = v.validate_native_query("DROP TABLE users;")
    assert ok is False
    assert err


def test_rejects_data_modifying_cte():
    """WITH t AS (DELETE ...) SELECT ... — a write hidden in a CTE."""
    v = QuerySecurityValidator()
    ok, err = v.validate_native_query(
        "WITH t AS (DELETE FROM users RETURNING id) SELECT * FROM t"
    )
    assert ok is False
    assert err


def test_rejects_stacked_statements():
    v = QuerySecurityValidator()
    ok, err = v.validate_native_query("SELECT 1; DELETE FROM users")
    assert ok is False
    assert err


@pytest.mark.parametrize(
    "sql",
    [
        "PRAGMA table_info(users)",
        "ATTACH DATABASE 'evil.db' AS evil",
        "COPY users TO '/tmp/dump.csv'",
        "VACUUM",
        "GRANT ALL ON *.* TO 'attacker'@'%'",
        "TRUNCATE TABLE users",
        "CREATE TABLE evil (id INT)",
        "ALTER TABLE users ADD COLUMN evil TEXT",
    ],
    ids=[
        "pragma",
        "attach",
        "copy",
        "vacuum",
        "grant",
        "truncate",
        "create",
        "alter",
    ],
)
def test_rejects_ddl_and_admin(sql):
    v = QuerySecurityValidator()
    ok, err = v.validate_native_query(sql)
    assert ok is False, f"expected rejection for {sql!r}"
    assert err


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO users (name) VALUES ('evil')",
        "UPDATE users SET role = 'admin' WHERE id = 1",
        "DELETE FROM users WHERE id = 1",
    ],
    ids=["insert", "update", "delete"],
)
def test_rejects_dml_in_read_mode(sql):
    """Default validator is SELECT-only; DML must be rejected."""
    v = QuerySecurityValidator()  # defaults to allowed_operations=['SELECT']
    ok, err = v.validate_native_query(sql)
    assert ok is False
    assert err


def test_rejects_unparseable_fail_closed():
    v = QuerySecurityValidator()
    ok, err = v.validate_native_query("SELECT password FROM users INTO OUTFILE '/tmp/x'")
    assert ok is False
    assert err


# --- Legitimate reads the OLD regex wrongly flagged, now ALLOWED -----------


def test_allows_simple_select():
    v = QuerySecurityValidator()
    ok, err = v.validate_native_query("SELECT id, name FROM customers WHERE active = 1")
    assert ok is True
    assert err is None


def test_allows_literal_tautology_defended_downstream():
    """WHERE 1 < 2 PASSES the validator now.

    It is a pure SELECT over authorized tables; a tautology only widens the
    row set *within* tables the ACL already permits. The old denylist gave a
    false guarantee — defense lives in the read-only role + params + ACL + caps.
    """
    v = QuerySecurityValidator()
    ok, err = v.validate_native_query("SELECT id FROM users WHERE 1 < 2")
    assert ok is True
    assert err is None


def test_allows_union_all_select():
    """UNION ALL SELECT is a legal read; it cannot escalate past table ACL."""
    v = QuerySecurityValidator()
    ok, err = v.validate_native_query(
        "SELECT name FROM products UNION ALL SELECT title FROM catalog"
    )
    assert ok is True
    assert err is None


def test_allows_semicolon_inside_string_literal():
    """A semicolon inside a quoted literal is ONE statement — must pass."""
    v = QuerySecurityValidator()
    ok, err = v.validate_native_query("SELECT id FROM users WHERE name = 'a;b'")
    assert ok is True
    assert err is None


# --- Constructor knobs -----------------------------------------------------


def test_dialect_is_threaded_to_guard():
    """Bracket-quoted identifiers parse under sqlite but not the default dialect."""
    sql = "SELECT [id] FROM [users]"
    v_sqlite = QuerySecurityValidator(dialect="sqlite")
    ok_sqlite, _ = v_sqlite.validate_native_query(sql)
    assert ok_sqlite is True

    v_default = QuerySecurityValidator()
    ok_default, err_default = v_default.validate_native_query(sql)
    assert ok_default is False
    assert err_default


def test_allow_multi_statement_opt_in():
    v = QuerySecurityValidator(
        allowed_operations=["SELECT", "INSERT", "UPDATE", "DELETE"],
        allow_multi_statement=True,
    )
    ok, err = v.validate_native_query("INSERT INTO t (a) VALUES (1); DELETE FROM t")
    assert ok is True, err


def test_allowed_operations_setter_round_trips():
    v = QuerySecurityValidator()
    assert v.allowed_operations == ["SELECT"]
    v.allowed_operations = ["SELECT", "INSERT"]
    assert v.allowed_operations == ["SELECT", "INSERT"]
    ok, _ = v.validate_native_query("INSERT INTO t (a) VALUES (1)")
    assert ok is True
