"""Secure query pipeline — deep module for NL→SQL→execute.

Enforcement is delegated to the sqlglot AST guard (`cognidb.security.sql_guard`),
which is the single source of parsing truth. The default generation mode is
``intent`` (deterministic render with bound parameters); raw free-form LLM SQL is
opt-in behind ``allow_dangerous_sql`` because it cannot be parameterized.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from ..intent import render_sql
from ..schema.linking import link_schema
from ..security import sql_guard
from ..security.sql_guard import GuardError
from ..security.statement_policy import StatementPolicy

logger = logging.getLogger(__name__)

_Params = Sequence[Any] | None


class _Driver(Protocol):
    def execute_native_query(
        self, query: str, params: _Params = None
    ) -> list[dict[str, Any]]: ...


class _Generator(Protocol):
    def generate_sql(
        self, natural_language: str, schema: dict[str, Any], examples: Any = None
    ) -> str: ...

    def explain_query(self, sql: str, schema: dict[str, Any]) -> str: ...


class _Validator(Protocol):
    allowed_operations: Any


class _Sanitizer(Protocol):
    def sanitize_natural_language(self, text: str) -> str: ...


def _acl_name(table: Any) -> str:
    """Name used for access-control matching: schema-qualified key if the table
    carries a schema/catalog, else the bare name (so `evil.users` != `users`)."""
    return table.key if (table.db or table.catalog) else table.name


def _infer_dialect(driver: Any) -> str | None:
    name = type(driver).__name__.lower()
    if "sqlite" in name:
        return "sqlite"
    if "postgres" in name or "pg" in name:
        return "postgres"
    if "mysql" in name or "maria" in name:
        return "mysql"
    return getattr(driver, "dialect", None)


@dataclass
class QueryResult:
    success: bool
    query: str
    sql: str | None = None
    results: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    explanation: str | None = None
    error: str | None = None
    execution_ms: float | None = None
    schema_strategy: str | None = None
    repaired: bool = False

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "success": self.success,
            "query": self.query,
            "sql": self.sql,
            "results": self.results,
            "row_count": self.row_count,
            "execution_time": self.execution_ms,
            "repaired": self.repaired,
            "schema_strategy": self.schema_strategy,
        }
        if self.explanation is not None:
            d["explanation"] = self.explanation
        if self.error is not None:
            d["error"] = self.error
        return d


class SecureQueryPipeline:
    """Single deep interface for safe NL2SQL execution.

    1. Sanitize NL
    2. Link schema context
    3. Generate SQL: intent → deterministic parameterized render (default), or
       free-form LLM SQL (opt-in via ``allow_dangerous_sql``)
    4. Guard: AST statement gating (single SELECT / policy ops, no DDL/admin/CTE-write)
    5. Fail-closed table/column access control
    6. Execute with bound parameters; optional single repair on failure
    7. Audit
    """

    def __init__(
        self,
        *,
        driver: _Driver,
        generator: _Generator,
        validator: _Validator,
        sanitizer: _Sanitizer,
        schema: dict[str, Any],
        dialect: str | None = None,
        access_controller: Any | None = None,
        enable_access_control: bool = False,
        few_shot_examples: Any = None,
        audit_path: str | None = None,
        enable_audit: bool = True,
        policy: StatementPolicy | None = None,
        enable_schema_linking: bool = True,
        schema_top_k: int = 8,
        max_schema_tables: int = 40,
        repair_budget: int = 1,
        generation_mode: str = "intent",
        allow_dangerous_sql: bool = False,
    ):
        self.driver = driver
        self.generator = generator
        self.validator = validator
        self.sanitizer = sanitizer
        self.schema = schema
        self.dialect = dialect or _infer_dialect(driver)
        self.access_controller = access_controller
        self.enable_access_control = enable_access_control
        self.few_shot_examples = few_shot_examples
        self.audit_path = Path(audit_path).expanduser() if audit_path else None
        self.enable_audit = enable_audit
        self.policy = policy or StatementPolicy()
        self.enable_schema_linking = enable_schema_linking
        self.schema_top_k = schema_top_k
        self.max_schema_tables = max_schema_tables
        self.repair_budget = max(0, repair_budget)
        self.allow_dangerous_sql = allow_dangerous_sql

        mode = (generation_mode or "intent").strip().lower()
        if mode not in ("free_form", "intent"):
            raise ValueError(
                f"generation_mode must be 'free_form' or 'intent', got {generation_mode!r}"
            )
        if mode == "free_form" and not allow_dangerous_sql:
            raise ValueError(
                "generation_mode='free_form' emits unparameterized LLM SQL and requires "
                "allow_dangerous_sql=True. Prefer generation_mode='intent' (bound parameters)."
            )
        self.generation_mode = mode

        # Keep the (compat) validator's operation list aligned with policy.
        self.validator.allowed_operations = list(self.policy.allowed_operations)

    def run(
        self,
        natural_language_query: str,
        *,
        user_id: str | None = None,
        explain: bool = False,
        sql_override: str | None = None,
    ) -> QueryResult:
        started = time.perf_counter()
        sql_query: str | None = None
        schema_strategy: str | None = None
        repaired = False
        try:
            sanitized = self.sanitizer.sanitize_natural_language(natural_language_query)
            schema_ctx, schema_strategy = link_schema(
                sanitized,
                self.schema,
                top_k=self.schema_top_k,
                max_tables=self.max_schema_tables,
                enable=self.enable_schema_linking,
            )

            params: _Params = None
            if sql_override is not None:
                if not self.allow_dangerous_sql:
                    raise GuardError(
                        "sql_override supplies raw, unparameterized SQL and requires "
                        "allow_dangerous_sql=True"
                    )
                sql_query = sql_override.strip()
            elif self.generation_mode == "intent":
                sql_query, params = self._generate_via_intent(sanitized, schema_ctx)
            else:
                sql_query = self.generator.generate_sql(
                    sanitized, schema_ctx, examples=self.few_shot_examples
                )

            sql_query, params = self._enforce(sql_query, params, user_id)

            try:
                results = self.driver.execute_native_query(sql_query, params)
            except Exception as exec_err:
                if self.repair_budget < 1 or sql_override is not None:
                    raise
                repaired_sql = self._try_repair(sql_query, str(exec_err), schema_ctx)
                if repaired_sql is None:
                    raise
                sql_query, params = self._enforce(repaired_sql, None, user_id)
                results = self.driver.execute_native_query(sql_query, params)
                repaired = True

            elapsed = (time.perf_counter() - started) * 1000
            explanation = None
            if explain:
                try:
                    explanation = self.generator.explain_query(sql_query, schema_ctx)
                except Exception as e:
                    explanation = f"(explanation unavailable: {e})"

            self._audit(user_id, natural_language_query, sql_query, True, None, repaired)
            return QueryResult(
                success=True,
                query=natural_language_query,
                sql=sql_query,
                results=results,
                row_count=len(results),
                explanation=explanation,
                execution_ms=elapsed,
                schema_strategy=schema_strategy,
                repaired=repaired,
            )
        except Exception as e:
            self._audit(user_id, natural_language_query, sql_query, False, str(e), repaired)
            return QueryResult(
                success=False,
                query=natural_language_query,
                sql=sql_query,
                error=str(e),
                execution_ms=(time.perf_counter() - started) * 1000,
                schema_strategy=schema_strategy,
                repaired=repaired,
            )

    def _generate_via_intent(
        self, sanitized: str, schema_ctx: dict[str, Any]
    ) -> tuple[str, _Params]:
        """NL → QueryIntent (port) → deterministic parameterized render."""
        gen_intent = getattr(self.generator, "generate_intent", None)
        if not callable(gen_intent):
            raise ValueError(
                "generation_mode='intent' requires a generator with generate_intent()"
            )
        intent = gen_intent(sanitized, schema_ctx, examples=self.few_shot_examples)
        dialect = self.dialect
        if dialect is None:
            raise ValueError(
                "generation_mode='intent' requires a dialect (sqlite/postgres/mysql); "
                "pass dialect=... or use a driver whose dialect can be inferred."
            )
        rendered = render_sql(intent, dialect=dialect)
        return rendered.sql, tuple(rendered.params)

    def _enforce(
        self, sql: str, params: _Params, user_id: str | None
    ) -> tuple[str, _Params]:
        """AST security gate + fail-closed access control. Raises on any violation."""
        result = sql_guard.analyze(
            sql,
            dialect=self.dialect,
            allowed_operations=frozenset(self.policy.allowed_operations),
            allow_multi_statement=self.policy.allow_multi_statement,
        )

        if self.enable_access_control:
            if self.access_controller is None or not user_id:
                raise GuardError(
                    "Access control is enabled but no access controller or user "
                    "identity was provided; denying (fail closed)"
                )
            if result.tables:
                # Use the schema-qualified key so `evil.users` is not authorized
                # as the bare `users`; only a truly unqualified table checks by name.
                self.access_controller.check_table_access(
                    user_id, [_acl_name(t) for t in result.tables]
                )
                for tref in result.tables:
                    columns = result.columns_by_table.get(tref.key)
                    if columns:
                        self.access_controller.check_column_access(
                            user_id, _acl_name(tref), list(columns)
                        )

        return sql, params

    def _try_repair(
        self, sql: str, error: str, schema_ctx: dict[str, Any]
    ) -> str | None:
        repair_fn = getattr(self.generator, "repair_sql_with_error", None)
        if not callable(repair_fn):
            try:
                return self.generator.generate_sql(
                    f"Fix this SQL. Error: {error}\nSQL: {sql}",
                    schema_ctx,
                    examples=self.few_shot_examples,
                )
            except Exception:
                return None
        try:
            return repair_fn(sql, error, schema_ctx)
        except Exception:
            return None

    def _audit(
        self,
        user_id: str | None,
        nl: str,
        sql: str | None,
        success: bool,
        error: str | None,
        repaired: bool,
    ) -> None:
        if not self.enable_audit:
            return
        record = {
            "ts": time.time(),
            "user_id": user_id,
            "query": nl[:500],
            "sql": (sql or "")[:2000],
            "success": success,
            "error": error,
            "mode": self.policy.mode.value,
            "repaired": repaired,
        }
        logger.info(
            "AUDIT user=%s success=%s mode=%s repaired=%s query=%s",
            user_id,
            success,
            self.policy.mode.value,
            repaired,
            nl[:50],
        )
        if self.audit_path:
            try:
                self.audit_path.parent.mkdir(parents=True, exist_ok=True)
                with self.audit_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record) + "\n")
            except OSError as e:
                logger.warning("Audit write failed: %s", e)
