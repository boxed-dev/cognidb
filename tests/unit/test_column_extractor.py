"""Unit tests for column extraction helpers (guard-backed).

These helpers now delegate to ``sql_guard.analyze(...).columns_by_table`` — the
single AST source of truth — instead of regex scanning. Two behaviors changed
from the old regex extractor and are asserted here deliberately:

* INSERT target-column lists are not part of the guard's column set (they are
  ``exp.Schema``/``exp.Identifier`` nodes, not ``exp.Column``), so INSERT yields
  no columns. Write-column scope is governed by table-level write ACL instead.
* Ambiguous *unqualified* columns in a multi-table read are attributed to no
  table (best-effort); qualified columns are still attributed precisely. Intent-
  rendered SQL always qualifies columns, so the allowlist path is unaffected.
"""

import pytest

from cognidb.security.column_extractor import extract_columns, extract_columns_by_table


@pytest.mark.parametrize(
    "sql,expected",
    [
        ("SELECT secret FROM users", ["secret"]),
        ("SELECT id, name FROM users", ["id", "name"]),
        ("SELECT * FROM users", ["*"]),
        ("SELECT u.secret FROM users u", ["secret"]),
        ("SELECT id AS user_id FROM users", ["id"]),
        # INSERT target columns are not exposed by the AST column set -> empty.
        ("INSERT INTO users (name, email) VALUES ('a', 'b')", []),
        ("INSERT INTO users VALUES (1)", []),
        ("DELETE FROM users", []),
        ("", []),
    ],
)
def test_extract_columns(sql, expected):
    assert extract_columns(sql) == expected


def test_extract_columns_by_table_single():
    assert extract_columns_by_table("SELECT secret FROM users", ["users"]) == {
        "users": ["secret"]
    }


def test_extract_columns_by_table_multi_qualified():
    mapping = extract_columns_by_table(
        "SELECT users.id, orders.total FROM users JOIN orders",
        ["users", "orders"],
    )
    assert mapping["users"] == ["id"]
    assert mapping["orders"] == ["total"]


def test_extract_columns_by_table_multi_unqualified_fail_closed():
    """Unqualified columns across multiple tables are attributed to ALL of them.

    The guard cannot disambiguate a bare ``id`` between ``users`` and ``orders``
    without a schema, so it fails CLOSED — every candidate table sees the column,
    and a column allowlist that restricts either one will reject it.
    """
    mapping = extract_columns_by_table(
        "SELECT id FROM users JOIN orders",
        ["users", "orders"],
    )
    assert mapping == {"users": ["id"], "orders": ["id"]}


def test_extract_columns_star_survives_for_allowlist_fail_closed():
    """SELECT * must still surface ``*`` so a column allowlist can reject it."""
    assert extract_columns_by_table("SELECT * FROM users", ["users"]) == {
        "users": ["*"]
    }


def test_extract_columns_unparseable_fails_closed_empty():
    assert extract_columns("DROP TABLE users") == []
    assert extract_columns_by_table("DROP TABLE users", ["users"]) == {"users": []}
