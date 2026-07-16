"""Track C — policy / access-control stress (allowlists, write opt-in, repair)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from cognidb.security import StatementMode, StatementPolicy

from benchmarks.pipeline_factory import (
    load_commerce_driver,
    make_access_controller,
    make_pipeline,
)
from benchmarks.runner import load_jsonl
from benchmarks.types import CaseResult, TrackReport, score_of


def _policy_from_case(case: Dict[str, Any]) -> StatementPolicy:
    mode = (case.get("mode") or "read").lower()
    allow_multi = bool(case.get("allow_multi_statement", False))
    sm = StatementMode.WRITE if mode == "write" else StatementMode.READ
    return StatementPolicy(mode=sm, allow_multi_statement=allow_multi)


def run_policy_track(
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
            expect_success = bool(case.get("expect_success", False))
            sql = case.get("sql") or case.get("generated_sql")
            repair_sql = case.get("repair_sql")
            question = case.get("question") or f"policy case {cid}"
            user_id = case.get("user_id")
            enable_ac = bool(case.get("enable_access_control", False))
            ac = None
            if enable_ac and case.get("table_permissions"):
                ac = make_access_controller(
                    user_id or "bench_user",
                    case["table_permissions"],
                )

            policy = _policy_from_case(case)
            repair_budget = int(case.get("repair_budget", 0))

            pipe = make_pipeline(
                driver=driver,
                sql=sql,
                repair_sql=repair_sql,
                policy=policy,
                access_controller=ac,
                enable_access_control=enable_ac,
                repair_budget=repair_budget,
            )

            use_override = bool(case.get("sql_override", False))
            kwargs: Dict[str, Any] = {}
            if user_id:
                kwargs["user_id"] = user_id
            if use_override:
                kwargs["sql_override"] = sql

            out = pipe.run(question, **kwargs)
            ok = out.success is expect_success
            if expect_success is False and out.success:
                false_accepts += 1

            detail = (
                f"expect_success={expect_success} got_success={out.success}"
            )
            if out.error:
                detail += f" error={out.error[:120]}"
            if out.repaired:
                detail += " repaired=True"
            if case.get("expect_repaired") is not None:
                if bool(out.repaired) != bool(case["expect_repaired"]):
                    ok = False
                    detail += (
                        f" | repaired mismatch expect={case['expect_repaired']}"
                    )

            results.append(
                CaseResult(
                    id=cid,
                    track="policy",
                    passed=ok,
                    detail=detail,
                    meta={
                        "false_accept": expect_success is False and out.success,
                        "expect_success": expect_success,
                        "got_success": out.success,
                        "category": case.get("category", "policy"),
                        "sql": sql,
                        "error": out.error,
                        "repaired": out.repaired,
                    },
                )
            )
    finally:
        driver.disconnect()

    passed_n = sum(1 for r in results if r.passed)
    total = len(results)
    return TrackReport(
        name="policy",
        total=total,
        passed=passed_n,
        failed=total - passed_n,
        score=score_of(passed_n, total),
        cases=results,
        extras={
            "false_accepts": false_accepts,
            "reject_rate": score_of(
                sum(1 for r in results if r.meta.get("expect_success") is False and r.passed),
                max(1, sum(1 for r in results if r.meta.get("expect_success") is False)),
            ),
        },
    )
