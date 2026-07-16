"""Optional competitor comparison scaffold (offline stubs only).

This module does **not** claim wins against Vanna, Google SQL generation, or
other systems. Live competitor runs require external packages, API keys, and
shared evaluation protocols that are out of scope for the offline CI suite.

Enable exploratory work with COGNIDB_BENCH_LIVE=1 after implementing adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol


class TextToSQLSystem(Protocol):
    """Minimal adapter interface for comparative harnesses."""

    name: str

    def generate_sql(self, question: str, schema: Dict[str, Any]) -> str: ...


@dataclass
class ComparativeCase:
    id: str
    question: str
    expected_sql: str
    schema: Dict[str, Any]


@dataclass
class ComparativeResult:
    system: str
    case_id: str
    sql: str
    notes: str = ""


class OfflineStubSystem:
    """Deterministic stub that returns empty SQL — documents the seam only."""

    name = "offline_stub"

    def generate_sql(self, question: str, schema: Dict[str, Any]) -> str:
        del question, schema
        return ""


def run_comparative_stub(
    cases: List[ComparativeCase],
    systems: Optional[List[TextToSQLSystem]] = None,
) -> List[ComparativeResult]:
    """Run offline stubs; does not score competitors."""
    systems = systems or [OfflineStubSystem()]
    out: List[ComparativeResult] = []
    for system in systems:
        for case in cases:
            sql = system.generate_sql(case.question, case.schema)
            out.append(
                ComparativeResult(
                    system=system.name,
                    case_id=case.id,
                    sql=sql,
                    notes="stub only — no comparative claim",
                )
            )
    return out
