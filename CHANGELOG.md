# Changelog

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
