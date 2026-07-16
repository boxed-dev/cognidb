"""CLI entry: ``python -m benchmarks.run`` / ``python -m benchmarks``."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import List, Optional, Sequence

from benchmarks.runner import TRACKS, BenchmarkRunner
from benchmarks.types import SuiteReport


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m benchmarks.run",
        description=(
            "CogniDB offline benchmark suite — correctness, security, "
            "policy, and robustness against SecureQueryPipeline."
        ),
    )
    p.add_argument(
        "--track",
        action="append",
        dest="tracks",
        default=None,
        help="Track to run: all|correctness|security|policy|robustness (repeatable)",
    )
    p.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text)",
    )
    p.add_argument(
        "--fail-under",
        type=float,
        default=None,
        metavar="RATE",
        help="Exit non-zero if overall score is below RATE (0.0–1.0)",
    )
    p.add_argument(
        "--smoke",
        action="store_true",
        help="Run a small subset of each selected track (CI-friendly)",
    )
    p.add_argument(
        "--smoke-limit",
        type=int,
        default=5,
        help="Cases per track in smoke mode (default: 5)",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic seed (reserved for sampling; fixtures are fixed)",
    )
    p.add_argument(
        "--no-report-file",
        action="store_true",
        help="Do not write JSON under benchmarks/reports/",
    )
    p.add_argument(
        "--report-prefix",
        default="report",
        help="Filename prefix for report JSON (default: report)",
    )
    return p


def _resolve_tracks(raw: Optional[Sequence[str]]) -> List[str]:
    if not raw:
        return ["all"]
    return list(raw)


def main(argv: Optional[Sequence[str]] = None) -> int:
    logging.basicConfig(level=logging.WARNING)
    # Expected fail-path noise (bad repair SQL, rejected statements) is not a suite signal.
    logging.getLogger("cognidb").setLevel(logging.CRITICAL)

    # Live LLM path is explicitly gated and never required.
    if os.environ.get("COGNIDB_BENCH_LIVE", "").strip() in {"1", "true", "yes"}:
        print(
            "NOTE: COGNIDB_BENCH_LIVE is set, but this suite runs offline "
            "generators only. Live comparison is not implemented in CI.",
            file=sys.stderr,
        )

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    tracks = _resolve_tracks(args.tracks)

    runner = BenchmarkRunner(
        smoke=args.smoke,
        smoke_limit=args.smoke_limit,
        seed=args.seed,
    )
    try:
        report = runner.run(tracks)
    except Exception as e:
        print(f"benchmark failed to start: {e}", file=sys.stderr)
        return 2

    report_path = None
    if not args.no_report_file:
        report_path = runner.write_report(report, prefix=args.report_prefix)

    if args.format == "json":
        payload = report.to_dict()
        if report_path is not None:
            payload["report_path"] = str(report_path)
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(report.summary_text())
        if report_path is not None:
            print(f"  report_path={report_path}")

    # Security false accepts always fail the process hard
    hard = report.hard_failures()
    if hard:
        print(
            f"HARD FAILURE: {len(hard)} security/policy false accept(s)",
            file=sys.stderr,
        )
        return 1

    if args.fail_under is not None:
        if report.overall_score < args.fail_under:
            print(
                f"overall_score {report.overall_score:.4f} < fail-under {args.fail_under}",
                file=sys.stderr,
            )
            return 1
        # Also gate each selected track when fail-under is set
        for name, tr in report.tracks.items():
            if tr.total and tr.score < args.fail_under:
                print(
                    f"track {name} score {tr.score:.4f} < fail-under {args.fail_under}",
                    file=sys.stderr,
                )
                return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
