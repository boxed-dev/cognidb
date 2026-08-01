"""Statement policy — read mode default, write mode DML opt-in (ADR 0002–0004)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StatementMode(str, Enum):
    READ = "read"
    WRITE = "write"


READ_OPS: frozenset[str] = frozenset({"SELECT"})
WRITE_OPS: frozenset[str] = frozenset({"SELECT", "INSERT", "UPDATE", "DELETE"})
# DDL and admin always forbidden in library policy
FORBIDDEN_ALWAYS: frozenset[str] = frozenset({
    "DROP", "CREATE", "ALTER", "TRUNCATE", "GRANT", "REVOKE",
    "REPLACE", "RENAME", "MERGE", "CALL", "EXEC", "EXECUTE",
})


@dataclass(frozen=True)
class StatementPolicy:
    """Immutable policy for one pipeline configuration."""

    mode: StatementMode = StatementMode.READ
    allow_multi_statement: bool = False

    def __post_init__(self) -> None:
        if self.allow_multi_statement and self.mode != StatementMode.WRITE:
            raise ValueError(
                "allow_multi_statement requires write mode (second opt-in only with write)"
            )

    @property
    def allowed_operations(self) -> frozenset[str]:
        return WRITE_OPS if self.mode == StatementMode.WRITE else READ_OPS

    def check_multi_statement(self, sql: str) -> tuple[bool, str | None]:
        if _is_multi_statement(sql):
            if self.mode == StatementMode.READ:
                return False, "Multiple SQL statements are not allowed in read mode"
            if not self.allow_multi_statement:
                return (
                    False,
                    "Multiple SQL statements require write mode and allow_multi_statement=True",
                )
        return True, None


def _is_multi_statement(sql: str) -> bool:
    stripped = sql.strip().rstrip(";").strip()
    return ";" in stripped
