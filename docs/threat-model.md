# CogniDB threat model

Honest security boundaries for a **security-first natural-language SQL library**.
This document describes assets, attackers, mitigations, and **non-goals**.

## Assets

| Asset | Why it matters |
|---|---|
| Caller databases | Generated SQL must not destroy schema or exfiltrate beyond policy |
| Library consumer trust | Embedders rely on intent-mode/read-mode defaults and fail-closed validation |
| Audit trail integrity | Pipeline runs should leave reviewable evidence of what ran |

## Attackers / abuse cases

1. **Prompt injection** — natural-language input that steers the model toward unsafe SQL or a malicious `QueryIntent`.
2. **Hostile generated statements** — free-form SQL (opt-in path) that includes SQLi idioms, stacked statements, DDL, or file/time primitives.
3. **Confused deputy** — a privileged DB role used by the library that over-grants beyond statement policy.
4. **Cross-caller access** — one caller identity reading tables/columns belonging to another when ACLs are enabled.

## Mitigations (defense in depth)

CogniDB layers five independent controls. Each is designed to fail closed on its own,
so a bypass of one layer does not imply a bypass of the whole pipeline.

| Layer | What it does |
|---|---|
| **Sanitizer** (`cognidb.security.sanitizer`) | Normalizes the natural-language input before it reaches the generator. |
| **AST guard** (`cognidb.security.sql_guard`, sqlglot) | The single source of parsing truth. Parses the exact SQL string that will execute with the target dialect and gates on *structure*, never on text: single statement only (unless write mode + `allow_multi_statement`); only the operations the active `StatementPolicy` allows (`SELECT`, or `SELECT`/`INSERT`/`UPDATE`/`DELETE` in write mode); no DDL/admin anywhere in the tree (`CREATE`/`DROP`/`ALTER`/`TRUNCATE`/`PRAGMA`/`ATTACH`/`DETACH`/`COPY`/`GRANT`/`Command`); no data-modifying CTE hidden inside a read query; no `SELECT ... INTO` (creates a table); a denylist of dangerous functions matched on the parsed function name (`load_file`, `pg_read_file`, `pg_sleep`, `sleep`, `benchmark`, `dblink`, `xp_cmdshell`, …). **Fails closed on any parse error** — unparseable SQL is rejected, never passed through. |
| **Statement policy** (`cognidb.security.statement_policy`) | Read mode (default) permits `SELECT` only; write mode is an explicit opt-in that adds `INSERT`/`UPDATE`/`DELETE`; DDL is always forbidden regardless of mode; multi-statement requires write mode **and** a second explicit opt-in. |
| **Fail-closed access control** (opt-in) | Optional table/column allowlists, checked against the exact base tables the AST guard resolves (comma-joins, schema-qualified and quoted identifiers included). Schema-qualified keys mean `evil.users` is never authorized as `users`. When enabled without a caller identity or controller, the query is **denied**, never skipped. |
| **Parameterized drivers** | In intent mode (default), every value is a bound parameter — nothing is ever interpolated into SQL; identifiers are validated against a strict allow-pattern instead of being bound. Drivers add streaming cursors with row caps (no `fetchall`-then-slice DoS), statement timeouts, TLS `sslmode=verify-full` (Postgres) / `ssl_verify_identity` (MySQL), and generic, non-leaking error messages. |
| **Audit** | Every run (success or failure) is logged: mode, statement, repair flag, and outcome, for later review. |

Two SQL-generation paths feed the AST guard:

- **Intent mode (default):** the LLM (or a caller-supplied generator) produces a structured `QueryIntent`; `cognidb.intent.render_sql` renders it deterministically with bound parameters. Values can never reach the SQL string because the renderer only ever emits placeholders for them.
- **Free-form (opt-in, `allow_dangerous_sql=True`):** the LLM emits a raw SQL string. The same AST guard applies, but values are inlined by the model rather than bound, so this path carries materially higher risk and is not the default.

## Non-goals (honest)

- CogniDB is **not** a WAF, IDS, or full SQL firewall for arbitrary client SQL outside the secure query pipeline.
- The AST guard proves *structural* properties (statement shape, operation, forbidden functions) of the exact string that will execute; it does not prove the query is semantically what the caller intended, and it is not a substitute for least-privilege DB grants.
- Free-form mode is a deliberately higher-risk opt-in: the guard still gates it, but unbound value interpolation means it is not held to the same assurance bar as intent mode.
- Row-level predicates are a designed seam (ADR 0005), not a fully shipped product guarantee in every release line — use PostgreSQL Row-Level Security for multi-tenant isolation (see `SECURITY.md`).
- Legitimate CTE/subquery-heavy analytics that resolve to a data-modifying node anywhere in the tree are rejected in read mode by design (fail-closed), even when the outer statement is a `SELECT`.
- Dangerous-function matching is a denylist on the parsed AST (defense-in-depth); it is not a substitute for a least-privilege, read-only DB role that cannot read/write files or execute admin commands even if a check is ever bypassed.

## Verification

- Unit seams: `StatementPolicy`, `sql_guard.analyze`, the intent renderer's identifier/DDL rejection.
- Corpus: `tests/security/corpus/` — adversarial payloads (tautologies, `UNION ALL`, data-modifying CTEs, comma-joins, quoted/schema-qualified identifiers, dangerous functions) must fail closed.
- Pipeline guards: `tests/security/test_pipeline_guards.py` and related — access-control fail-closed behavior, `allow_dangerous_sql` gating, multi-statement opt-in.
