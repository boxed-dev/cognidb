# Security Policy

CogniDB is designed to keep LLM-generated SQL on a constrained path.

## Threat model (summary)

- Prompt injection influencing SQL generation
- Classic SQL injection patterns in generated/native queries
- Destructive statements (DROP/DELETE/UPDATE/UPDATE/INSERT/…)
- Over-broad data access without table/column ACLs

Full write-up (assets, mitigations, honest non-goals): [docs/threat-model.md](docs/threat-model.md).

## Built-in controls

- **AST guard** (`cognidb.security.sql_guard`, built on sqlglot): the single source of
  parsing truth. Statements are gated on structure, not text, so comments, casing, and
  quoting cannot obfuscate an attack. It rejects: non-`SELECT` roots in read mode,
  data-modifying CTEs, DDL/admin (`DROP`/`CREATE`/`ALTER`/`TRUNCATE`/`GRANT`/`PRAGMA`/
  `ATTACH`/`COPY`/`VACUUM`), multiple statements, and a denylist of dangerous functions
  (`load_file`, `pg_read_file`, `readfile`, `load_extension`, `pg_sleep`, `sleep`,
  `benchmark`, `dblink`, …). It **fails closed** on any parse error.
- **Parameter binding**: in intent mode every value is a bound parameter; nothing is
  interpolated into SQL. Identifiers are validated against a strict pattern. Free-form
  raw LLM SQL is opt-in (`allow_dangerous_sql=True`).
- **Statement policy**: read mode default; write mode opt-in for DML; DDL always rejected.
- **Fail-closed access control**: optional table/column allowlists checked against the exact
  tables the AST resolves (comma-joins, schema-qualified, and quoted identifiers included).
  When enabled without a user identity, the query is **denied**, never skipped.
- Audit logging hooks; drivers use streaming row caps, statement timeouts, verified TLS,
  and non-leaking error messages.
- Adversarial SQL corpus (`tests/security/corpus/`) — payloads must fail closed, enforced in CI.

## Recommended: least-privilege database role

App-layer checks are defense-in-depth. The database engine is the real boundary — run
CogniDB as a role that **cannot** write or read files, even if a check is ever bypassed.

Postgres:

```sql
CREATE ROLE cognidb_ro LOGIN PASSWORD '...';
GRANT CONNECT ON DATABASE app TO cognidb_ro;
GRANT USAGE ON SCHEMA public TO cognidb_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO cognidb_ro;   -- no INSERT/UPDATE/DELETE/DDL
ALTER ROLE cognidb_ro SET default_transaction_read_only = on; -- secondary, not the primary control
-- Do NOT grant SUPERUSER or file-access (pg_read_server_files) roles.
```

MySQL:

```sql
CREATE USER 'cognidb_ro'@'%' IDENTIFIED BY '...';
GRANT SELECT ON app.* TO 'cognidb_ro'@'%';   -- no FILE privilege (blocks LOAD_FILE / INTO OUTFILE)
```

For multi-tenant isolation, use PostgreSQL Row-Level Security and set the tenant per request
(`SET LOCAL app.tenant_id = ...` inside the transaction) with `CREATE POLICY … USING
(tenant_id = current_setting('app.tenant_id'))`. Pair it with the least-privilege role
(a `BYPASSRLS`/superuser role skips RLS).

## Supported databases (current)

- SQLite
- MySQL
- PostgreSQL

## Reporting a vulnerability

Open a private security advisory on GitHub or email the maintainer via the address on the GitHub profile. Please do not open public issues for unpatched critical vulnerabilities.
