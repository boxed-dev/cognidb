# CogniDB 4.0

**Secure natural-language SQL for applications** — a Python **library**, not a chat product.

> CogniDB turns natural language into **SELECT-oriented SQL** against PostgreSQL, MySQL, and SQLite. Security is the product: sanitize → generate → **AST guard** → allowlists → **parameterized execute** → audit.

Secure by default:

- **Intent mode is the default** — the LLM produces a structured `QueryIntent`, which is rendered deterministically with **bound parameters** (no value is ever interpolated into SQL). Raw free-form LLM SQL is opt-in behind `allow_dangerous_sql=True`.
- **A real SQL AST guard** ([sqlglot](https://github.com/tobymao/sqlglot)) enforces read/write policy structurally — data-modifying CTEs, `UNION ALL`, stacked statements, DDL/admin (`PRAGMA`/`ATTACH`/`COPY`/`VACUUM`/`GRANT`), and dangerous functions (`load_file`, `pg_read_file`, `pg_sleep`, …) cannot be hidden by comments, casing, or quoting.
- **Read mode** (SELECT) by default; **write mode** (INSERT/UPDATE/DELETE) opt-in. DDL is always rejected. Optional **fail-closed** table/column allowlists.

> **Recommended backstop:** run CogniDB against a least-privilege, `GRANT SELECT`-only database role. App-layer checks are defense-in-depth; the database engine is the real boundary.

## Install

```bash
pip install cognidb
```

From source (for development):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

## Quick start (offline SQLite, secure default)

No network LLM — a `FakeIntentGenerator` supplies a canned `QueryIntent`; the pipeline renders it with **bound parameters**:

```python
from cognidb.drivers import SQLiteDriver
from cognidb.pipeline import SecureQueryPipeline
from cognidb.security import QuerySecurityValidator, InputSanitizer
from cognidb.ai.fake_generator import FakeIntentGenerator
from cognidb.core.query_intent import (
    QueryIntent, QueryType, Column, Condition, ConditionGroup, ComparisonOperator,
)

drv = SQLiteDriver({"database": ":memory:"})
drv.connect()
drv.execute_native_query("CREATE TABLE users (id INTEGER, name TEXT)")
drv.execute_native_query("INSERT INTO users VALUES (1, ?)", ["Ada"])

intent = QueryIntent(
    query_type=QueryType.SELECT, tables=["users"], columns=[Column("id"), Column("name")],
    conditions=ConditionGroup([Condition(Column("name"), ComparisonOperator.EQ, "Ada")]),
)

pipe = SecureQueryPipeline(
    driver=drv,                             # dialect auto-inferred (sqlite)
    generator=FakeIntentGenerator(intent),
    validator=QuerySecurityValidator(),
    sanitizer=InputSanitizer(),
    schema=drv.fetch_schema(),
    enable_audit=False,
)

result = pipe.run("find Ada")
print(result.sql)      # SELECT id, name FROM users WHERE name = ?   <- value is a bound parameter
print(result.results)  # [{'id': 1, 'name': 'Ada'}]
drv.disconnect()
```

**Free-form (opt-in).** To let the LLM emit raw SQL strings instead of intents, pass `generation_mode="free_form", allow_dangerous_sql=True`. The AST guard still applies, but values are inlined by the model rather than bound — prefer intent mode.

## High-level client (needs DB + LLM credentials)

```python
from cognidb import CogniDB

with CogniDB(config_file="cognidb.yaml") as db:
    result = db.query("Show the top 10 customers by revenue", explain=True)
    if result["success"]:
        print(result["sql"], result["results"])
```

## Security model

| Layer | What it does |
|---|---|
| Sanitizer | Normalizes the natural-language input |
| **AST guard** (`cognidb.security.sql_guard`) | Parses with the target dialect and gates on structure: single statement, allowed operation only, no DDL/admin, no data-modifying CTE, no dangerous functions. Fails **closed** on any parse error. |
| **Parameter binding** | Intent render emits placeholders (`?`/`%s`) + an ordered params list; identifiers are validated, never bound. |
| Access control (opt-in) | Fail-closed table/column allowlists checked against the exact tables the AST resolves. |
| Drivers | Bound parameters, streaming row caps, statement timeouts, TLS `verify-full` (PG) / `ssl_verify_identity` (MySQL), non-leaking errors. |
| Audit | Structured audit log of every query. |

```python
from cognidb.security import AccessController

access = AccessController()
access.create_read_only_user("analyst_1", ["customers"])
# SecureQueryPipeline(..., access_controller=access, enable_access_control=True)
# then: pipe.run("...", user_id="analyst_1")   # missing user_id -> denied (fail closed)
```

For a copy-paste read-only role recipe (Postgres/MySQL) and Row-Level-Security guidance, see [SECURITY.md](SECURITY.md).

## Offline benchmarks

```bash
python -m benchmarks.run --track all
python -m benchmarks.run --track all --smoke --fail-under 1.0
```

The benchmark drives the real pipeline + SQLite + security stack with canned SQL — a **security/policy/robustness regression harness**, not an NL→SQL accuracy score. See [`benchmarks/README.md`](benchmarks/README.md).

## Configuration

Environment variables (`DB_TYPE`, `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `LLM_PROVIDER`, `LLM_API_KEY`, …) or YAML — see `cognidb.example.yaml`. `${ENV_VAR}` placeholders in YAML are expanded on load (and error loudly if unset).

## Development

```bash
pip install -e ".[dev]"
pytest -q
ruff check cognidb/ && bandit -rq -ll cognidb/
```

Contributing: [CONTRIBUTING.md](CONTRIBUTING.md). Conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Dialects: SQLite, PostgreSQL, MySQL. License: MIT — see [LICENSE](LICENSE).
