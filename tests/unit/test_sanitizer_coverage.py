"""Sanitizer public-seam coverage for Epic 0 coverage gate."""

import pytest

from cognidb.security import InputSanitizer


def test_sanitize_natural_language_strips_and_truncates():
    assert InputSanitizer.sanitize_natural_language("") == ""
    out = InputSanitizer.sanitize_natural_language("list users; DROP TABLE x")
    assert "users" in out.lower()
    long = "x" * 1000
    assert len(InputSanitizer.sanitize_natural_language(long)) <= (
        InputSanitizer.MAX_NATURAL_LANGUAGE_LENGTH
    )


def test_sanitize_identifier():
    assert InputSanitizer.sanitize_identifier("users") == "users"
    assert InputSanitizer.sanitize_identifier("bad-name!") == "badname"
    with pytest.raises(ValueError):
        InputSanitizer.sanitize_identifier("")


def test_sanitize_string_and_numeric():
    s = InputSanitizer.sanitize_string_value("O'Reilly")
    assert isinstance(s, str)
    assert InputSanitizer.sanitize_numeric_value(42) == 42
    assert InputSanitizer.sanitize_numeric_value("3.5") == 3.5
    assert InputSanitizer.sanitize_list_value([1, 2], InputSanitizer.sanitize_numeric_value) == [
        1,
        2,
    ]
    d = InputSanitizer.sanitize_dict_value({"a": "x", "b": 1})
    assert "a" in d
