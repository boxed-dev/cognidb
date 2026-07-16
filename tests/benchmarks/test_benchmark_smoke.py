"""CI smoke tests for the offline CogniDB benchmark harness.

Full suite: ``python -m benchmarks.run --track all``
Smoke CLI:  ``python -m benchmarks.run --track all --smoke``
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.metrics import exact_sql_match, normalize_sql, result_match, soft_match
from benchmarks.runner import BenchmarkRunner, load_jsonl
from benchmarks.run import main as bench_main
from benchmarks.types import score_of

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "benchmarks" / "data"


def test_datasets_meet_minimum_sizes():
    correctness = load_jsonl(DATA / "correctness.jsonl")
    security = load_jsonl(DATA / "security.jsonl")
    policy = load_jsonl(DATA / "policy.jsonl")
    robustness = load_jsonl(DATA / "robustness.jsonl")
    assert len(correctness) >= 80, len(correctness)
    assert len(security) >= 60, len(security)
    assert len(policy) >= 15, len(policy)
    assert len(robustness) >= 10, len(robustness)


def test_metrics_helpers():
    assert exact_sql_match(
        "select id, name from customers",
        "SELECT id, name FROM customers",
    )
    assert normalize_sql("SELECT   id\nFROM t;") == normalize_sql("select id from t")
    assert result_match(
        [{"b": 2, "a": 1}],
        [{"a": 1, "b": 2}],
        ordered=False,
    )
    assert soft_match(
        "SELECT id, name FROM customers",
        "SELECT name, id FROM customers WHERE id = 1",
    )


def test_score_of():
    assert score_of(8, 10) == 0.8
    assert score_of(0, 0) == 0.0


def test_smoke_runner_all_tracks_offline():
    runner = BenchmarkRunner(smoke=True, smoke_limit=3, seed=42)
    report = runner.run(["all"])
    assert set(report.tracks) == {
        "correctness",
        "security",
        "policy",
        "robustness",
    }
    for name, tr in report.tracks.items():
        assert tr.total > 0, name
        assert tr.score == 1.0, f"{name} failures: {[c for c in tr.cases if not c.passed]}"
    assert not report.hard_failures()
    assert report.offline is True


def test_cli_smoke_exits_zero(tmp_path, monkeypatch):
    # Write reports under tmp via monkeypatch of REPORTS_DIR usage — CLI writes to package reports.
    # Use --no-report-file to avoid polluting tree in CI if desired; still exercise main.
    rc = bench_main(
        [
            "--track",
            "security",
            "--track",
            "correctness",
            "--smoke",
            "--smoke-limit",
            "2",
            "--format",
            "json",
            "--fail-under",
            "1.0",
            "--no-report-file",
        ]
    )
    assert rc == 0


def test_security_false_accept_would_fail_suite():
    """Guard: security track treats any accept as a failed case."""
    runner = BenchmarkRunner(smoke=True, smoke_limit=5)
    report = runner.run(["security"])
    assert report.tracks["security"].score == 1.0
    assert report.tracks["security"].extras.get("false_accepts", 0) == 0


def test_sample_report_schema_if_present():
    sample = ROOT / "benchmarks" / "reports" / "SAMPLE_REPORT.json"
    if not sample.exists():
        pytest.skip("sample report not checked in")
    data = json.loads(sample.read_text(encoding="utf-8"))
    assert "tracks" in data
    assert "overall_score" in data
