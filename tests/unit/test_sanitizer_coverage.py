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
