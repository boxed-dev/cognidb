# Grill summary — major release shared understanding

Decisions locked in CONTEXT.md + docs/adr/0001–0010.

## Product
- Embeddable **library**, not a chat product.

## Security
- **Read mode** default (SELECT/CTE only).
- **Write mode** opt-in: INSERT/UPDATE/DELETE only; **never DDL**.
- **Multi-statement**: never in read mode; write mode requires **second** opt-in.
- **Allowlists** (table/column) by caller identity when access control on.
- **Row predicate hooks** designed, implemented later.
- **Defense in depth**: policy ∧ DB grants ∧ audit.

## Generation
- **Free-form** default; **intent mode** opt-in.
- **Schema linking** default; full schema fallback with size limit; else fail closed.
- **One repair** on execution error; re-check policy.

## Dialects
- SQLite, PostgreSQL, MySQL.

## Success bar (major)
- Single pipeline entry; no execute bypass.
- Tests: policy, multi-stmt, allowlist, repair, SQLite E2E with FakeLLM.
- Honest README + versioned package.
