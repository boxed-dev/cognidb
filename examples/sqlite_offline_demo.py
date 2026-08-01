"""Offline SQLite demo — no network LLM.

Intent mode is the secure default: a QueryIntent is rendered with bound
parameters (no value is interpolated into SQL).

Run from repo root (with package installed)::

    python examples/sqlite_offline_demo.py
"""

from cognidb.ai.fake_generator import FakeIntentGenerator
from cognidb.core.query_intent import (
    Column,
    ComparisonOperator,
    Condition,
    ConditionGroup,
    QueryIntent,
    QueryType,
)
from cognidb.drivers import SQLiteDriver
from cognidb.pipeline import SecureQueryPipeline
from cognidb.security import InputSanitizer, QuerySecurityValidator


def main() -> None:
    drv = SQLiteDriver({"database": ":memory:"})
    drv.connect()
    try:
        drv.execute_native_query(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
        )
        drv.execute_native_query("INSERT INTO users (id, name) VALUES (1, ?)", ["Ada"])

        intent = QueryIntent(
            query_type=QueryType.SELECT,
            tables=["users"],
            columns=[Column("id"), Column("name")],
            conditions=ConditionGroup(
                [Condition(Column("name"), ComparisonOperator.EQ, "Ada")]
            ),
        )

        pipe = SecureQueryPipeline(
            driver=drv,  # dialect auto-inferred (sqlite)
            generator=FakeIntentGenerator(intent),
            validator=QuerySecurityValidator(),
            sanitizer=InputSanitizer(),
            schema=drv.fetch_schema(),
            enable_audit=False,
        )
        result = pipe.run("find Ada")
        print(result.sql)  # SELECT id, name FROM users WHERE name = ?  (value is bound)
        print(result.to_dict())
    finally:
        drv.disconnect()


if __name__ == "__main__":
    main()
