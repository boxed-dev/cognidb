"""Adversarial SQL corpus — a fail-closed regression pack for the AST guard.

Every payload in ``adversarial_payloads.json`` must be **rejected** by the
guard-backed validator in read mode. These are the audit's *confirmed* bypasses
of the old regex/sqlparse checks: data-modifying CTEs, stacked statements,
DDL/admin nodes, DML in read mode, file-access writes, and — via the guard's
AST dangerous-function denylist — time-based and file/remote functions
(``SLEEP``, ``BENCHMARK``, ``pg_sleep``, ``LOAD_FILE``, ``pg_read_file``,
``load_extension``, ``dblink``, ...). All of these are still structurally blocked.

What is deliberately NOT rejected: pure *tautologies* (``OR 1=1``, ``OR 'a'='a'``,
``OR TRUE``, ``AND 2=2``, ``WHERE 1<2``), set operations (``UNION [ALL] SELECT``),
and a semicolon inside a string literal. The textual denylist that flagged those
was a false guarantee — a tautology only widens a SELECT *within already-
authorized tables*, so injection is defended downstream by parameter binding, a
read-only role, table/column allowlists, and row caps, not by whack-a-mole regex.
Those legitimate reads are asserted to PASS below.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cognidb.security import (
    QuerySecurityValidator,
    StatementMode,
    StatementPolicy,
    extract_tables,
)

CORPUS_PATH = Path(__file__).parent / "adversarial_payloads.json"


def _load_corpus() -> list[dict]:
    data = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    return data


def _read_validator() -> QuerySecurityValidator:
    """Default read-mode validator: SELECT only, single statement."""
    return QuerySecurityValidator(allowed_operations=["SELECT"])


CORPUS = _load_corpus()


def test_corpus_has_at_least_30_payloads():
    assert len(CORPUS) >= 30, f"corpus has {len(CORPUS)} payloads; need >=30"


def test_corpus_ids_are_unique():
    ids = [c["id"] for c in CORPUS]
    assert len(ids) == len(set(ids)), "duplicate corpus ids"


@pytest.mark.parametrize("case", CORPUS, ids=[c["id"] for c in CORPUS])
def test_adversarial_payload_rejected_by_guard(case: dict):
    """The guard-backed validator must fail closed on every corpus payload."""
    ok, err = _read_validator().validate_native_query(case["sql"])
    assert ok is False, (
        f"corpus hole: {case['id']} ({case.get('category')}) incorrectly PASSED "
        f"the guard-backed validator.\nsql={case['sql']!r}"
    )
    assert err, f"{case['id']} rejected without a reason"


# --- Legitimate reads the old regex wrongly flagged — must PASS ------------


def test_legitimate_select_still_allowed():
    ok, err = _read_validator().validate_native_query(
        "SELECT id, name FROM customers WHERE active = 1"
    )
    assert ok is True, f"legitimate SELECT rejected: {err}"

    # Defense in depth: a clean single SELECT also passes statement policy.
    policy = StatementPolicy(mode=StatementMode.READ)
    ok_m, err_m = policy.check_multi_statement("SELECT id FROM customers")
    assert ok_m is True, err_m


def test_literal_tautology_passes_defended_downstream():
    """WHERE 1 < 2 PASSES: a tautology only widens a SELECT within ACL'd tables."""
    ok, err = _read_validator().validate_native_query(
        "SELECT id FROM users WHERE 1 < 2"
    )
    assert ok is True, f"literal tautology wrongly rejected: {err}"


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT id FROM users WHERE id = 1 OR 1 = 1",
        "SELECT * FROM users WHERE name = 'x' OR 'a' = 'a'",
        "SELECT * FROM users WHERE id = 1 OR TRUE",
        "SELECT * FROM users WHERE id = 1 AND 2 = 2",
        "SELECT id FROM users WHERE status = 1 OR active = 1",
        "SELECT id FROM users WHERE col = 1 AND flag = 0",
    ],
    ids=["or-1eq1", "or-quoted", "or-true", "and-2eq2", "or-col", "and-col"],
)
def test_boolean_predicates_pass(sql: str):
    """OR/AND predicates (tautological or not) pass — defended downstream."""
    ok, err = _read_validator().validate_native_query(sql)
    assert ok is True, f"boolean predicate wrongly rejected: {err}\nsql={sql!r}"


def test_union_all_select_passes():
    ok, err = _read_validator().validate_native_query(
        "SELECT name FROM products UNION ALL SELECT title FROM catalog"
    )
    assert ok is True, f"UNION ALL wrongly rejected: {err}"


def test_semicolon_inside_string_literal_passes():
    """One statement — the semicolon is data, not a separator."""
    ok, err = _read_validator().validate_native_query(
        "SELECT id FROM users WHERE name = 'a;b'"
    )
    assert ok is True, f"semicolon-in-literal wrongly rejected: {err}"


# --- Extractor-level regressions: hidden tables must still be seen ---------


def test_comma_join_extracts_both_tables():
    tables = extract_tables("SELECT a.id, b.total FROM accounts a, balances b")
    assert set(tables) == {"accounts", "balances"}


def test_schema_qualified_extracts_both_tables():
    tables = extract_tables(
        "SELECT * FROM myschema.orders o JOIN public.customers c ON o.cid = c.id"
    )
    assert set(tables) == {"orders", "customers"}


def test_bracket_quoted_extracts_both_tables():
    tables = extract_tables(
        "SELECT * FROM [Users] u JOIN [Orders] o ON u.id = o.uid",
        dialect="sqlite",
    )
    assert set(tables) == {"users", "orders"}
