"""QueryGenerator.generate_intent: NL → LLM JSON → validated QueryIntent."""

from __future__ import annotations

import pytest

from cognidb.ai.query_generator import QueryGenerator
from cognidb.core.exceptions import TranslationError
from cognidb.core.query_intent import ComparisonOperator, QueryType

SCHEMA = {"users": {"id": "INTEGER", "name": "TEXT"}}


class _FakeResponse:
    def __init__(self, content: str):
        self.content = content


class _FakeLLM:
    """Records the prompt and returns a canned response — no network."""

    def __init__(self, content: str):
        self.content = content
        self.last_prompt: str | None = None

    def generate(self, prompt: str, **kwargs):
        self.last_prompt = prompt
        return _FakeResponse(self.content)


def _gen(content: str) -> tuple[QueryGenerator, _FakeLLM]:
    llm = _FakeLLM(content)
    return QueryGenerator(llm, database_type="sqlite"), llm


def test_generate_intent_parses_json():
    gen, llm = _gen(
        '{"query_type": "SELECT", "tables": ["users"], '
        '"columns": ["id", "name"], '
        '"conditions": {"conditions": [{"column": "name", "operator": "=", "value": "Ada"}]}}'
    )
    intent = gen.generate_intent("find Ada", SCHEMA)

    assert intent.query_type is QueryType.SELECT
    assert intent.tables == ["users"]
    assert [c.name for c in intent.columns] == ["id", "name"]
    cond = intent.conditions.conditions[0]
    assert cond.operator is ComparisonOperator.EQ
    assert cond.value == "Ada"
    # prompt was schema-aware
    assert "users" in llm.last_prompt
    assert "find Ada" in llm.last_prompt


def test_generate_intent_tolerates_code_fence():
    gen, _ = _gen('```json\n{"query_type": "SELECT", "tables": ["users"]}\n```')
    intent = gen.generate_intent("everyone", SCHEMA)
    assert intent.tables == ["users"]


def test_generate_intent_wraps_bad_json():
    gen, _ = _gen("sorry, I cannot help with that")
    with pytest.raises(TranslationError):
        gen.generate_intent("find Ada", SCHEMA)


def test_generate_intent_rejects_write_type():
    gen, _ = _gen('{"query_type": "DELETE", "tables": ["users"]}')
    with pytest.raises(TranslationError):
        gen.generate_intent("delete users", SCHEMA)
