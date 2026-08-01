"""Dialect-aware SQL security guard built on a real AST (sqlglot).

This is the single source of parsing truth for CogniDB. It replaces the previous
regex + sqlparse-tokenizer checks, which the audit showed were bypassable by
tautologies, ``UNION ALL``, data-modifying CTEs, comma-joins, schema-qualified
and bracket-quoted identifiers.

Design: parse once with the target dialect; **fail closed** on any parse error;
gate on the *structure* of the statement, never on its text. Because sqlglot has
already resolved the grammar, a ``DELETE`` hidden in a CTE or a comment cannot
hide from ``find_all(exp.Delete)``.
"""

from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError
from sqlglot.optimizer.scope import build_scope

from ..core.exceptions import SecurityError


class GuardError(SecurityError):
    """Raised when a statement violates the security guard."""


# Dialect names understood by sqlglot for the engines CogniDB supports.
_DIALECTS = {"sqlite", "postgres", "mysql"}

# Write nodes — used both to name the operation and to detect hidden writes.
_WRITE_NODES: tuple[type, ...] = (exp.Insert, exp.Update, exp.Delete, exp.Merge)

# Structurally dangerous nodes that may never appear anywhere in a statement,
# in any mode (DDL + admin). Built with getattr so a sqlglot version that lacks
# one of these classes does not break import.
_DANGEROUS_NAMES = (
    "Create", "Drop", "Alter", "TruncateTable", "Command",
    "Pragma", "Attach", "Detach", "Copy", "Grant",
)
_DANGEROUS: tuple[type, ...] = tuple(
    getattr(exp, name) for name in _DANGEROUS_NAMES if hasattr(exp, name)
)

# Functions that read files, execute code, exfiltrate, or enable time-based DoS.
# Matched by exact name against the parsed AST (exp.Anonymous), so casing,
# comments, and whitespace cannot obfuscate them. Defense-in-depth on top of a
# least-privilege read-only DB role.
_DANGEROUS_FUNCS = frozenset({
    # file / filesystem access
    "load_file", "load_data", "readfile", "writefile", "load_extension",
    "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "pg_stat_file",
    "lo_import", "lo_export",
    # cross-database / remote
    "dblink", "dblink_exec",
    # time-based DoS
    "sleep", "pg_sleep", "benchmark", "waitfor",
    # command execution (various engines/extensions)
    "sys_exec", "sys_eval", "xp_cmdshell", "fts3_tokenizer",
    # server administration / connection DoS (never legitimate from NL2SQL)
    "pg_terminate_backend", "pg_cancel_backend", "pg_reload_conf", "pg_rotate_logfile",
})

# Base "query" type (Select/Union/Subquery/…). Present in modern sqlglot.
_QUERY = getattr(exp, "Query", None)


def _is_query(node: exp.Expression) -> bool:
    if _QUERY is not None:
        return isinstance(node, _QUERY)
    return isinstance(node, (exp.Select, exp.Union, exp.Subquery))


@dataclass(frozen=True)
class TableRef:
    """A base-table reference. ``name``/``db``/``catalog`` are lowercased."""

    name: str
    db: str = ""
    catalog: str = ""

    @property
    def key(self) -> str:
        return ".".join(p for p in (self.catalog, self.db, self.name) if p)


@dataclass(frozen=True)
class GuardResult:
    operation: str
    tables: tuple[TableRef, ...]
    columns_by_table: dict[str, tuple[str, ...]]


def _operation_of(node: exp.Expression) -> str:
    if isinstance(node, exp.Insert):
        return "INSERT"
    if isinstance(node, exp.Update):
        return "UPDATE"
    if isinstance(node, exp.Delete):
        return "DELETE"
    if isinstance(node, exp.Merge):
        return "MERGE"
    if _is_query(node):
        return "SELECT"
    # Drop/Create/Alter/Truncate/Grant/Pragma/Attach/Copy/Command/Set/Use/…
    raise GuardError(f"Statement type {type(node).__name__} is not allowed")


def _cte_names(node: exp.Expression) -> frozenset[str]:
    return frozenset(cte.alias_or_name.lower() for cte in node.find_all(exp.CTE))


def _table_ref(tbl: exp.Table) -> TableRef | None:
    name = (tbl.name or "").lower()
    if not name:
        return None
    return TableRef(name=name, db=(tbl.db or "").lower(), catalog=(tbl.catalog or "").lower())


def _base_tables(node: exp.Expression) -> list[TableRef]:
    """Resolve the PHYSICAL base tables the statement reads/writes.

    Uses sqlglot scope resolution, which correctly separates real tables from CTE
    references even when a CTE name collides with a table it reads
    (``WITH secret AS (SELECT * FROM secret) SELECT * FROM secret`` -> ``secret``).
    Falls back to a CTE-name-aware ``find_all`` for statements scope cannot handle
    (INSERT/UPDATE/DELETE targets).
    """
    refs: list[TableRef] = []
    seen: set[str] = set()

    root = None
    try:
        root = build_scope(node)
    except Exception:
        root = None
    if root is not None:
        for scope in root.traverse():
            for source in scope.sources.values():
                if isinstance(source, exp.Table):
                    ref = _table_ref(source)
                    if ref and ref.key not in seen:
                        seen.add(ref.key)
                        refs.append(ref)
        if refs:
            return refs

    # Fallback: bare identifiers matching a CTE name are CTE references, not tables.
    cte_names = _cte_names(node)
    for tbl in node.find_all(exp.Table):
        ref = _table_ref(tbl)
        if ref is None:
            continue
        if not ref.db and not ref.catalog and ref.name in cte_names:
            continue
        if ref.key not in seen:
            seen.add(ref.key)
            refs.append(ref)
    return refs


def _columns_by_table(node: exp.Expression, tables: list[TableRef]) -> dict[str, tuple[str, ...]]:
    table_keys = [t.key for t in tables]
    real_keys = set(table_keys)

    # Map every alias/name that can qualify a column to a resolved base-table key.
    alias_map: dict[str, str] = {}
    for tbl in node.find_all(exp.Table):
        ref = _table_ref(tbl)
        if ref is None or ref.key not in real_keys:
            continue
        if tbl.alias:
            alias_map[tbl.alias.lower()] = ref.key
        alias_map[ref.name] = ref.key

    grouped: dict[str, set] = {}

    # A ``*`` projection exposes every column of every table in scope -> record it
    # for all of them (fail closed; column ACL then decides).
    if list(node.find_all(exp.Star)):
        for key in table_keys:
            grouped.setdefault(key, set()).add("*")

    for col in node.find_all(exp.Column):
        qualifier = (col.table or "").lower()
        cname = col.name
        if not cname:
            continue
        if qualifier and qualifier in alias_map:
            grouped.setdefault(alias_map[qualifier], set()).add(cname)
        elif not qualifier:
            # Unqualified: cannot pin to one table -> attribute to all (fail closed).
            for key in table_keys:
                grouped.setdefault(key, set()).add(cname)

    return {k: tuple(sorted(v)) for k, v in grouped.items()}


def _parse(sql: str, dialect):
    """Parse to a list of statements or raise GuardError (fail closed)."""
    if dialect is not None and dialect not in _DIALECTS:
        raise GuardError(f"Unsupported dialect: {dialect!r}")
    try:
        parsed = sqlglot.parse(sql, read=dialect)
    except ParseError as e:
        raise GuardError(f"Unparseable SQL rejected: {e}") from e
    except Exception as e:  # tokenizer/other sqlglot errors — fail closed
        raise GuardError(f"SQL could not be parsed safely: {e}") from e
    statements = [s for s in parsed if s is not None]
    if not statements:
        raise GuardError("Empty statement is not allowed")
    return statements


def _analyze_one(node: exp.Expression, allowed_operations: frozenset[str]) -> GuardResult:
    operation = _operation_of(node)

    # SELECT ... INTO creates a table (Postgres) — it is a write, not a read.
    if node.args.get("into") is not None:
        raise GuardError("SELECT ... INTO is not allowed (it creates a table)")

    # DDL / admin may never appear anywhere in the tree.
    if list(node.find_all(*_DANGEROUS)):
        raise GuardError("DDL or administrative statements are not allowed")

    # File-access / RCE / time-based-DoS functions, matched on the parsed AST.
    # ``fn.name`` is the quote-stripped function name, so "pg_read_file"(...) and
    # `sleep`(...) cannot dodge the denylist by quoting the identifier.
    for fn in node.find_all(exp.Anonymous):
        if fn.name.lower() in _DANGEROUS_FUNCS:
            raise GuardError(f"Disallowed function is not permitted: {fn.name.lower()}")

    # Hidden writes: a read query must contain no write nodes (data-modifying CTE);
    # a write statement must contain exactly one write node (its own root).
    writes: list[exp.Expression] = list(node.find_all(*_WRITE_NODES))
    if operation == "SELECT":
        if writes:
            raise GuardError("Data-modifying statement is not allowed in a read query")
    elif len(writes) > 1:
        raise GuardError("Nested data-modifying statement is not allowed")

    if operation not in allowed_operations:
        raise GuardError(f"Operation {operation} is not allowed")

    tables = _base_tables(node)
    return GuardResult(
        operation=operation,
        tables=tuple(tables),
        columns_by_table=_columns_by_table(node, tables),
    )


def analyze(
    sql: str,
    *,
    dialect: str | None,
    allowed_operations: frozenset[str],
    allow_multi_statement: bool = False,
) -> GuardResult:
    """Parse and security-gate a SQL string. Raises :class:`GuardError` on any violation.

    Args:
        sql: the SQL to check (the exact string that will execute).
        dialect: target engine — one of ``sqlite``/``postgres``/``mysql``, or
            ``None`` to parse with sqlglot's generic dialect.
        allowed_operations: the operations permitted by the active policy.
        allow_multi_statement: permit multiple statements (write mode opt-in only).
    """
    statements = _parse(sql, dialect)

    try:
        if len(statements) > 1:
            if not allow_multi_statement:
                raise GuardError("Multiple statements are not allowed")
            results = [_analyze_one(s, allowed_operations) for s in statements]
            tables: list[TableRef] = []
            seen = set()
            columns: dict[str, tuple[str, ...]] = {}
            for r in results:
                for t in r.tables:
                    if t.key not in seen:
                        seen.add(t.key)
                        tables.append(t)
                columns.update(r.columns_by_table)
            return GuardResult(operation="MULTI", tables=tuple(tables), columns_by_table=columns)

        return _analyze_one(statements[0], allowed_operations)
    except GuardError:
        raise
    except Exception as e:  # never leak an unexpected error — fail closed
        raise GuardError(f"SQL rejected (analysis error): {e}") from e


def extract_table_refs(sql: str, dialect=None) -> tuple[TableRef, ...]:
    """Best-effort base-table extraction WITHOUT security gating (compat helper).

    Fails closed on unparseable SQL. Used by the legacy extractor shims.
    """
    refs: list[TableRef] = []
    seen = set()
    try:
        for stmt in _parse(sql, dialect):
            for t in _base_tables(stmt):
                if t.key not in seen:
                    seen.add(t.key)
                    refs.append(t)
    except GuardError:
        raise
    except Exception as e:  # fail closed
        raise GuardError(f"table extraction failed: {e}") from e
    return tuple(refs)


def primary_operation(sql: str, dialect=None) -> str:
    """Return the primary operation keyword of the first statement (compat helper).

    Fails closed on unparseable SQL. Returns SELECT/INSERT/UPDATE/DELETE/MERGE for
    those, or the node type name uppercased (e.g. DROP, COMMAND) for anything else.
    """
    node = _parse(sql, dialect)[0]
    if isinstance(node, exp.Insert):
        return "INSERT"
    if isinstance(node, exp.Update):
        return "UPDATE"
    if isinstance(node, exp.Delete):
        return "DELETE"
    if isinstance(node, exp.Merge):
        return "MERGE"
    if _is_query(node):
        return "SELECT"
    return type(node).__name__.upper()
