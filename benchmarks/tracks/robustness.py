"""Track D — robustness / soak / schema linking / offline latency."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from benchmarks.metrics import latency_stats
from benchmarks.pipeline_factory import load_commerce_driver, make_pipeline
from benchmarks.runner import load_jsonl
from benchmarks.types import CaseResult, TrackReport, score_of
from cognidb.schema.linking import link_schema
from cognidb.security import StatementMode, StatementPolicy


def _large_schema(n_tables: int) -> dict[str, Any]:
    schema: dict[str, Any] = {}
    for i in range(n_tables):
        name = f"entity_{i:03d}"
        schema[name] = {
            "id": "INTEGER",
            "name": "TEXT",
            f"attr_{i % 7}": "TEXT",
            "created_at": "TEXT",
        }
    # Include realistic names so linking can hit
    schema["customers"] = {"id": "INTEGER", "name": "TEXT", "email": "TEXT"}
    schema["orders"] = {"id": "INTEGER", "customer_id": "INTEGER", "total": "REAL"}
    return schema


def run_robustness_track(
    path: Path,
    *,
    limit: int | None = None,
    seed: int = 42,
) -> TrackReport:
    del seed
    cases = load_jsonl(path, limit=limit)
    driver = load_commerce_driver()
    results: list[CaseResult] = []
    latencies: list[float] = []

    try:
        for case in cases:
            cid = case["id"]
            kind = case.get("kind", "pipeline")
            try:
                if kind == "schema_link":
                    n = int(case.get("n_tables", 80))
                    max_tables = int(case.get("max_schema_tables", 40))
                    top_k = int(case.get("schema_top_k", 8))
                    question = case.get("question") or "list customers and orders"
                    schema = _large_schema(n)
                    ctx, strategy = link_schema(
                        question,
                        schema,
                        top_k=top_k,
                        max_tables=max_tables,
                        enable=True,
                    )
                    expect_strategy = case.get("expect_strategy")
                    expect_max = case.get("expect_max_tables")
                    ok = True
                    detail = f"strategy={strategy} tables={len(ctx)}"
                    if expect_strategy and strategy != expect_strategy:
                        # linked is fine when tokens hit; full_truncated when not
                        if expect_strategy == "linked_or_truncated":
                            ok = strategy in ("linked", "full_truncated", "full")
                        else:
                            ok = strategy == expect_strategy
                    if expect_max is not None and len(ctx) > int(expect_max):
                        ok = False
                        detail += f" exceeds max {expect_max}"
                    # Fail-closed size bound
                    if len(ctx) > max_tables:
                        ok = False
                        detail += " overstuffed schema"
                    results.append(
                        CaseResult(
                            id=cid,
                            track="robustness",
                            passed=ok,
                            detail=detail,
                            meta={
                                "kind": kind,
                                "strategy": strategy,
                                "n_context_tables": len(ctx),
                            },
                        )
                    )
                    continue

                if kind == "soak":
                    n_runs = int(case.get("n_runs", 25))
                    sql = case.get("sql") or "SELECT id, name FROM customers ORDER BY id"
                    pipe = make_pipeline(
                        driver=driver,
                        sql=sql,
                        policy=StatementPolicy(mode=StatementMode.READ),
                        repair_budget=0,
                    )
                    ok = True
                    last_err = ""
                    for i in range(n_runs):
                        t0 = time.perf_counter()
                        out = pipe.run(f"soak run {i}")
                        latencies.append((time.perf_counter() - t0) * 1000)
                        if not out.success:
                            ok = False
                            last_err = out.error or "failed"
                            break
                    results.append(
                        CaseResult(
                            id=cid,
                            track="robustness",
                            passed=ok,
                            detail=f"n_runs={n_runs}" + (f" err={last_err}" if last_err else ""),
                            meta={"kind": kind, "n_runs": n_runs},
                        )
                    )
                    continue

                # default: single pipeline latency probe
                sql = case.get("sql") or "SELECT COUNT(*) AS n FROM orders"
                pipe = make_pipeline(
                    driver=driver,
                    sql=sql,
                    policy=StatementPolicy(mode=StatementMode.READ),
                    repair_budget=0,
                    max_schema_tables=int(case.get("max_schema_tables", 40)),
                )
                t0 = time.perf_counter()
                out = pipe.run(case.get("question") or "robustness probe")
                elapsed = (time.perf_counter() - t0) * 1000
                latencies.append(elapsed)
                expect_success = case.get("expect_success", True)
                ok = out.success is bool(expect_success)
                results.append(
                    CaseResult(
                        id=cid,
                        track="robustness",
                        passed=ok,
                        detail=f"success={out.success} ms={elapsed:.3f}",
                        meta={
                            "kind": kind,
                            "latency_ms": elapsed,
                            "error": out.error,
                        },
                    )
                )
            except Exception as e:
                results.append(
                    CaseResult(
                        id=cid,
                        track="robustness",
                        passed=False,
                        detail=f"exception: {e}",
                        meta={"kind": kind},
                    )
                )
    finally:
        driver.disconnect()

    passed_n = sum(1 for r in results if r.passed)
    total = len(results)
    return TrackReport(
        name="robustness",
        total=total,
        passed=passed_n,
        failed=total - passed_n,
        score=score_of(passed_n, total),
        cases=results,
        extras={"latency": latency_stats(latencies)},
    )
