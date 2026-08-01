# Major-release scope freeze (SoTA library core)

**Status:** accepted for 3.x; item 5 superseded by 4.0.0 (see `CHANGELOG.md`)

For the 3.x major line, the following decisions are frozen together:

1. Library-only product (ADR 0001)
2. Read mode default; write mode opt-in DML only; no DDL (0002–0003)
3. Multi-statement only with write mode + second opt-in (0004)
4. Table/column allowlists in this line; row predicate hook later (0005)
5. ~~Free-form default + intent mode opt-in (0006)~~ — **4.0.0 reverses this:**
   intent mode is the default and free-form requires `allow_dangerous_sql=True`
   (see ADR 0006's superseded note and `docs/migration-3.x-to-4.0.md`).
6. Schema linking with limited full-schema fallback (0007)
7. At most one repair attempt (0008)
8. Dialects: SQLite, PostgreSQL, MySQL (0009)

Non-goals for this major: chat UI, charts, Mongo/Dynamo, warehouse connectors, multi-agent orchestration product.

**Why:** “State of the art” for CogniDB means strongest default-safe NL→SQL library path, not feature parity with agent platforms.
