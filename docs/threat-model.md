# CogniDB threat model

Honest security boundaries for a **security-first natural-language SQL library**.
This document describes assets, attackers, mitigations, and **non-goals**.

## Assets

| Asset | Why it matters |
|---|---|
| Caller databases | Generated SQL must not destroy schema or exfiltrate beyond policy |
| Library consumer trust | Embedders rely on read-mode defaults and fail-closed validation |
| Audit trail integrity | Pipeline runs should leave reviewable evidence of what ran |

## Attackers / abuse cases

1. **Prompt injection** — natural-language input that steers the model toward unsafe SQL.
2. **Hostile generated statements** — free-form SQL that includes SQLi idioms, stacked statements, DDL, or file/time primitives.
3. **Confused deputy** — a privileged DB role used by the library that over-grants beyond statement policy.
4. **Cross-caller access** — one caller identity reading tables/columns belonging to another when ACLs are enabled.

## Mitigations (defense in depth)

| Layer | What it does |
|---|---|
| **Statement policy** | Read mode = SELECT/CTE-shaped reads only; multi-statement forbidden; DDL always rejected |
| **Query security validator** | Forbidden keywords + injection pattern scan (comment-normalized) + parse-type checks; fail-closed on boolean tautologies (`OR/AND <literal>=<literal>`, `OR/AND TRUE`) while allowing column-vs-literal business filters |
| **Access control** | Optional table/column allowlists per caller identity |
| **Least-privilege DB grants** | Consumer must not connect as a superuser; policy is not a substitute for DB privileges |
| **Audit events** | Record mode flags, statement, success/failure for later review |
| **Adversarial corpus** | `tests/security/corpus/` regression pack (≥30 payloads must fail closed in read mode) |

## Non-goals (honest)

- CogniDB is **not** a WAF, IDS, or full SQL firewall for arbitrary client SQL outside the secure query pipeline.
- Pattern matching cannot prove absence of all obfuscated SQLi; fail-closed heuristics + DB grants remain required.
- **Tautology tradeoff:** literal-vs-literal `OR/AND` comparisons and `OR/AND TRUE` are rejected even when mathematically false (e.g. `OR 1=2`). Intentional: NL→SQL never needs that shape; prefer fail-closed over enumerating only equal pairs.
- Intent-mode / structured rendering reduces free-form risk but is a separate path; free-form still needs policy + validator.
- Row-level predicates are a designed seam, not a fully shipped product guarantee in every release line.
- Legitimate CTE/subquery-heavy analytics may be rejected when `allow_subqueries=False` (default fail-closed).

## Verification

- Unit seams: `StatementPolicy`, `QuerySecurityValidator`
- Corpus: `tests/security/corpus/test_adversarial_sql.py`
- Pipeline guards: `tests/security/test_pipeline_guards.py` (and related)
