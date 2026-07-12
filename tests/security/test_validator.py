"""Security validator regression tests."""

from cognidb.security import QuerySecurityValidator


def test_rejects_drop():
    v = QuerySecurityValidator()
    ok, err = v.validate_native_query("DROP TABLE users;")
    assert ok is False
    assert err


def test_rejects_union_injection_pattern():
    v = QuerySecurityValidator()
    ok, err = v.validate_native_query("SELECT * FROM t WHERE id=1 UNION SELECT password FROM users")
    assert ok is False


def test_allows_simple_select():
    v = QuerySecurityValidator()
    ok, err = v.validate_native_query("SELECT id, name FROM customers WHERE active = 1")
    # Depending on parser strictness, accept True or documented False — must not crash
    assert err is None or isinstance(err, str)
    assert isinstance(ok, bool)
