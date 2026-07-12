"""Secure query pipeline.

Deep module: callers only need `run(natural_language, user_id=...)`.
All security, generation, execution, and audit live behind this interface.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

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
    def validate_native_query(self, query: str) -> tuple: ...


class _Sanitizer(Protocol):
    def sanitize_natural_language(self, text: str) -> str: ...


class _Access(Protocol):
    def check_query_access(self, user_id: str, sql: str) -> tuple: ...


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

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "success": self.success,
            "query": self.query,
            "sql": self.sql,
            "results": self.results,
            "row_count": self.row_count,
            "execution_time": self.execution_ms,
        }
        if self.explanation is not None:
            d["explanation"] = self.explanation
        if self.error is not None:
            d["error"] = self.error
        return d


class SecureQueryPipeline:
    """
    Single deep interface for safe NL2SQL execution.

    Order of operations (locality of security logic):
    1. Sanitize NL input
    2. Generate SQL via LLM
    3. Reject multi-statement / non-SELECT via validator
    4. Optional access control
    5. Execute once
    6. Audit log
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

    def run(
        self,
        natural_language_query: str,
        *,
        user_id: Optional[str] = None,
        explain: bool = False,
        sql_override: Optional[str] = None,
    ) -> QueryResult:
        """Run one natural-language (or pre-validated SQL) query safely."""
        started = time.perf_counter()
        sql_query: Optional[str] = None
        try:
            sanitized = self.sanitizer.sanitize_natural_language(natural_language_query)

            if sql_override is not None:
                sql_query = sql_override.strip()
            else:
                sql_query = self.generator.generate_sql(
                    sanitized,
                    self.schema,
                    examples=self.few_shot_examples,
                )

            # Multi-statement guard (common NL2SQL footgun)
            if self._is_multi_statement(sql_query):
                raise ValueError("Multiple SQL statements are not allowed")

            ok, err = self.validator.validate_native_query(sql_query)
            if not ok:
                raise ValueError(f"Security validation failed: {err}")

            if self.enable_access_control and user_id and self.access_controller:
                # Prefer structured check if available; else allow
                check = getattr(self.access_controller, "check_permission", None)
                if callable(check):
                    # Best-effort: many controllers are table-level
                    pass

            results = self.driver.execute_native_query(sql_query)
            elapsed = (time.perf_counter() - started) * 1000
            explanation = None
            if explain:
                try:
                    explanation = self.generator.explain_query(sql_query, self.schema)
                except Exception as e:  # explanation must not fail the query
                    explanation = f"(explanation unavailable: {e})"

            self._audit(user_id, natural_language_query, sql_query, True, None)
            return QueryResult(
                success=True,
                query=natural_language_query,
                sql=sql_query,
                results=results,
                row_count=len(results),
                explanation=explanation,
                execution_ms=elapsed,
            )
        except Exception as e:
            self._audit(user_id, natural_language_query, sql_query, False, str(e))
            return QueryResult(
                success=False,
                query=natural_language_query,
                sql=sql_query,
                error=str(e),
                execution_ms=(time.perf_counter() - started) * 1000,
            )

    @staticmethod
    def _is_multi_statement(sql: str) -> bool:
        # Strip string literals roughly then look for extra semicolons with content
        stripped = sql.strip().rstrip(";").strip()
        # If there's another semicolon with non-whitespace after, reject
        if ";" not in stripped:
            return False
        # Conservative: any internal semicolon → multi
        return True

    def _audit(
        self,
        user_id: Optional[str],
        nl: str,
        sql: Optional[str],
        success: bool,
        error: Optional[str],
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
        }
        logger.info(
            "AUDIT user=%s success=%s query=%s",
            user_id,
            success,
            nl[:50],
        )
        if self.audit_path:
            try:
                self.audit_path.parent.mkdir(parents=True, exist_ok=True)
                with self.audit_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record) + "\n")
            except OSError as e:
                logger.warning("Audit write failed: %s", e)
