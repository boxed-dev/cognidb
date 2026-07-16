# CogniDB offline benchmark suite

Stress-tested evaluation of the **`SecureQueryPipeline`** seam: NL→SQL correctness, security fail-closed behavior, statement policy / access control, and offline robustness.

This is a **library** harness, not a chat product eval. It does not open the network unless you deliberately build a live adapter later.

## Quick start

```bash
# From repo root (editable install recommended)
pip install -e ".[dev]"

# Full offline suite (writes benchmarks/reports/report_*.json)
python -m benchmarks.run --track all

# One track
python -m benchmarks.run --track security --format text

# CI-friendly smoke + gate
python -m benchmarks.run --track all --smoke --fail-under 1.0

# JSON to stdout
python -m benchmarks.run --track correctness --format json --no-report-file
```

Pytest smoke (default CI surface):

```bash
pytest -q tests/benchmarks/test_benchmark_smoke.py
```

## Tracks

| Track | Cases (approx.) | What it measures |
|---|---|---|
| **correctness** | ≥80 curated | Execution-result match (primary) on a multi-table SQLite commerce fixture; exact SQL + soft table/column match recorded. Free-form + intent mode. |
| **security** | ≥60 adversarial | Hostile SQL through the **same pipeline enforcement path** (`sql_override` / generator) in **read mode**. Metric: % correctly rejected. **Any false accept fails the suite hard.** |
| **policy** | ≥15 | Table/column allowlists (incl. `SELECT *` fail-closed), write-mode / multi-statement double opt-in negatives, repair-then-success and repair-still-violates. |
| **robustness** | ≥10 | Large-schema linking bounds, soak re-runs, offline p50/p95 latency (informational — not flaky CI thresholds). |

## How to read scores

```
overall_score=1.0000  duration_ms=…
  [correctness] score=1.0000  passed=85/85
  [security]    score=1.0000  passed=80/80   false_accepts=0
  [policy]      score=1.0000  passed=23/23
  [robustness]  score=1.0000  latency p50/p95 …
```

- **score** = passed / total for that track (0.0–1.0).
- **Primary correctness metric** is **execution result match** against golden SQL on the fixture DB (order-tolerant unless the case sets `"ordered": true`).
- **Security / policy false accepts** are hard failures (`exit 1`) even if you omit `--fail-under`.
- Use `--fail-under 1.0` to require perfect scores on selected tracks in CI.

Sample report schema: `benchmarks/reports/SAMPLE_REPORT.json`. Generated reports under `benchmarks/reports/` are gitignored except the sample.

## Architecture

```
benchmarks/
  run.py                 # CLI (python -m benchmarks.run)
  runner.py              # BenchmarkRunner — one deep interface
  types.py               # CaseResult / TrackReport / SuiteReport
  metrics.py             # SQL normalize, result/soft match, latency stats
  pipeline_factory.py    # Fake generators + commerce SQLite fixture
  fixtures/              # commerce_schema.sql + seed
  data/*.jsonl           # track cases
  tracks/                # per-track executors
  comparative.py         # optional competitor adapter scaffold (stubs only)
```

`BenchmarkRunner.run(tracks)` loads JSONL, builds `SecureQueryPipeline` with `FakeSQLGenerator` / `FakeIntentGenerator`, executes cases, and returns a `SuiteReport`.

## Extending cases

Append one JSON object per line to the track file:

**Correctness** (`data/correctness.jsonl`):

```json
{
  "id": "c900",
  "difficulty": "medium",
  "question": "list VIP customers",
  "expected_sql": "SELECT id, name FROM customers WHERE is_vip = 1",
  "generated_sql": "SELECT id, name FROM customers WHERE is_vip = 1",
  "mode": "free_form",
  "primary_metric": "result",
  "ordered": false,
  "tags": ["filter"]
}
```

Intent mode: set `"mode": "intent"` and provide an `"intent"` object matching `QueryIntent` fields (`query_type`, `tables`, `columns`, `conditions`, …). The expected SQL must match `render_sql` output for exact match; result match uses golden `expected_sql` execution.

**Security** (`data/security.jsonl`):

```json
{"id": "sec-my-case", "category": "stacked_queries", "sql": "SELECT 1; DROP TABLE customers", "question": "…"}
```

**Policy** (`data/policy.jsonl`): set `expect_success`, optional `enable_access_control` + `table_permissions` + `user_id`, `mode` (`read`/`write`), `allow_multi_statement`, `repair_sql` / `repair_budget`.

## Offline vs live LLM

| Mode | How | CI |
|---|---|---|
| **Offline (default)** | `FakeSQLGenerator` / `FakeIntentGenerator` + fixture SQL | Required |
| **Live LLM** | Not wired into this runner. Gate any future path with `COGNIDB_BENCH_LIVE=1` and never require API keys for default CI. | Optional, local only |

## What this suite does **not** claim

- **Not** a leaderboard win vs Vanna, Google text-to-SQL, or other systems. No comparative numbers are published here.
- `comparative.py` is a **stub seam** for future shared-protocol adapters. Offline stubs do not score competitors.
- Pattern-based security is **fail-closed heuristics**, not a proof of absence of all SQLi (see `docs/threat-model.md`).
- Correctness offline scores measure **pipeline + policy + fixture execution** with canned generation — not live model accuracy.

## Domain language

Uses glossary terms from `CONTEXT.md`: natural-language question, generated statement, statement policy, read/write mode, caller identity, table/column allowlist, free-form vs intent generation, repair attempt, schema linking.
