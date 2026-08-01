"""Behavior spec for the sqlglot AST security guard (cognidb.security.sql_guard).

Every case here is derived from the audit's confirmed bypasses. The guard is the
single source of parsing truth: statement-type gating, structural DDL/admin
rejection, data-modifying-CTE rejection, multi-statement rejection, and correct
table extraction (the thing the app-side regex got wrong).
"""

import pytest

from cognidb.security.sql_guard import analyze, GuardError, GuardResult, TableRef

READ = frozenset({"SELECT"})
WRITE = frozenset({"SELECT", "INSERT", "UPDATE", "DELETE"})


def keys(result: GuardResult):
    return {t.key for t in result.tables}


# --- legitimate SELECTs pass, with CORRECT table extraction ------------------

def test_plain_select_passes_and_extracts_table():
    r = analyze("SELECT id, name FROM users WHERE id = 5", dialect="sqlite", allowed_operations=READ)
    assert r.operation == "SELECT"
    assert keys(r) == {"users"}


def test_tautology_is_not_blocked_anymore():
    # Regex tautology denylist is intentionally deleted; a tautology only widens a
    # SELECT within already-authorized tables. It must parse clean, not error.
    r = analyze("SELECT id FROM accounts WHERE x = 5 OR 1 < 2", dialect="postgres", allowed_operations=READ)
    assert r.operation == "SELECT"
    assert keys(r) == {"accounts"}


def test_comma_join_extracts_all_tables():
    # Audit CRITICAL: regex returned only ['orders'], leaking `secret`.
    r = analyze("SELECT * FROM orders, secret", dialect="postgres", allowed_operations=READ)
    assert keys(r) == {"orders", "secret"}


def test_schema_qualified_extracts_real_table_not_schema():
    # Audit CRITICAL: regex returned ['public'] and never checked `salaries`.
    r = analyze("SELECT * FROM public.salaries", dialect="postgres", allowed_operations=READ)
    assert keys(r) == {"public.salaries"}
    assert any(t.name == "salaries" and t.db == "public" for t in r.tables)


def test_bracket_quoted_identifier_is_extracted_not_empty():
    # Audit CRITICAL: `[secret]` produced an empty table set -> ACL fail-open skip.
    # sqlite accepts MSSQL-style [bracket] quoting, so it is a real threat surface.
    r = analyze("SELECT * FROM [secret]", dialect="sqlite", allowed_operations=READ)
    assert keys(r) == {"secret"}


def test_join_extracts_both_tables():
    r = analyze("SELECT s.* FROM orders o JOIN secret s ON o.id = s.id", dialect="mysql", allowed_operations=READ)
    assert keys(r) == {"orders", "secret"}


def test_subquery_source_table_is_extracted():
    r = analyze("SELECT * FROM (SELECT * FROM secret) z", dialect="sqlite", allowed_operations=READ)
    assert keys(r) == {"secret"}


def test_union_all_passes_and_extracts_both_tables():
    # Audit: `UNION ALL` bypassed the regex. It is a legal read; extract both.
    r = analyze("SELECT a FROM t UNION ALL SELECT b FROM secrets", dialect="postgres", allowed_operations=READ)
    assert r.operation == "SELECT"
    assert keys(r) == {"t", "secrets"}


def test_cte_names_are_not_reported_as_tables():
    r = analyze("WITH c AS (SELECT 1 AS x) SELECT x FROM c", dialect="sqlite", allowed_operations=READ)
    assert keys(r) == set()  # `c` is a CTE alias, not a base table


def test_semicolon_inside_string_literal_is_one_statement():
    r = analyze("SELECT * FROM t WHERE note = 'a;b'", dialect="postgres", allowed_operations=READ)
    assert r.operation == "SELECT"
    assert keys(r) == {"t"}


# --- adversarial statements are REJECTED (fail closed) -----------------------

@pytest.mark.parametrize("sql,dialect", [
    ("WITH t AS (DELETE FROM users RETURNING *) SELECT * FROM t", "postgres"),  # data-modifying CTE
    ("WITH a AS (SELECT 1) DELETE FROM users", "postgres"),
    ("INSERT INTO users (name) VALUES ('x')", "sqlite"),
    ("UPDATE users SET name = 'x' WHERE id = 1", "sqlite"),
    ("DELETE FROM users WHERE id = 1", "sqlite"),
    ("DROP TABLE users", "sqlite"),
    ("TRUNCATE TABLE users", "postgres"),
    ("GRANT SELECT ON users TO bob", "postgres"),
    ("PRAGMA table_info(users)", "sqlite"),
    ("ATTACH DATABASE '/tmp/x.db' AS y", "sqlite"),
    ("COPY users TO '/tmp/out.csv'", "postgres"),
    ("VACUUM", "postgres"),
    ("SELECT 1; DROP TABLE users", "postgres"),  # stacked
])
def test_read_mode_rejects_dangerous_statements(sql, dialect):
    with pytest.raises(GuardError):
        analyze(sql, dialect=dialect, allowed_operations=READ)


def test_unparseable_sql_fails_closed():
    with pytest.raises(GuardError):
        analyze("SELCT foo FROM", dialect="sqlite", allowed_operations=READ)


def test_empty_sql_fails_closed():
    with pytest.raises(GuardError):
        analyze("   ", dialect="sqlite", allowed_operations=READ)


# --- write mode: DML allowed, DDL/admin still forbidden ----------------------

def test_write_mode_allows_insert():
    r = analyze("INSERT INTO users (name) VALUES ('x')", dialect="postgres", allowed_operations=WRITE)
    assert r.operation == "INSERT"
    assert keys(r) == {"users"}


def test_write_mode_allows_delete():
    r = analyze("DELETE FROM users WHERE id = 1", dialect="mysql", allowed_operations=WRITE)
    assert r.operation == "DELETE"


def test_write_mode_still_rejects_ddl():
    with pytest.raises(GuardError):
        analyze("DROP TABLE users", dialect="postgres", allowed_operations=WRITE)


def test_multi_statement_rejected_by_default_in_write_mode():
    with pytest.raises(GuardError):
        analyze("DELETE FROM a; DELETE FROM b", dialect="postgres", allowed_operations=WRITE)


def test_multi_statement_allowed_when_opted_in_but_ddl_still_rejected():
    r = analyze("DELETE FROM a WHERE id=1; UPDATE b SET x=1 WHERE id=2",
                dialect="postgres", allowed_operations=WRITE, allow_multi_statement=True)
    assert keys(r) == {"a", "b"}
    with pytest.raises(GuardError):
        analyze("DELETE FROM a; DROP TABLE b",
                dialect="postgres", allowed_operations=WRITE, allow_multi_statement=True)


# --- column extraction (best-effort, alias-resolved, for column ACL) ---------

def test_columns_grouped_by_table_with_alias_resolution():
    r = analyze("SELECT u.id, u.name FROM users AS u", dialect="postgres", allowed_operations=READ)
    assert set(r.columns_by_table["users"]) == {"id", "name"}


def test_star_column_recorded():
    r = analyze("SELECT * FROM users", dialect="sqlite", allowed_operations=READ)
    assert r.columns_by_table["users"] == ("*",)


# --- TableRef key normalization ----------------------------------------------

def test_tableref_key_lowercased():
    r = analyze("SELECT * FROM Orders", dialect="sqlite", allowed_operations=READ)
    assert keys(r) == {"orders"}


# --- non-gating compat helpers (used by the legacy shims) --------------------

def test_extract_table_refs_does_not_gate():
    from cognidb.security.sql_guard import extract_table_refs
    # Extraction returns tables even for statements analyze() would reject.
    refs = extract_table_refs("DELETE FROM users WHERE id = 1", dialect="postgres")
    assert {t.key for t in refs} == {"users"}
    refs2 = extract_table_refs("SELECT * FROM orders, secret")
    assert {t.key for t in refs2} == {"orders", "secret"}


def test_extract_table_refs_fails_closed_on_unparseable():
    from cognidb.security.sql_guard import extract_table_refs
    with pytest.raises(GuardError):
        extract_table_refs("SELCT nope FROM", dialect="sqlite")


def test_primary_operation():
    from cognidb.security.sql_guard import primary_operation
    assert primary_operation("SELECT 1", dialect="sqlite") == "SELECT"
    assert primary_operation("DELETE FROM t WHERE id=1", dialect="postgres") == "DELETE"
    assert primary_operation("DROP TABLE t", dialect="sqlite") == "DROP"
    assert primary_operation("VACUUM", dialect="postgres") == "COMMAND"


def test_dialect_none_uses_default_parser():
    r = analyze("SELECT id FROM users", dialect=None, allowed_operations=READ)
    assert keys(r) == {"users"}


# --- dangerous-function denylist (file access / RCE / time-based DoS) ---------

@pytest.mark.parametrize("sql,dialect", [
    ("SELECT load_file('/etc/passwd')", "mysql"),
    ("SELECT * FROM users WHERE SLEEP(5)", "mysql"),
    ("SELECT benchmark(1000000, md5('x'))", "mysql"),
    ("SELECT pg_sleep(5)", "postgres"),
    ("SELECT pg_read_file('/etc/passwd')", "postgres"),
    ("SELECT lo_import('/etc/passwd')", "postgres"),
    ("SELECT readfile('/etc/passwd')", "sqlite"),
    ("SELECT load_extension('evil.so')", "sqlite"),
    ("SELECT id FROM t WHERE name = pg_read_file('/x')", "postgres"),  # nested in WHERE
    ("SELECT pg_terminate_backend(123)", "postgres"),                  # connection DoS
])
def test_dangerous_functions_are_rejected(sql, dialect):
    with pytest.raises(GuardError):
        analyze(sql, dialect=dialect, allowed_operations=READ)


@pytest.mark.parametrize("sql,dialect", [
    ("SELECT COUNT(*) FROM users", "postgres"),
    ("SELECT UPPER(name), LENGTH(name) FROM users", "mysql"),
    ("SELECT id FROM users WHERE created_at > NOW()", "postgres"),
])
def test_ordinary_functions_are_allowed(sql, dialect):
    r = analyze(sql, dialect=dialect, allowed_operations=READ)
    assert r.operation == "SELECT"


# --- red-team regressions -----------------------------------------------------

@pytest.mark.parametrize("sql,dialect", [
    ('SELECT "pg_read_file"(\'/etc/passwd\')', "postgres"),   # quoted identifier evasion
    ('SELECT "pg_sleep"(10)', "postgres"),
    ("SELECT `sleep`(5)", "mysql"),                            # backtick-quoted
    ("SELECT [readfile]('/x')", "sqlite"),                     # bracket-quoted
])
def test_quoted_dangerous_functions_are_rejected(sql, dialect):
    # F1: the denylist must match the quote-stripped function name.
    with pytest.raises(GuardError):
        analyze(sql, dialect=dialect, allowed_operations=READ)


def test_cte_name_colliding_with_real_table_still_extracts_it():
    # F2: `secret` inside the CTE body is the PHYSICAL table; do not drop it.
    r = analyze("WITH secret AS (SELECT * FROM secret) SELECT * FROM secret",
                dialect="postgres", allowed_operations=READ)
    assert keys(r) == {"secret"}


def test_multi_table_star_recorded_for_every_table():
    # F3: `SELECT *` across a join must record `*` for both tables (column ACL).
    r = analyze("SELECT * FROM users u JOIN orders o ON u.id = o.uid",
                dialect="postgres", allowed_operations=READ)
    assert "*" in r.columns_by_table.get("users", ())
    assert "*" in r.columns_by_table.get("orders", ())


def test_multi_table_unqualified_column_attributed_fail_closed():
    # F3: an unqualified column in a multi-table read is attributed to all tables.
    r = analyze("SELECT ssn FROM users JOIN orders ON users.id = orders.uid",
                dialect="postgres", allowed_operations=READ)
    assert "ssn" in r.columns_by_table.get("users", ())
    assert "ssn" in r.columns_by_table.get("orders", ())


@pytest.mark.parametrize("sql", [
    "SELECT * INTO newtable FROM users",
    "SELECT id INTO other FROM users",
])
def test_select_into_is_rejected(sql):
    # F4: SELECT ... INTO creates a table on Postgres — not a read.
    with pytest.raises(GuardError):
        analyze(sql, dialect="postgres", allowed_operations=READ)
