# Migrating from CogniDB 3.x to 4.0.0

CogniDB 4.0.0 is a security-foundations breaking release (see the `## 4.0.0` entry
in `CHANGELOG.md` for the full write-up). The regex/`sqlparse` guard is replaced by
a real SQL AST guard ([sqlglot](https://github.com/tobymao/sqlglot)), values are
always bound parameters in the default path, and the secure path is now the
default rather than an opt-in.

## Breaking changes and what to do about them

### 1. Intent mode is now the default generation mode

`SecureQueryPipeline(generation_mode=...)` defaults to `"intent"` instead of
`"free_form"`. Intent mode requires your generator to implement `generate_intent(
natural_language, schema, examples=None) -> QueryIntent` (see `cognidb.ai.fake_generator
.FakeIntentGenerator` for the shape, or your own LLM-backed generator).

- **If your generator already implements `generate_intent`:** no change needed —
  you get bound-parameter rendering automatically.
- **If your generator only implements `generate_sql` (raw SQL strings):** pass
  `generation_mode="free_form"` explicitly, plus the opt-in below.

```python
# 3.x (implicit free-form)
pipe = SecureQueryPipeline(driver=drv, generator=gen, validator=v, sanitizer=s, schema=schema)

# 4.0.0 — keep the old free-form behavior explicitly
pipe = SecureQueryPipeline(
    driver=drv, generator=gen, validator=v, sanitizer=s, schema=schema,
    generation_mode="free_form", allow_dangerous_sql=True,
)
```

### 2. Free-form SQL requires `allow_dangerous_sql=True`

Raw, unparameterized LLM SQL — whether via `generation_mode="free_form"` or
`pipe.run(..., sql_override=...)` — now raises unless `allow_dangerous_sql=True`
is passed to the pipeline constructor. This is enforced at construction time
(`generation_mode="free_form"` without the flag raises `ValueError` immediately)
and at run time (`sql_override` without the flag raises `GuardError`).

```python
pipe = SecureQueryPipeline(..., generation_mode="free_form", allow_dangerous_sql=True)
```

Prefer migrating your generator to `generate_intent` and dropping this flag —
intent mode is the durable, higher-assurance path.

### 3. The intent renderer's signature and return type changed

`cognidb.intent.render_sql` now requires a `dialect` and returns a `RenderedSQL`
(a `sql: str` / `params: tuple[Any, ...]` pair) instead of a bare SQL string.

```python
# 3.x
sql = render_sql(intent)

# 4.0.0
rendered = render_sql(intent, dialect="sqlite")  # or "postgres" / "mysql"
sql, params = rendered.sql, rendered.params
```

`SecureQueryPipeline` threads this automatically — it infers `dialect` from the
driver class name (or accepts an explicit `dialect=` kwarg) and passes the bound
`params` through to `driver.execute_native_query(sql, params)`. No value is ever
interpolated into the SQL string in intent mode.

### 4. Access control fails closed on missing identity

If you had `enable_access_control=True` without always supplying `user_id`,
those calls previously could be skipped; they now raise/deny (`GuardError`) when
`user_id` or the access controller is missing. Always pass `user_id` when access
control is enabled.

### 5. `cognidb/security/query_parser.py` is removed

The `sqlparse`-tokenizer table/statement extraction path is gone. Any direct
imports of `query_parser` must move to `cognidb.security.sql_guard` (`analyze`,
`extract_table_refs`, `primary_operation`), which is now the single source of
parsing truth and fails closed on parse errors instead of best-effort tokenizing.

### 6. Version and `requires-python`

The package version is now `4.0.0`, and CI/tooling target Python 3.10–3.13
(`requires-python >= 3.10`).

## Not changed

- `StatementPolicy` (read mode default, write mode DML-only opt-in, DDL always
  forbidden, multi-statement second opt-in) is unchanged.
- Table/column allowlist shapes (`AccessController`) are unchanged; only the
  fail-closed behavior on missing identity is new (see #4).
- Supported dialects remain SQLite, PostgreSQL, MySQL.

## Checklist

- [ ] Either implement `generate_intent` on your generator, or set
      `generation_mode="free_form", allow_dangerous_sql=True` explicitly.
- [ ] Update any direct `render_sql(intent)` calls to `render_sql(intent, dialect=...)`
      and unpack `RenderedSQL(sql, params)`.
- [ ] Replace any `cognidb.security.query_parser` imports with `cognidb.security.sql_guard`.
- [ ] Always pass `user_id` to `pipeline.run(...)` when `enable_access_control=True`.
- [ ] Re-run your adversarial/security tests — the AST guard rejects some
      constructs the old regex/`sqlparse` guard let through as false negatives,
      and (rarely) fail-closed heuristics may differ from the old text-based
      tautology denylist.
