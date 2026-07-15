# CogniDB 3.0

**Secure natural-language SQL for applications** — a Python **library**, not a chat product.

> CogniDB turns natural language into **SELECT-oriented SQL** against PostgreSQL, MySQL, and SQLite. Security is the product: sanitize → generate → validate → allowlists → execute → audit.

**Status:** Source release **3.0.1** ([GitHub Release](https://github.com/boxed-dev/cognidb/releases/tag/v3.0.1)). Prefer `pip install -e .` from a clone until `cognidb==3.0.1` appears on PyPI.

Default: **read mode** (SELECT only) → validate → optional table/column allowlists → execute → audit.  
Opt-in: **write mode** (INSERT/UPDATE/DELETE), schema linking, one repair attempt, **intent mode** (`generation_mode="intent"`).

## Install

```bash
# From source (recommended until PyPI 3.0.1 is published)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Optional extras (see pyproject.toml)
# pip install -e ".[redis]"   # Redis cache
# pip install -e ".[mongo]"   # Mongo driver experiments
```

```bash
pytest -q
```

## Quick start (offline SQLite, under 30 lines)

No network LLM — uses `FakeSQLGenerator` with canned SQL:

```python
from cognidb.drivers import SQLiteDriver
from cognidb.pipeline import SecureQueryPipeline
from cognidb.security import QuerySecurityValidator, InputSanitizer, StatementPolicy, StatementMode
from cognidb.ai.fake_generator import FakeSQLGenerator

drv = SQLiteDriver({"database": ":memory:"})
drv.connect()
drv.execute_native_query("CREATE TABLE users (id INTEGER, name TEXT)")
drv.execute_native_query("INSERT INTO users VALUES (1, 'Ada')")

pipe = SecureQueryPipeline(
    driver=drv,
    generator=FakeSQLGenerator("SELECT id, name FROM users"),
    validator=QuerySecurityValidator(),
    sanitizer=InputSanitizer(),
    schema=drv.fetch_schema(),
    policy=StatementPolicy(mode=StatementMode.READ),
    enable_audit=False,
)
print(pipe.run("list users").to_dict())
drv.disconnect()
```

Same script: `python examples/sqlite_offline_demo.py`.

## High-level client (needs DB + LLM credentials)

```python
from cognidb import CogniDB, create_cognidb

# Env: DB_* and LLM_API_KEY, or pass config / cognidb.yaml
with CogniDB(config_file="cognidb.yaml") as db:
    result = db.query("Show the top 10 customers by revenue", explain=True)
    if result["success"]:
        print(result["sql"], result["results"])
```

`examples/basic_usage.py` demonstrates the high-level API but **requires a live database and LLM API key** — it is not offline.

## What ships in 3.0

| Capability | Notes |
|---|---|
| Dialects | SQLite, PostgreSQL, MySQL |
| `SecureQueryPipeline` | Single NL→SQL→execute path |
| Statement policy | Read default; write opt-in; DDL always rejected |
| Allowlists | Table + column access control when enabled |
| Intent mode | Opt-in structured `QueryIntent` → deterministic SQL render |
| Offline testing | `FakeSQLGenerator` / `FakeIntentGenerator` |
| LLM providers | OpenAI, Anthropic, Azure OpenAI; HuggingFace/local need extra deps |
| Docs | [SECURITY.md](SECURITY.md), [docs/threat-model.md](docs/threat-model.md), [CHANGELOG.md](CHANGELOG.md), [ROADMAP.md](ROADMAP.md) |

## Security (brief)

- Parameterized execution via drivers; validator + sanitizer on generated SQL
- Optional `AccessController` for table/column allowlists (fail-closed on `SELECT *` when columns are restricted)
- Audit logging hooks; adversarial corpus under `tests/security/corpus/`

```python
from cognidb.security import AccessController

access = AccessController()
access.create_restricted_user(
    user_id="analyst_1",
    table_permissions_dict={
        "customers": {
            "operations": ["SELECT"],
            "columns": ["id", "name", "email", "country"],
            "row_filter": "country = 'USA'",
        }
    },
)
# Pass access_controller into SecureQueryPipeline with enable_access_control=True
# or configure via CogniDB settings / yaml.
```

## Configuration

Environment variables (`DB_TYPE`, `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `LLM_PROVIDER`, `LLM_API_KEY`, …) or YAML — see `cognidb.example.yaml`.

## Development

```bash
git clone https://github.com/boxed-dev/cognidb
cd cognidb
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Contributing: [CONTRIBUTING.md](CONTRIBUTING.md). Conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

MIT — see [LICENSE](LICENSE).
