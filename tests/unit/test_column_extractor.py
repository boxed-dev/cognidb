"""Unit tests for column extraction helpers (Epic 2)."""

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
        ("INSERT INTO users (name, email) VALUES ('a', 'b')", ["name", "email"]),
        ("INSERT INTO users VALUES (1)", ["*"]),
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
    mapping = extract_columns_by_table(
        "SELECT id FROM users JOIN orders",
        ["users", "orders"],
    )
    assert mapping["users"] == ["id"]
    assert mapping["orders"] == ["id"]
