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
The SQL (or dialect SQL) produced from a natural-language question before or after validation.
_Avoid_: query (alone — overloaded), command, script

**Secure query pipeline**:
The single path that sanitizes input, obtains a generated statement, validates it, optionally applies access rules, executes it, and records an audit event.
_Avoid_: agent loop, chat session, workflow engine

**Read-oriented access** *(provisional — confirm in later grill)*:
The intended default mode of execution: retrieving data without mutating schema or rows, pending a hard statement-policy decision.
_Avoid_: "fully secure", injection-proof
