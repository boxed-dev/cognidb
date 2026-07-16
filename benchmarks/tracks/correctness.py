"""Track A — curated NL→SQL correctness (execution-primary metrics)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from cognidb.core.query_intent import (
    Aggregation,
    AggregateFunction,
    Column,
    ComparisonOperator,
    Condition,
    ConditionGroup,
    JoinCondition,
    JoinType,
    LogicalOperator,
    OrderBy,
    QueryIntent,
    QueryType,
)

from benchmarks.metrics import exact_sql_match, result_match, soft_match
from benchmarks.pipeline_factory import load_commerce_driver, make_pipeline
from benchmarks.runner import load_jsonl
from benchmarks.types import CaseResult, TrackReport, score_of


def _intent_from_dict(raw: Optional[Dict[str, Any]]) -> Optional[QueryIntent]:
    if not raw:
        return None
    qtype = QueryType[raw.get("query_type", "SELECT")]
    columns = [
        Column(c["name"], table=c.get("table"), alias=c.get("alias"))
        for c in raw.get("columns") or []
    ]
    conditions = None
    if raw.get("conditions"):
        conds = []
        for c in raw["conditions"]:
            conds.append(
                Condition(
                    Column(c["column"], table=c.get("table")),
                    ComparisonOperator[c["op"]],
                    c.get("value"),
                )
            )
        conditions = ConditionGroup(conds, LogicalOperator.AND)
    joins = []
    for j in raw.get("joins") or []:
        joins.append(
            JoinCondition(
                join_type=JoinType[j.get("type", "INNER")],
                left_table=j["left_table"],
                right_table=j["right_table"],
                left_column=j["left_column"],
                right_column=j["right_column"],
            )
        )
    aggregations = []
    for a in raw.get("aggregations") or []:
        aggregations.append(
            Aggregation(
                function=AggregateFunction[a["function"]],
                column=Column(a["column"], table=a.get("table")),
                alias=a.get("alias"),
            )
        )
    group_by = [
        Column(g["name"], table=g.get("table")) for g in raw.get("group_by") or []
    ]
    order_by = [
        OrderBy(
            Column(o["name"], table=o.get("table")),
            ascending=o.get("ascending", True),
        )
        for o in raw.get("order_by") or []
    ]
    return QueryIntent(
        query_type=qtype,
        tables=list(raw.get("tables") or []),
        columns=columns,
        conditions=conditions,
        joins=joins,
        aggregations=aggregations,
        group_by=group_by,
        order_by=order_by,
        limit=raw.get("limit"),
        offset=raw.get("offset"),
        distinct=bool(raw.get("distinct", False)),
        values=raw.get("values"),
    )


def run_correctness_track(
    path: Path,
    *,
    limit: Optional[int] = None,
    seed: int = 42,
) -> TrackReport:
    del seed  # deterministic fixtures; reserved for future sampling
    cases = load_jsonl(path, limit=limit)
    driver = load_commerce_driver()
    results: List[CaseResult] = []
    by_diff: Counter = Counter()
    by_diff_pass: Counter = Counter()

    try:
        for case in cases:
            cid = case["id"]
            difficulty = case.get("difficulty", "medium")
            by_diff[difficulty] += 1
            expected_sql = case["expected_sql"]
            question = case.get("question") or case.get("nl") or cid
            mode = (case.get("mode") or "free_form").lower()
            primary = (case.get("primary_metric") or "result").lower()
            ordered = bool(case.get("ordered", False))

            # Golden rows from expected SQL via driver (bypass pipeline)
            try:
                golden = driver.execute_native_query(expected_sql)
            except Exception as e:
                results.append(
                    CaseResult(
                        id=cid,
                        track="correctness",
                        passed=False,
                        detail=f"golden SQL failed: {e}",
                        meta={"difficulty": difficulty},
                    )
                )
                continue

            intent = _intent_from_dict(case.get("intent"))
            gen_sql = case.get("generated_sql") or expected_sql

            try:
                if mode == "intent":
                    pipe = make_pipeline(
                        driver=driver,
                        intent=intent,
                        generation_mode="intent",
                        repair_budget=0,
                    )
                else:
                    pipe = make_pipeline(
                        driver=driver,
                        sql=gen_sql,
                        generation_mode="free_form",
                        repair_budget=0,
                    )
                out = pipe.run(question)
            except Exception as e:
                results.append(
                    CaseResult(
                        id=cid,
                        track="correctness",
                        passed=False,
                        detail=f"pipeline exception: {e}",
                        meta={"difficulty": difficulty},
                    )
                )
                continue

            if not out.success:
                results.append(
                    CaseResult(
                        id=cid,
                        track="correctness",
                        passed=False,
                        detail=f"pipeline failed: {out.error}",
                        meta={
                            "difficulty": difficulty,
                            "sql": out.sql,
                            "expected_sql": expected_sql,
                        },
                    )
                )
                continue

            actual_sql = out.sql or ""
            exact = exact_sql_match(expected_sql, actual_sql)
            res_ok = result_match(golden, out.results, ordered=ordered)
            soft = soft_match(expected_sql, actual_sql)

            if primary == "exact":
                passed = exact
            elif primary == "soft":
                passed = soft or res_ok
            else:
                # result is preferred primary
                passed = res_ok

            if passed:
                by_diff_pass[difficulty] += 1

            detail = (
                f"primary={primary} result={res_ok} exact={exact} soft={soft}"
            )
            if not passed:
                detail += (
                    f" | expected_sql={expected_sql!r} got={actual_sql!r}"
                    f" | expected_rows={len(golden)} got_rows={out.row_count}"
                )

            results.append(
                CaseResult(
                    id=cid,
                    track="correctness",
                    passed=passed,
                    detail=detail,
                    meta={
                        "difficulty": difficulty,
                        "primary_metric": primary,
                        "result_match": res_ok,
                        "exact_match": exact,
                        "soft_match": soft,
                        "mode": mode,
                        "expected_sql": expected_sql,
                        "got_sql": actual_sql,
                    },
                )
            )
    finally:
        driver.disconnect()

    passed_n = sum(1 for r in results if r.passed)
    total = len(results)
    by_difficulty = {
        d: {
            "total": by_diff[d],
            "passed": by_diff_pass[d],
            "score": score_of(by_diff_pass[d], by_diff[d]),
        }
        for d in sorted(by_diff.keys())
    }
    return TrackReport(
        name="correctness",
        total=total,
        passed=passed_n,
        failed=total - passed_n,
        score=score_of(passed_n, total),
        cases=results,
        extras={"by_difficulty": by_difficulty},
    )
