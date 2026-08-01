# Changelog

## 4.0.0 — security foundations (breaking)

A ground-up hardening of the security core. The regex/`sqlparse` checks are
replaced by a real SQL AST guard, values are always bound parameters, and the
secure path is the default.

### Breaking changes
- **`generation_mode="intent"` is now the DEFAULT.** Raw free-form LLM SQL is
  opt-in behind `allow_dangerous_sql=True` (it cannot be parameterized).
- **The intent renderer returns `RenderedSQL(sql, params)`** and requires a
  `dialect` (`render_sql(intent, dialect=...)`); `SecureQueryPipeline` takes a
  `dialect` (auto-inferred from the driver) and threads bound parameters through
  execution. No value is ever interpolated into SQL.
- Access control **fails closed**: when `enable_access_control=True` but the
  user identity or controller is missing, the query is denied (never skipped).
- `cognidb/security/query_parser.py` (the `sqlparse` tokenizer path) is removed.

### Security
- **AST guard (`cognidb.security.sql_guard`, sqlglot)** is the single source of
  parsing truth. Structural gating catches what regex could not: data-modifying
  CTEs (`WITH … (DELETE …) SELECT`), `UNION ALL`, stacked statements, and
  DDL/admin (`PRAGMA`/`ATTACH`/`COPY`/`VACUUM`/`GRANT`) — none can be hidden by
  comments, casing, or quoting.
- **Correct table extraction** for comma-joins, schema-qualified, and
  bracket-quoted identifiers (the old regex missed these → allowlist bypass /
  fail-open). ACL now checks the exact tables the DB executes.
- **Dangerous-function denylist** on the AST (`load_file`, `pg_read_file`,
  `readfile`, `load_extension`, `pg_sleep`, `sleep`, `benchmark`, `dblink`, …).
- **Parameter binding everywhere**; the tautology/UNION textual denylists are
  removed as false guarantees (defended by params + read-only role + allowlist).
- **Drivers**: bound parameters, streaming cursors with row caps (no more
  `fetchall`-then-slice DoS), Postgres `sslmode=verify-full`, MySQL
  `ssl_verify_identity` + `MAX_EXECUTION_TIME`, SQLite interrupt watchdog,
  generic (non-leaking) error messages.
- **Secrets**: per-install random KDF salt (≥600k iterations), `repr`-safe
  secret fields, `${ENV_VAR}` expansion on config load.
- **Adversarial red-team fixes**: quote-stripped function matching (so
  `"pg_read_file"(…)` cannot dodge the denylist), scope-resolved table
  extraction (a CTE whose name collides with a real table no longer empties the
  ACL), multi-table `SELECT *`/unqualified-column attribution (fail closed),
  `SELECT … INTO` rejected, schema-qualified ACL keys (`evil.users` ≠ `users`),
  and `run(sql_override=…)` gated behind `allow_dangerous_sql`.
- Removed the unused `InputSanitizer` value/limit/offset helpers (dead surface);
  the sanitizer now covers only the NL question and identifier introspection.

### Tooling
- CI gates: ruff, mypy, bandit, pip-audit, and a coverage floor; test matrix
  3.10–3.13. `requires-python >= 3.10`. Adversarial corpus expanded and
  re-framed around the AST guard.

## 3.0.1

Intent mode, column allowlists, adversarial corpus, SQLite E2E, Postgres CI,
threat model, and release packaging on top of the 3.0.0 library core.
Install from Git until `cognidb==3.0.1` is available on PyPI.

### Security / product law
- **Read mode** default (SELECT); **write mode** opt-in for INSERT/UPDATE/DELETE only
- **DDL always rejected**; multi-statement only with write mode + second opt-in
- **Table and column allowlists** enforced when access control is enabled (fail-closed on `SELECT *` with column restrictions)
- **Schema linking** with bounded full-schema fallback
- **One repair attempt** on execution failure (re-validated against policy)
- **Adversarial SQL corpus** under `tests/security/corpus/` for closed-fail regressions
- Threat model documented in `docs/threat-model.md` + `SECURITY.md`

### Architecture
- `SecureQueryPipeline` is the only NL→SQL→execute path
- **Intent mode** (`generation_mode="intent"`): `QueryIntent` → `cognidb.intent.render_sql`
- `StatementPolicy`, table/column extractors, schema linker
- `FakeSQLGenerator` / `FakeIntentGenerator` for offline tests and demos
- Dialects: **SQLite, PostgreSQL, MySQL**
- Public API version **3.0.1** (`pyproject.toml`, `cognidb.__version__`, `cognidb.client`)

### Tests / examples
- Unit + security + SQLite E2E coverage; Postgres integration when `DATABASE_URL` is set
- Offline demo: `examples/sqlite_offline_demo.py`

### Docs / community
- CONTEXT.md glossary, ADRs 0001–0010, ROADMAP, threat model
- CONTRIBUTING, CODE_OF_CONDUCT, GitHub issue/PR templates

## 3.0.0 — secure library core

Major SoTA-oriented library release tagged as `v3.0.0`:
read-mode default, `SecureQueryPipeline`, statement policy, schema linking,
dialects (SQLite / PostgreSQL / MySQL), and public API 3.0.0.

## 2.0.1
- Initial revive: installable API, MIT, CI, SQLite driver, basic pipeline
