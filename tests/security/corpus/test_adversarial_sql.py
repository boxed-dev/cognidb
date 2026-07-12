"""Adversarial SQL corpus — every payload must fail closed in read mode.

Seams under test (Epic E3 / Slice 3.1):
- StatementPolicy.check_multi_statement (read mode: multi-stmt forbidden)
- QuerySecurityValidator.validate_native_query (SELECT-only + injection patterns)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cognidb.security import QuerySecurityValidator, StatementMode, StatementPolicy

CORPUS_PATH = Path(__file__).parent / "adversarial_payloads.json"


def _load_corpus() -> list[dict]:
    data = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    return data


def _fails_read_mode(sql: str) -> tuple[bool, str]:
    """Return (rejected, reason). Rejected if policy or validator fails closed."""
    policy = StatementPolicy(mode=StatementMode.READ)
    ok_multi, err_multi = policy.check_multi_statement(sql)
    if not ok_multi:
        return True, err_multi or "multi-statement rejected"

    validator = QuerySecurityValidator(allowed_operations=["SELECT"])
    ok_val, err_val = validator.validate_native_query(sql)
    if not ok_val:
        return True, err_val or "validator rejected"

    return False, "passed both statement policy and validator"


CORPUS = _load_corpus()


def test_corpus_has_at_least_30_payloads():
    assert len(CORPUS) >= 30, f"corpus has {len(CORPUS)} payloads; need ≥30"


@pytest.mark.parametrize(
    "case",
    CORPUS,
    ids=[c["id"] for c in CORPUS],
)
def test_adversarial_payload_fails_read_mode(case: dict):
    sql = case["sql"]
    rejected, reason = _fails_read_mode(sql)
    assert rejected, (
        f"corpus hole: {case['id']} ({case.get('category')}) incorrectly PASSED "
        f"read-mode enforcement.\nsql={sql!r}\nlast_reason={reason}"
    )


def test_legitimate_select_still_allowed():
    """Corpus hardening must not gut SELECT-only legitimate queries."""
    validator = QuerySecurityValidator(allowed_operations=["SELECT"])
    ok, err = validator.validate_native_query(
        "SELECT id, name FROM customers WHERE active = 1"
    )
    assert ok is True, f"legitimate SELECT rejected: {err}"

    policy = StatementPolicy(mode=StatementMode.READ)
    ok_m, err_m = policy.check_multi_statement("SELECT id FROM customers")
    assert ok_m is True, err_m


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT id FROM users WHERE status = 1 OR active = 1",
        "SELECT id FROM users WHERE id = 1 OR role = 'admin'",
        "SELECT id FROM users WHERE col = 1 AND flag = 0",
        "SELECT id FROM users WHERE name = 'TRUE' OR code = 'admin'",
    ],
    ids=["or-col-eq-num", "or-col-eq-str", "and-col-eq", "or-string-value-true"],
)
def test_legitimate_or_and_business_filters_allowed(sql: str):
    """Column-vs-literal OR/AND filters must not be treated as tautology SQLi."""
    validator = QuerySecurityValidator(allowed_operations=["SELECT"])
    ok, err = validator.validate_native_query(sql)
    assert ok is True, f"legitimate business filter rejected: {err}\nsql={sql!r}"
