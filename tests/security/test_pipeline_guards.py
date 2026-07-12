"""Pipeline security locality tests — no live LLM required."""

from cognidb.pipeline.secure_query import SecureQueryPipeline, QueryResult
from cognidb.security import QuerySecurityValidator, InputSanitizer


class _FakeGen:
    def __init__(self, sql: str):
        self.sql = sql

    def generate_sql(self, natural_language, schema, examples=None):
        return self.sql

    def explain_query(self, sql, schema):
        return "ok"


class _FakeDriver:
    def __init__(self):
        self.calls = []

    def execute_native_query(self, query, params=None):
        self.calls.append(query)
        return [{"n": 1}]


def _pipe(sql: str) -> SecureQueryPipeline:
    return SecureQueryPipeline(
        driver=_FakeDriver(),
        generator=_FakeGen(sql),
        validator=QuerySecurityValidator(),
        sanitizer=InputSanitizer(),
        schema={"users": {"columns": {"id": {"type": "int"}}}},
        enable_audit=False,
    )


def test_blocks_drop():
    r = _pipe("DROP TABLE users").run("destroy users")
    assert r.success is False
    assert any(x in (r.error or "") for x in ("Security validation", "Forbidden", "DROP", "not allowed"))


def test_blocks_multi_statement():
    r = _pipe("SELECT 1; DROP TABLE users").run("two statements")
    assert r.success is False
    assert "Multiple" in (r.error or "") or "multi" in (r.error or "").lower()


def test_allows_select_and_executes_once():
    pipe = _pipe("SELECT id FROM users")
    r = pipe.run("list users")
    assert r.success is True
    assert r.sql == "SELECT id FROM users"
    assert r.row_count == 1
    assert len(pipe.driver.calls) == 1


def test_result_to_dict_shape():
    r = QueryResult(success=True, query="q", sql="SELECT 1", results=[{"a": 1}], row_count=1)
    d = r.to_dict()
    assert d["success"] is True
    assert d["row_count"] == 1
