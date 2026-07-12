# CogniDB

Domain language for a **security-first natural-language SQL library** — embeddable in applications and agents, not a standalone chat product.

## Language

**CogniDB**:
The library product: a Python package that turns a natural-language question into a validated, executed database query and returns results.
_Avoid_: app, platform, workspace, agent product

**Library consumer**:
A developer or system that depends on the CogniDB package inside their own application, service, or agent runtime.
_Avoid_: end user, customer (unless meaning the consumer's user), tenant of a CogniDB-hosted product

**Natural-language question**:
The free-text input from a library consumer (or their end user) that describes the data they want.
_Avoid_: prompt (alone), chat message, utterance

**Generated statement**:
The SQL (or dialect SQL) produced from a natural-language question and checked against statement policy before execution.
_Avoid_: query (alone — overloaded), command, script

**Secure query pipeline**:
The single path that sanitizes input, obtains a generated statement, validates it under statement policy, optionally applies access rules, executes it, and records an audit event.
_Avoid_: agent loop, chat session, workflow engine

**Statement policy**:
The rules that decide whether a generated statement may be executed (allowed operations, multi-statement rules, and mode).
_Avoid_: security level, permission (when meaning policy)

**Read mode**:
The default statement policy: only read-oriented statements (SELECT and read-only WITH/CTE forms) may execute. Mutations and DDL are rejected.
_Avoid_: safe mode, production mode

**Write mode**:
An explicit opt-in statement policy that allows row-mutating DML (INSERT, UPDATE, DELETE) in addition to read mode statements. Never the default.
_Avoid_: admin mode, full access, unsafe mode (as the official name)

**DDL**:
Schema-changing statements (CREATE, ALTER, DROP, TRUNCATE, and similar). Out of scope for both read mode and write mode; rejected by statement policy.
_Avoid_: migration (as a CogniDB feature)

**Defense in depth**:
The combination of statement policy, least-privilege database grants, and audit events. No single layer is treated as sufficient.
_Avoid_: "secure by default" as a claim without naming the layers

**Single-statement execution**:
The default rule that one pipeline run executes at most one SQL statement. Always required in read mode.
_Avoid_: batch (unqualified), script

**Multi-statement batch**:
More than one SQL statement in a single pipeline run. Forbidden in read mode. In write mode, only if the library consumer enables an additional explicit opt-in (separate from write mode itself).
_Avoid_: transaction script (as free NL batching)

**Caller identity**:
An opaque identifier supplied by the library consumer for the human or system on whose behalf a pipeline run executes (for allowlists, audit, and future row rules).
_Avoid_: user (unqualified), session, principal (unless documenting auth systems)

**Table allowlist**:
The set of tables a caller identity may reference in a generated statement. Enforced by the secure query pipeline when access control is enabled.
_Avoid_: schema filter (vague)

**Column allowlist**:
The set of columns a caller identity may reference within allowed tables. Enforced with the table allowlist when access control is enabled.
_Avoid_: field mask (alone)

**Row predicate hook**:
An extension point that may inject or require row-level filter predicates for a caller identity. Designed as a seam for a later release; not required for the v2 allowlist milestone.
_Avoid_: RLS (as if already fully shipped)

**Free-form generation**:
The generation path where the model produces a SQL string that is then checked by statement policy and access rules.
_Avoid_: raw mode (in user docs prefer "free-form")

**Intent generation**:
The generation path where the model produces a structured query intent that a deterministic renderer turns into SQL before the same policy and access checks.
_Avoid_: plan (unqualified), AST mode

**Query intent**:
A structured description of a read or write operation (targets, projections, filters, aggregations, etc.) independent of SQL dialect syntax.
_Avoid_: prompt, plan blob

**Schema context**:
The subset of database structure (tables, columns, types, relationships as available) provided to generation for a single pipeline run.
_Avoid_: full database, metadata dump (unqualified)

**Schema linking**:
Selecting which tables (and related objects) belong in schema context for a natural-language question.
_Avoid_: RAG (alone — too generic), search

**Schema size limit**:
The maximum amount of schema context that may be sent to the model; beyond it the pipeline must link, truncate by policy, or fail closed rather than silently overstuffing the prompt.
_Avoid_: token budget (implementation detail in glossary)
