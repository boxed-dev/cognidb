"""BenchmarkRunner — small deep interface over multi-track offline suites."""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from benchmarks.types import SuiteReport, TrackReport, score_of

TRACKS = ("correctness", "security", "policy", "robustness")
DATA_DIR = Path(__file__).resolve().parent / "data"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"


class BenchmarkRunner:
    """
    Deep module: one call runs selected tracks and returns a SuiteReport.

    Offline by default (FakeSQLGenerator / FakeIntentGenerator + fixture DB).
    Live LLM path is gated externally; this runner never opens the network.
    """

    def __init__(
        self,
        *,
        data_dir: Path | None = None,
        smoke: bool = False,
        smoke_limit: int = 5,
        seed: int = 42,
    ):
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self.smoke = smoke
        self.smoke_limit = smoke_limit
        self.seed = seed

    def run(self, tracks: Sequence[str] = TRACKS) -> SuiteReport:
        # Late imports avoid circular deps with track modules
        from benchmarks.tracks.correctness import run_correctness_track
        from benchmarks.tracks.policy import run_policy_track
        from benchmarks.tracks.robustness import run_robustness_track
        from benchmarks.tracks.security import run_security_track

        selected = self._normalize_tracks(tracks)
        started = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()
        reports: dict[str, TrackReport] = {}
        limit = self.smoke_limit if self.smoke else None

        dispatch = {
            "correctness": lambda: run_correctness_track(
                self.data_dir / "correctness.jsonl",
                limit=limit,
                seed=self.seed,
            ),
            "security": lambda: run_security_track(
                self.data_dir / "security.jsonl",
                limit=limit,
                seed=self.seed,
            ),
            "policy": lambda: run_policy_track(
                self.data_dir / "policy.jsonl",
                limit=limit,
                seed=self.seed,
            ),
            "robustness": lambda: run_robustness_track(
                self.data_dir / "robustness.jsonl",
                limit=limit,
                seed=self.seed,
            ),
        }

        for name in selected:
            reports[name] = dispatch[name]()

        finished_at = datetime.now(timezone.utc).isoformat()
        duration_ms = (time.perf_counter() - started) * 1000
        return SuiteReport(
            tracks=reports,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=round(duration_ms, 3),
            offline=True,
            live_llm=False,
        )

    def write_report(
        self,
        report: SuiteReport,
        *,
        reports_dir: Path | None = None,
        prefix: str = "report",
    ) -> Path:
        out_dir = Path(reports_dir) if reports_dir else REPORTS_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = out_dir / f"{prefix}_{stamp}.json"
        payload = json.dumps(report.to_dict(), indent=2, default=str) + "\n"
        path.write_text(payload, encoding="utf-8")
        latest = out_dir / f"{prefix}_latest.json"
        latest.write_text(payload, encoding="utf-8")
        return path

    @staticmethod
    def _normalize_tracks(tracks: Sequence[str]) -> list[str]:
        if not tracks or "all" in tracks:
            return list(TRACKS)
        out: list[str] = []
        for t in tracks:
            t = t.strip().lower()
            if t == "all":
                return list(TRACKS)
            if t not in TRACKS:
                raise ValueError(f"Unknown track {t!r}; choose from {TRACKS} or all")
            if t not in out:
                out.append(t)
        return out


def load_jsonl(path: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rows.append(json.loads(line))
        if limit is not None and len(rows) >= limit:
            break
    return rows


# Re-export for convenience / tests
__all__ = [
    "TRACKS",
    "DATA_DIR",
    "REPORTS_DIR",
    "BenchmarkRunner",
    "load_jsonl",
    "score_of",
    "SuiteReport",
    "TrackReport",
]
