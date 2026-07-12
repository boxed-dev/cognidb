"""Offline intent-mode E2E: FakeIntentGenerator → render_sql → SQLite (Epic 1 done criteria)."""

from cognidb.ai.fake_generator import FakeIntentGenerator
from cognidb.core.query_intent import Column, QueryIntent, QueryType
from cognidb.pipeline.secure_query import SecureQueryPipeline
from cognidb.security import InputSanitizer, QuerySecurityValidator, StatementPolicy


def test_intent_mode_end_to_end_sqlite(memory_sqlite, sample_schema):
    intent = QueryIntent(
        query_type=QueryType.SELECT,
        tables=["users"],
        columns=[Column("id"), Column("name")],
    )
    pipe = SecureQueryPipeline(
        driver=memory_sqlite,
        generator=FakeIntentGenerator(intent),
        validator=QuerySecurityValidator(allowed_operations=["SELECT"]),
        sanitizer=InputSanitizer(),
        schema=sample_schema,
        enable_audit=False,
        policy=StatementPolicy(),
        generation_mode="intent",
        repair_budget=0,
    )
    result = pipe.run("show users")
    assert result.success is True
    assert result.sql == "SELECT id, name FROM users"
    assert result.row_count >= 1
    assert result.results[0]["name"] == "Ada"
