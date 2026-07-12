"""Validator intent-path coverage for Epic 0 gate."""

from cognidb.core.query_intent import Column, QueryIntent, QueryType
from cognidb.security import QuerySecurityValidator


def test_validate_query_intent_allows_select():
    v = QuerySecurityValidator(allowed_operations=["SELECT"])
    intent = QueryIntent(
        query_type=QueryType.SELECT,
        tables=["users"],
        columns=[Column("id"), Column("name")],
    )
    ok, err = v.validate_query_intent(intent)
    assert ok is True
    assert err is None


def test_validate_query_intent_rejects_disallowed_type():
    v = QuerySecurityValidator(allowed_operations=["SELECT"])
    intent = QueryIntent(
        query_type=QueryType.INSERT,
        tables=["users"],
        columns=[Column("name")],
        values=["Ada"],
    )
    ok, err = v.validate_query_intent(intent)
    assert ok is False
    assert "INSERT" in (err or "")


def test_sanitize_identifier_and_value():
    v = QuerySecurityValidator()
    assert v.sanitize_identifier("users") == "users"
    assert v.sanitize_value("ok") == "ok"
    assert v.sanitize_value(None) is None
    assert v.sanitize_value(["a", "b"]) == ["a", "b"]
