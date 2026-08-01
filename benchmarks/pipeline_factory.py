"""Build SecureQueryPipeline instances for offline benchmark tracks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cognidb.ai.fake_generator import FakeIntentGenerator, FakeSQLGenerator
from cognidb.core.query_intent import QueryIntent
from cognidb.drivers import SQLiteDriver
from cognidb.pipeline import SecureQueryPipeline
from cognidb.security import (
    AccessController,
    InputSanitizer,
    QuerySecurityValidator,
    StatementMode,
    StatementPolicy,
)

FIXURES_DIR = Path(__file__).resolve().parent / "fixtures"
SCHEMA_SQL = FIXURES_DIR / "commerce_schema.sql"
SEED_SQL = FIXURES_DIR / "commerce_seed.sql"


def _split_sql_script(script: str) -> list[str]:
    """Split fixture SQL on semicolons outside of simple string literals."""
    statements: list[str] = []
    buf: list[str] = []
    in_single = False
    i = 0
    while i < len(script):
        ch = script[i]
        if ch == "'" and not in_single:
            in_single = True
            buf.append(ch)
        elif ch == "'" and in_single:
            # escaped '' inside string
            if i + 1 < len(script) and script[i + 1] == "'":
                buf.append("''")
                i += 2
                continue
            in_single = False
            buf.append(ch)
        elif ch == ";" and not in_single:
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
        else:
            buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def load_commerce_driver(
    *,
    database: str = ":memory:",
    max_result_size: int = 10_000,
) -> SQLiteDriver:
    """Create a connected SQLite driver with the commerce fixture loaded."""
    drv = SQLiteDriver({"database": database, "max_result_size": max_result_size})
    drv.connect()
    schema_sql = SCHEMA_SQL.read_text(encoding="utf-8")
    seed_sql = SEED_SQL.read_text(encoding="utf-8")
    for stmt in _split_sql_script(schema_sql) + _split_sql_script(seed_sql):
        drv.execute_native_query(stmt)
    return drv


def make_pipeline(
    *,
    driver: SQLiteDriver,
    sql: str | None = None,
    repair_sql: str | None = None,
    intent: QueryIntent | None = None,
    generation_mode: str = "free_form",
    policy: StatementPolicy | None = None,
    access_controller: AccessController | None = None,
    enable_access_control: bool = False,
    enable_schema_linking: bool = True,
    schema_top_k: int = 8,
    max_schema_tables: int = 40,
    repair_budget: int = 1,
    schema: dict[str, Any] | None = None,
    enable_audit: bool = False,
) -> SecureQueryPipeline:
    """Construct a pipeline with FakeSQLGenerator / FakeIntentGenerator."""
    if generation_mode == "intent":
        if intent is None:
            raise ValueError("intent generation_mode requires an intent object")
        generator: Any = FakeIntentGenerator(intent)
    else:
        generator = FakeSQLGenerator(sql or "SELECT 1", repair_sql=repair_sql)

    return SecureQueryPipeline(
        driver=driver,
        generator=generator,
        validator=QuerySecurityValidator(),
        sanitizer=InputSanitizer(),
        schema=schema if schema is not None else driver.fetch_schema(),
        access_controller=access_controller,
        enable_access_control=enable_access_control,
        policy=policy or StatementPolicy(mode=StatementMode.READ),
        enable_schema_linking=enable_schema_linking,
        schema_top_k=schema_top_k,
        max_schema_tables=max_schema_tables,
        repair_budget=repair_budget,
        generation_mode=generation_mode,
        allow_dangerous_sql=True,
        enable_audit=enable_audit,
    )


def make_access_controller(
    user_id: str,
    table_permissions: dict[str, dict[str, Any]],
) -> AccessController:
    ac = AccessController()
    ac.create_restricted_user(user_id, table_permissions)
    return ac
