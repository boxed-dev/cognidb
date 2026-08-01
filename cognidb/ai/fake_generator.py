"""Deterministic SQL / intent generators for offline tests (no network)."""

from __future__ import annotations

from typing import Any

from ..core.query_intent import QueryIntent


class FakeSQLGenerator:
    """Returns canned SQL; supports a simple repair rewrite."""

    def __init__(self, sql: str, *, repair_sql: str | None = None):
        self.sql = sql
        self.repair_sql = repair_sql
        self.calls = 0
        self.repair_calls = 0

    def generate_sql(
        self, natural_language: str, schema: dict[str, Any], examples: Any = None
    ) -> str:
        self.calls += 1
        return self.sql

    def explain_query(self, sql: str, schema: dict[str, Any]) -> str:
        return f"Fake explanation for: {sql}"

    def repair_sql_with_error(
        self, sql: str, error: str, schema: dict[str, Any]
    ) -> str:
        self.repair_calls += 1
        return self.repair_sql if self.repair_sql is not None else sql


class FakeIntentGenerator:
    """Returns a canned QueryIntent for generation_mode='intent' tests."""

    def __init__(self, intent: QueryIntent):
        self.intent = intent
        self.calls = 0

    def generate_intent(
        self, natural_language: str, schema: dict[str, Any], examples: Any = None
    ) -> QueryIntent:
        self.calls += 1
        return self.intent

    def generate_sql(
        self, natural_language: str, schema: dict[str, Any], examples: Any = None
    ) -> str:
        # Free-form path should not be used in intent mode; keep for Protocol compat
        raise RuntimeError("FakeIntentGenerator does not produce free-form SQL")

    def explain_query(self, sql: str, schema: dict[str, Any]) -> str:
        return f"Fake explanation for: {sql}"
