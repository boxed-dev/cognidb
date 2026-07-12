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
