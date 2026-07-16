"""Track B — security stress: adversarial SQL must fail closed in read mode."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from cognidb.security import StatementMode, StatementPolicy

from benchmarks.pipeline_factory import load_commerce_driver, make_pipeline
from benchmarks.runner import load_jsonl
from benchmarks.types import CaseResult, TrackReport, score_of


def run_security_track(
    path: Path,
    *,
    limit: Optional[int] = None,
    seed: int = 42,
) -> TrackReport:
    del seed
    cases = load_jsonl(path, limit=limit)
    driver = load_commerce_driver()
    results: List[CaseResult] = []
    false_accepts = 0

    try:
        for case in cases:
            cid = case["id"]
            sql = case["sql"]
            category = case.get("category", "unknown")
            # Prefer sql_override path — same enforcement as generator output
            pipe = make_pipeline(
                driver=driver,
                sql="SELECT id FROM customers LIMIT 1",
                policy=StatementPolicy(mode=StatementMode.READ),
                repair_budget=0,
            )
            out = pipe.run(
                case.get("question") or f"security case {cid}",
                sql_override=sql,
            )
            rejected = not out.success
            if not rejected:
                false_accepts += 1
            results.append(
                CaseResult(
                    id=cid,
                    track="security",
                    passed=rejected,
                    detail=(
                        "correctly rejected"
                        if rejected
                        else f"FALSE ACCEPT sql={sql!r}"
                    ),
                    meta={
                        "category": category,
                        "false_accept": not rejected,
                        "error": out.error,
                        "sql": sql,
                    },
                )
            )
    finally:
        driver.disconnect()

    passed_n = sum(1 for r in results if r.passed)
    total = len(results)
    return TrackReport(
        name="security",
        total=total,
        passed=passed_n,
        failed=total - passed_n,
        score=score_of(passed_n, total),
        cases=results,
        extras={
            "false_accepts": false_accepts,
            "reject_rate": score_of(passed_n, total),
        },
    )
