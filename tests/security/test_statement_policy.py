"""Statement policy ADR 0002–0004."""

import pytest
from cognidb.security.statement_policy import StatementMode, StatementPolicy


def test_read_mode_rejects_multi():
    p = StatementPolicy(mode=StatementMode.READ)
    ok, err = p.check_multi_statement("SELECT 1; DELETE FROM t")
    assert ok is False
    assert "read mode" in err.lower()


def test_write_mode_requires_second_flag_for_multi():
    p = StatementPolicy(mode=StatementMode.WRITE, allow_multi_statement=False)
    ok, err = p.check_multi_statement("SELECT 1; DELETE FROM t")
    assert ok is False
    assert "allow_multi_statement" in err


def test_write_mode_with_flag_allows_multi_shape():
    p = StatementPolicy(mode=StatementMode.WRITE, allow_multi_statement=True)
    ok, err = p.check_multi_statement("SELECT 1; DELETE FROM t")
    assert ok is True
    assert err is None


def test_multi_flag_without_write_raises():
    with pytest.raises(ValueError):
        StatementPolicy(mode=StatementMode.READ, allow_multi_statement=True)
