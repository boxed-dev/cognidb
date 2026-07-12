"""Secure query pipeline — deep module for NL→SQL→execute (major-release SoTA core)."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple

from ..schema.linking import link_schema
from ..security.statement_policy import StatementMode, StatementPolicy
from ..security.table_extractor import extract_primary_operation, extract_tables

logger = logging.getLogger(__name__)


class _Driver(Protocol):
    def execute_native_query(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]: ...


class _Generator(Protocol):
    def generate_sql(
        self, natural_language: str, schema: Dict[str, Any], examples: Any = None
    ) -> str: ...

    def explain_query(self, sql: str, schema: Dict[str, Any]) -> str: ...


class _Validator(Protocol):
    def validate_native_query(self, query: str) -> Tuple[bool, Optional[str]]: ...

    allowed_operations: Any


class _Sanitizer(Protocol):
    def sanitize_natural_language(self, text: str) -> str: ...


@dataclass
class QueryResult:
    success: bool
    query: str
    sql: Optional[str] = None
    results: List[Dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    explanation: Optional[str] = None
    error: Optional[str] = None
    execution_ms: Optional[float] = None
    schema_strategy: Optional[str] = None
    repaired: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
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
    """
    Single deep interface for safe NL2SQL execution.

    1. Sanitize NL
    2. Link schema context
    3. Generate SQL (or override)
    4. Statement policy (mode, multi-stmt, allowlist ops)
    5. Table allowlist access control
    6. Execute; optional single repair on failure
    7. Audit
    """

    def __init__(
        self,
        *,
        driver: _Driver,
        generator: _Generator,
        validator: _Validator,
        sanitizer: _Sanitizer,
        schema: Dict[str, Any],
        access_controller: Optional[Any] = None,
        enable_access_control: bool = False,
        few_shot_examples: Any = None,
        audit_path: Optional[str] = None,
        enable_audit: bool = True,
        policy: Optional[StatementPolicy] = None,
        enable_schema_linking: bool = True,
        schema_top_k: int = 8,
        max_schema_tables: int = 40,
        repair_budget: int = 1,
    ):
        self.driver = driver
        self.generator = generator
        self.validator = validator
        self.sanitizer = sanitizer
        self.schema = schema
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

        # Keep validator ops aligned with policy
        self.validator.allowed_operations = list(self.policy.allowed_operations)

    def run(
        self,
        natural_language_query: str,
        *,
        user_id: Optional[str] = None,
        explain: bool = False,
        sql_override: Optional[str] = None,
    ) -> QueryResult:
        started = time.perf_counter()
        sql_query: Optional[str] = None
        schema_strategy: Optional[str] = None
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

            if sql_override is not None:
                sql_query = sql_override.strip()
            else:
                sql_query = self.generator.generate_sql(
                    sanitized,
                    schema_ctx,
                    examples=self.few_shot_examples,
                )

            sql_query = self._enforce(sql_query, user_id)

            try:
                results = self.driver.execute_native_query(sql_query)
            except Exception as exec_err:
                if self.repair_budget < 1 or sql_override is not None:
                    raise
                repaired_sql = self._try_repair(sql_query, str(exec_err), schema_ctx)
                if repaired_sql is None:
                    raise
                sql_query = self._enforce(repaired_sql, user_id)
                results = self.driver.execute_native_query(sql_query)
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

    def _enforce(self, sql: str, user_id: Optional[str]) -> str:
        ok_ms, err_ms = self.policy.check_multi_statement(sql)
        if not ok_ms:
            raise ValueError(err_ms)

        op = extract_primary_operation(sql)
        if op in ("DROP", "CREATE", "ALTER", "TRUNCATE", "GRANT", "REVOKE"):
            raise ValueError(f"Operation {op} is not allowed by statement policy (DDL/admin forbidden)")
        if op not in self.policy.allowed_operations and op != "UNKNOWN":
            raise ValueError(
                f"Operation {op} not allowed in {self.policy.mode.value} mode"
            )

        ok, err = self.validator.validate_native_query(sql)
        if not ok:
            raise ValueError(f"Security validation failed: {err}")

        if self.enable_access_control and self.access_controller and user_id:
            tables = extract_tables(sql)
            if tables:
                self.access_controller.check_table_access(user_id, tables)
            # Column checks are best-effort when * is used; skip star expansion here

        return sql

    def _try_repair(
        self, sql: str, error: str, schema_ctx: Dict[str, Any]
    ) -> Optional[str]:
        repair_fn = getattr(self.generator, "repair_sql_with_error", None)
        if not callable(repair_fn):
            # Fallback: re-generate with error hint in NL if generator has no repair
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
        user_id: Optional[str],
        nl: str,
        sql: Optional[str],
        success: bool,
        error: Optional[str],
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
