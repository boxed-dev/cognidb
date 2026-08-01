"""Shared report types for the benchmark harness."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CaseResult:
    id: str
    track: str
    passed: bool
    detail: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TrackReport:
    name: str
    total: int
    passed: int
    failed: int
    score: float
    cases: list[CaseResult] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "score": self.score,
            "extras": self.extras,
            "cases": [c.to_dict() for c in self.cases],
        }


@dataclass
class SuiteReport:
    tracks: dict[str, TrackReport]
    started_at: str
    finished_at: str
    duration_ms: float
    offline: bool = True
    live_llm: bool = False

    @property
    def overall_score(self) -> float:
        if not self.tracks:
            return 0.0
        scores = [t.score for t in self.tracks.values() if t.total > 0]
        if not scores:
            return 0.0
        return round(sum(scores) / len(scores), 4)

    def hard_failures(self) -> list[str]:
        msgs: list[str] = []
        for name, tr in self.tracks.items():
            if name in ("security", "policy"):
                for c in tr.cases:
                    if not c.passed and c.meta.get("false_accept"):
                        msgs.append(f"{name}:{c.id}: false accept")
        return msgs

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "offline": self.offline,
            "live_llm": self.live_llm,
            "overall_score": self.overall_score,
            "tracks": {k: v.to_dict() for k, v in self.tracks.items()},
            "hard_failures": self.hard_failures(),
        }

    def summary_text(self) -> str:
        lines = [
            "CogniDB Benchmark Suite (offline)",
            f"  overall_score={self.overall_score:.4f}  duration_ms={self.duration_ms:.1f}",
        ]
        track_order = ("correctness", "security", "policy", "robustness")
        for name in track_order:
            tr = self.tracks.get(name)
            if not tr:
                continue
            lines.append(
                f"  [{name}] score={tr.score:.4f}  "
                f"passed={tr.passed}/{tr.total}  failed={tr.failed}"
            )
            if tr.extras:
                interesting = {
                    k: v
                    for k, v in tr.extras.items()
                    if k in ("by_difficulty", "latency", "false_accepts", "reject_rate")
                }
                if interesting:
                    lines.append(
                        f"         extras={json.dumps(interesting, default=str)}"
                    )
        hard = self.hard_failures()
        if hard:
            lines.append(f"  HARD FAILURES: {len(hard)}")
            for h in hard[:10]:
                lines.append(f"    - {h}")
        failures: list[CaseResult] = []
        for tr in self.tracks.values():
            failures.extend(c for c in tr.cases if not c.passed)
        if failures:
            lines.append("  sample failures:")
            for c in failures[:8]:
                lines.append(f"    - {c.track}/{c.id}: {c.detail[:160]}")
        return "\n".join(lines)


def score_of(passed: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(passed / total, 4)
