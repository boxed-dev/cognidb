# Changelog

## 3.0.0 — major SoTA library core

### Security / product law (from design grill)
- **Read mode** default (SELECT); **write mode** opt-in for INSERT/UPDATE/DELETE only
- **DDL always rejected**; multi-statement only with write mode + second opt-in
- **Table allowlists** enforced when access control enabled
- **Schema linking** with bounded full-schema fallback
- **One repair attempt** on execution failure (re-checked against policy)

### Architecture
- Deep `SecureQueryPipeline` is the only execution path
- `StatementPolicy`, table extractor, schema linker, `FakeSQLGenerator` for offline tests
- Dialects: SQLite, PostgreSQL, MySQL

### Docs
- CONTEXT.md glossary, ADRs 0001–0010, GRILL-SUMMARY, ROADMAP

## 2.0.1
- Initial revive: installable API, MIT, CI, SQLite driver, basic pipeline
