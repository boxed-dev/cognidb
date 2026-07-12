# Write mode allows DML only; DDL is always rejected

**Status:** accepted

When write mode is enabled, generated statements may include INSERT, UPDATE, and DELETE (plus read-mode SELECT/CTE). DDL (CREATE/ALTER/DROP/TRUNCATE and similar), privilege changes, and multi-statement batches remain rejected. Schema change is not a CogniDB feature.

**Considered:** DML-only; DML + limited DDL; any single statement under consumer DB grants.

**Why:** Matches 2025–2026 production NL2SQL practice (read-first, allowlisted ops, hard validation before execute). Preserves an explicit opt-in for row mutation without becoming a schema agent. Defense in depth still requires least-privilege DB roles and audit.
