# CogniDB Master Plan: State-of-the-Art Library + Claude for Open Source Grant

**Repo:** https://github.com/boxed-dev/cognidb  
**Profile:** https://github.com/boxed-dev  
**Document date:** 2026-07-13  
**Current tag:** `v3.0.0` (major library core on `main`)  
**Owner:** Rishabh (boxed-dev)

This is the single source of truth for:

1. What CogniDB is becoming (SoTA **library**, not a chat product)  
2. Design decisions already locked (grill + ADRs)  
3. What shipped vs what remains  
4. A **TDD execution plan** (vertical slices, no blank shooting)  
5. How to **apply and maximize odds** for Anthropic **Claude for Open Source** (6 months free Claude Max 20x)

---

# Part A — Product north star

## Mission

> Ship the **safest, simplest open-source Python library** for turning natural language into **policy-checked SQL** against real databases — with **security as the product**, not a bullet point.

## What we are not

| Not this | Why |
|---|---|
| Second Vanna (chat UI, charts, agent workspace) | Dilutes security depth; different product |
| NoSQL-first platform | SQL safety first |
| “Injection-proof forever” marketing | Dishonest; we claim **defense in depth** |
| Star-farm / fake metrics | Banned by Anthropic §7 and by integrity |

## Success definition (“perfect”)

| Horizon | Bar |
|---|---|
| **Library trust** | Install works; single pipeline path; policy enforced; tests green; honest README |
| **Niche SoTA** | Schema linking, repair, allowlists, intent mode, adversarial corpus, PG CI, published threat model |
| **Category reference** | Real dependents, external contributors, Scorecard hygiene, public benchmark |

Stars are a **side effect**, not the goal.

---

# Part B — Locked design decisions (grill)

Recorded in `CONTEXT.md` and `docs/adr/0001`–`0010`.

| # | Topic | Decision |
|---|---|---|
| 0001 | Product shape | **Library only** (no hosted chat product) |
| 0002 | Statement default | **Read mode** (SELECT / read CTE) |
| 0003 | Write mode | Opt-in **DML only** (INSERT/UPDATE/DELETE); **never DDL** |
| 0004 | Multi-statement | Never in read mode; write mode needs **second opt-in** |
| 0005 | Access control | **Table/column allowlists** by caller identity now; **row predicate hooks later** |
| 0006 | Generation | **Free-form default**; **intent mode opt-in** |
| 0007 | Schema context | **Schema linking** default; full schema fallback with **size limit**; else fail closed |
| 0008 | Repair | **At most one** automatic repair; re-check policy |
| 0009 | Dialects | **SQLite, PostgreSQL, MySQL** first-class |
| 0010 | Scope freeze | No chat UI / warehouses / Mongo for this major line |

### Glossary (short)

| Term | Meaning |
|---|---|
| **Library consumer** | Developer/system embedding CogniDB |
| **Natural-language question** | Free-text input describing desired data |
| **Generated statement** | SQL checked by statement policy before execute |
| **Secure query pipeline** | Single path: sanitize → link schema → generate → policy → allowlist → execute → (repair?) → audit |
| **Read / write mode** | Statement policy modes (see above) |
| **Caller identity** | Opaque id for allowlists + audit |
| **Defense in depth** | Policy ∧ least-privilege DB grants ∧ audit |

Full glossary: [`CONTEXT.md`](../CONTEXT.md)

---

# Part C — Current codebase status (fact)

## Already shipped (`v3.0.0`)

| Capability | Location / notes |
|---|---|
| MIT LICENSE | Detected on GitHub |
| Installable `from cognidb import CogniDB` | Package API fixed |
| `SecureQueryPipeline` | `cognidb/pipeline/secure_query.py` |
| `StatementPolicy` read/write | `cognidb/security/statement_policy.py` |
| Multi-statement double opt-in | Policy module + tests |
| DDL blocked | Pipeline + validator |
| Table allowlist enforcement | AccessController wired when enabled |
| Schema linking | `cognidb/schema/linking.py` |
| One repair attempt | Pipeline |
| SQLite / MySQL / Postgres drivers | SQLite fully testable offline |
| `FakeSQLGenerator` | Offline tests |
| CI workflow | `.github/workflows/ci.yml` |
| Tests | **22 passing** (security + unit) |
| Docs | ROADMAP, CONTEXT, ADRs, CHANGELOG, GRILL-SUMMARY |

## Gaps (do not pretend these are done)

| Gap | Why it matters | TDD status |
|---|---|---|
| **Intent mode end-to-end** | ADR 0006; free-form only in pipeline today | **Not done** — primary next TDD epic |
| **Column allowlist enforcement** | Tables checked; columns partial | Incomplete |
| **Postgres CI integration** | Production reference dialect | Missing service job |
| **PyPI 3.0.0 publish** | Registry still historical 0.2.x vs Git 3.0.0 | Release engineering |
| **Adversarial SQL corpus ≥50** | SoTA security credibility | Thin today |
| **Deterministic intent → SQL renderer** | High-assurance path | Missing as deep module |
| **Row predicate hook interface** | ADR 0005 seam | Not designed as stable port yet |
| **Threat model doc** | Honest non-goals | Missing dedicated doc |
| **Real dependents / external PRs** | Grant + ecosystem | Growth work |

---

# Part D — TDD plan (perfect, no blanks)

## Rules (non-negotiable)

1. **Red → green → (review refactor later)** — no implementation without a failing test first.  
2. **Vertical slices** — one behavior per cycle, not “write all tests then all code.”  
3. **Test at seams only** — public interfaces below; never private methods.  
4. **Independent expected values** — known SQL strings, known allowlists, known errors — not tautologies.  
5. **Domain language** from `CONTEXT.md` in test names.  
6. **No mocks of the unit under test** — fake only at ports (LLM, driver) via `FakeSQLGenerator` / SQLite / fakes.  
7. **CI must stay green** after every merged slice.

## Seams under test (confirmed)

| Seam | Public interface | Why |
|---|---|---|
| **S1 Statement policy** | `StatementPolicy` | Product law for read/write/multi-stmt |
| **S2 Secure pipeline** | `SecureQueryPipeline.run` → `QueryResult` | Only execution path |
| **S3 Access control** | `AccessController` + pipeline with `user_id` | Allowlists |
| **S4 Schema linking** | `link_schema(...)` | Context selection |
| **S5 Drivers** | `SQLiteDriver` (and later PG) | Real adapters |
| **S6 Intent path** | `render_sql(QueryIntent)` + pipeline `generation_mode=intent` | ADR 0006 |
| **S7 Package surface** | `from cognidb import …` | Consumer contract |

## Epic 0 — Baseline lock (done when green)

- [x] Policy + pipeline major tests (22)  
- [ ] Add `tests/conftest.py` shared fixtures (FakeSQLGenerator, memory SQLite)  
- [ ] Coverage gate on `cognidb/security` + `cognidb/pipeline` (fail &lt; 70%)

## Epic 1 — Intent mode (highest product leverage)

**Goal:** `generation_mode="intent"` produces SQL only via deterministic renderer after structured intent.

### Slice 1.1 — Renderer pure function (S6)

| | |
|---|---|
| **RED** | `tests/unit/test_intent_renderer.py::test_renders_simple_select` |
| **Behavior** | `QueryIntent(SELECT, tables=[users], columns=[id,name])` → exact SQL string `SELECT id, name FROM users` |
| **GREEN** | Implement `cognidb/intent/renderer.py::render_sql(intent) -> str` |
| **Done** | No LLM involved; parametrized cases for WHERE EQ, AND, LIMIT |

### Slice 1.2 — Renderer rejects DDL-shaped intents

| | |
|---|---|
| **RED** | intent with forbidden type fails with clear error |
| **GREEN** | renderer only knows SELECT (and later DML if write mode) |

### Slice 1.3 — Pipeline intent mode

| | |
|---|---|
| **RED** | `SecureQueryPipeline(..., generation_mode="intent")` with FakeIntentGenerator returns policy-checked SQL |
| **GREEN** | pipeline: NL → intent (port) → `render_sql` → `_enforce` → execute |
| **Done** | Free-form still default; intent opt-in |

### Slice 1.4 — Intent + write mode

| | |
|---|---|
| **RED** | intent INSERT only succeeds when write mode on |
| **GREEN** | renderer + policy integration |

## Epic 2 — Column allowlists (S3)

### Slice 2.1

| | |
|---|---|
| **RED** | SQL `SELECT secret FROM users` denied when columns allowlist is `{id, name}` |
| **GREEN** | extract columns + `check_column_access` in pipeline |
| **Note** | `SELECT *` policy: reject `*` when column allowlist is set (fail closed) |

## Epic 3 — Adversarial security corpus (S1/S2)

### Slice 3.1

| | |
|---|---|
| **RED** | `tests/security/corpus/test_adversarial_sql.py` loads JSON of ≥30 payloads; each must fail in read mode |
| **GREEN** | Fix any validator/pipeline holes the corpus finds (one hole = one cycle) |
| **Corpus sources** | classic SQLi, stacked queries, comment tricks, UNION, INTO OUTFILE, sleep/benchmark |

## Epic 4 — Offline E2E (S2 + S5)

### Slice 4.1

| | |
|---|---|
| **RED** | Full SQLite: create tables → FakeSQLGenerator → pipeline run → assert rows |
| **GREEN** | Example + test `tests/integration/test_sqlite_e2e.py` |

### Slice 4.2

| | |
|---|---|
| **RED** | Repair path with real SQLite error then success |
| **GREEN** | Already partially covered; harden with real DB error message |

## Epic 5 — Postgres CI (S5)

### Slice 5.1

| | |
|---|---|
| **RED** | Job fails without service; integration test skipped locally without `DATABASE_URL` |
| **GREEN** | GHA service `postgres:16` + `tests/integration/test_postgres_driver.py` |

## Epic 6 — Release engineering

### Slice 6.1

| | |
|---|---|
| **Checklist** | CHANGELOG final, tag `v3.0.0` (exists), GitHub Release notes, **PyPI upload** |
| **Verify** | `pip install cognidb==3.0.0` from clean venv imports + runs SQLite example |

## Epic 7 — Growth (not TDD code; tracked)

- [ ] 10 good-first-issues with acceptance criteria  
- [ ] One technical blog: threat model + pipeline  
- [ ] Dogfood cognidb in one of your apps (creates a real dependent)  
- [ ] External PR grind for Maintainer-track long game (100 merged/12mo) |

## Execution order (do in this sequence)

```
E0 fixtures/coverage
 → E1.1 renderer
 → E1.2 renderer safety
 → E1.3 pipeline intent mode
 → E2.1 column allowlist
 → E3.1 adversarial corpus
 → E4.1 sqlite e2e
 → E5.1 postgres CI
 → E6.1 PyPI/GitHub release
 → E7 growth + grant apply
```

**Cadence:** one slice = one PR = red commit optional + green commit. Never ship green without the red test existing in the same PR.

---

# Part E — Architecture target (reference)

```
Library consumer
       │
       ▼
   CogniDB (factory / config only)
       │
       ▼
┌──────────────────────────────────────────┐
│     SecureQueryPipeline.run(...)         │  ← primary deep interface
│  sanitize → link schema → generate       │
│  (free-form | intent→render)             │
│  → statement policy → allowlists         │
│  → execute → optional 1× repair → audit  │
└──────────────────────────────────────────┘
         │                      │
         ▼                      ▼
  DatabaseDriver            Generator port
  PG / MySQL / SQLite       Free-form LLM | Intent LLM | Fake
```

---

# Part F — Claude for Open Source grant (complete guide)

## F1. What the program is

| Item | Fact |
|---|---|
| **Official name** | Claude for Open Source |
| **Benefit** | **6 months free Claude Max 20x** (~$200/mo list ≈ **$1,200** value) |
| **Apply URL** | https://claude.com/contact-sales/claude-for-oss |
| **Alias** | https://claude.com/open-source-max |
| **Terms** | https://www.anthropic.com/claude-for-oss-terms |
| **Cap** | Up to **10,000** approved recipients (Anthropic may raise) |
| **Review** | Rolling; **no SLA** |
| **Rejection email** | **None** — they email **only if approved** |
| **Silence** | Does **not** mean rejected |
| **Duplicates** | Re-applying can get later apps **disregarded** |
| **One per person** | Multi-account = disqualify (§7) |
| **Activation** | Gift link to **GitHub-associated email**; activate within **90 days** or forfeit |
| **After 6 months** | Comp ends; prior paid plan resumes if you had one; else free |
| **Overages** | Can still bill during free Max |
| **What it is NOT** | Not API credits; not Team seats; not Claude Corps / Nonprofits |

## F2. Official eligibility (prefer Terms over blogs)

### General requirements (§2.3) — need **all**

- Natural person (not a company application)
- Age 18+ / majority
- Resident where Claude.ai is offered; not sanctioned (**India is supported**)
- GitHub account **≥ 2 years**, good standing  
  - **boxed-dev:** created **2022-10-01** → **PASS** (~3.8 years)
- Public OSS activity in last **90 days**  
  - **boxed-dev:** cognidb revived + 3.0 → **PASS** if you keep pushing
- ≥1 project under **OSI-approved license**  
  - **cognidb MIT** → **PASS**
- Not Anthropic employee/affiliate

### Maintainer Track (§2.1) — need **one**

| Criterion | Threshold | boxed-dev / cognidb (approx.) | Verdict |
|---|---|---|---|
| Dependent repos | ≥500 aggregate | ~0 public | **FAIL** |
| Dependent packages | ≥100 aggregate | ~0 | **FAIL** |
| Monthly downloads | ≥200,000 | tens–low hundreds | **FAIL** |
| Foundation committer | listed on major foundation | no | **FAIL** |
| External merged PRs / 12 mo | ≥100 | ~0 | **FAIL** |
| External contributors / 12 mo on a repo | ≥20 unique | ~1 (self) | **FAIL** |
| OpenSSF criticality | ≥0.4 | not competitive | **FAIL** |

**Substance filter:** trivial/automated activity can be disregarded even if numbers nominally hit.

### Ecosystem Impact Track (§2.2) — **your path**

If you miss §2.1, still apply if you maintain something the ecosystem **meaningfully depends on** (or will). Marketing line:

> “Don't quite fit? If you maintain something the ecosystem quietly depends on, **apply anyway** and tell us about it.”

Evaluated on: dependents, usage breadth, **criticality of function**, your role.

### Stale myths (ignore)

| Myth | Reality |
|---|---|
| Need **5,000 GitHub stars** | **Not** on current official criteria (old launch-era blogging) |
| Need **1M npm downloads** | Official bar is **200k monthly** across registries, any ecosystem |

## F3. Form fields (Terms §3.1)

1. Sign in with **GitHub OAuth** (`boxed-dev` only)  
2. Email (activation delivery — use GitHub primary you check)  
3. **How you plan to use** the subscription (brief)  
4. **Why you qualify** — **≤ 500 words** (Ecosystem applicants: ecosystem significance here)

## F4. §7 bans (never “workarounds”)

- False application claims  
- Bot/purchased stars, fake downloads, graph padding, sockpuppet contributors  
- Multi-account applications  
- Sharing/selling the Max seat  

Anthropic pulls GitHub + package registry + dependency graph data.

## F5. boxed-dev positioning (honest)

| Strength | Weakness |
|---|---|
| Account age ≥2y | No Maintainer numeric gate |
| MIT cognidb, active 3.0 work | Low downloads / 0 dependents |
| Security-first NL2SQL narrative fits AI era | Flagship was stale before revive (fixed) |
| Clear maintainer role | Few external contributors |

**Primary path:** **Ecosystem Impact** + excellent narrative + proof of **active maintenance** (releases, tests, ADRs).

## F6. Pre-apply hygiene checklist

- [x] MIT LICENSE on cognidb  
- [x] Recent public commits (3.0)  
- [x] Installable package  
- [x] CI + tests  
- [ ] Pin **cognidb** #1 on GitHub profile  
- [ ] Bio: “Maintainer of CogniDB — secure NL→SQL”  
- [ ] Confirm GitHub email inbox for activation  
- [ ] Optional: GitHub Release notes for `v3.0.0`  
- [ ] Optional: PyPI 3.0.0 so metrics match Git  
- [ ] **Apply once** — do not spam resubmit  

## F7. Ready-to-paste application text

### How you plan to use the subscription

```
I will use Claude Max 20x primarily through Claude Code as a maintainer force-multiplier on CogniDB (github.com/boxed-dev/cognidb), a security-first natural-language-to-SQL library (MIT, Python).

Concrete workflows:
1) Multi-agent security review of the SecureQueryPipeline (statement policy, allowlists, multi-statement guards, repair path).
2) TDD slices for intent-mode SQL rendering, adversarial SQL corpus, and Postgres CI.
3) Dialect coverage and property tests across SQLite, PostgreSQL, and MySQL.
4) Docs/threat-model and CONTRIBUTING so external contributors can land safely.
5) Public write-ups of reproducible Claude Code maintainer workflows for secure NL2SQL.

All of this ships as public commits, PRs, releases, and tests — converting the grant into ecosystem artifacts, not private side projects.
```

### Why you qualify (≤500 words) — Ecosystem Impact

```
I am applying under the Ecosystem Impact track as the primary maintainer of CogniDB (https://github.com/boxed-dev/cognidb, PyPI: cognidb), an open-source security-first natural-language-to-SQL library for PostgreSQL, MySQL, and SQLite.

Why this project class matters: as teams attach LLMs to production databases, failure modes include SQL injection, destructive statements, and silent data exfiltration. CogniDB’s product is the guardrail path—not a chat UI. The SecureQueryPipeline enforces read mode by default (SELECT-only), optional write mode limited to DML (never DDL), multi-statement controls, table allowlists by caller identity, schema linking, a single repair attempt with re-validation, and audit hooks. That is infrastructure for the AI-agent-on-databases wave.

Evidence of real public work (honest metrics):
• GitHub: boxed-dev/cognidb — ~215 stars, 19 forks, sole/primary maintainer
• License: MIT (OSI-approved), detected on GitHub
• Engineering: v3.0.0 major with statement policy, pipeline, SQLite/MySQL/Postgres drivers, CI, automated security tests, ADRs and domain glossary
• Account: github.com/boxed-dev since October 2022; active public OSS maintenance in the current 90-day window
• Distribution: published on PyPI as cognidb (historical versions; aligning 3.x release with Git)

I do not currently meet numeric Maintainer thresholds (500+ dependents, 200k monthly downloads, 100 external merged PRs / 12 months, 20 external contributors, foundation committer, or OpenSSF criticality ≥0.4). I am not claiming those bars. I am asking for discretionary Ecosystem Impact consideration because the value is the problem class—safe NL2SQL execution—and because I own design, releases, security posture, and roadmap.

With Claude Max 20x I will run Claude Code full-time on this OSS surface: intent-mode completion, adversarial corpora, Postgres CI, documentation, and contributor onboarding—kept public so the grant becomes ecosystem artifacts. I am happy to be listed as a Program recipient and to publish reproducible secure NL2SQL workflows.

Thank you for considering a maintainer building the boring safety layer the ecosystem needs as NL2SQL adoption grows.
```

## F8. Submission protocol

1. Finish remaining hygiene (pin, bio, optional PyPI).  
2. Open apply URL; OAuth as **`boxed-dev` only**.  
3. Paste fields above.  
4. Submit **once**.  
5. Watch GitHub email for approval only.  
6. Activate within 90 days if approved.  
7. Do **not** re-submit to “nudge.”  

## F9. Legal aggressive plays vs fraud

| Allowed | Forbidden |
|---|---|
| Ecosystem narrative + honest metrics | Fake stars/downloads/dependents |
| Hygiene, LICENSE, real releases | Multi-account apps |
| Parallel: Claude Startups API credits (if company), OpenAI/Copilot OSS | Selling/sharing Max |
| Grind 100 real external PRs for future Maintainer path | Graph padding / bot contributors |

## F10. Medium-term grant ladder (if silent)

| Rank | Path | Timeline |
|---|---|---|
| 1 | Ecosystem app after hygiene | This week |
| 2 | 100 substantive external merged PRs / 12 mo | 3–6 months |
| 3 | 20 real external contributors on cognidb | 6–12 months |
| 4 | Real reverse-deps | 6–18 months |

Silence is normal. Spam is how you lose the only clean shot.

---

# Part G — Week-by-week operating plan

| Window | Focus |
|---|---|
| **Day 0–2** | TDD Epic 1.1–1.3 (intent renderer + pipeline) |
| **Day 3–4** | Epic 2 column allowlist + Epic 3 corpus start |
| **Day 5** | Epic 4 SQLite E2E; pin profile; apply grant **once** |
| **Week 2** | Epic 5 Postgres CI; PyPI 3.0 if not done |
| **Week 3–4** | Intent write path; threat-model doc; good-first-issues |
| **Month 2–3** | Dependents, blog, external PRs, Scorecard |

---

# Part H — File map in this repo

| Path | Purpose |
|---|---|
| `CONTEXT.md` | Domain glossary |
| `docs/adr/*` | Architecture/product decisions |
| `docs/GRILL-SUMMARY.md` | Short decision list |
| `ROADMAP.md` | Long-range phases A–E |
| `CHANGELOG.md` | Release notes |
| `docs/MASTER-PLAN-SOTA-AND-CLAUDE-OSS-GRANT.md` | **This document** |
| `cognidb/pipeline/secure_query.py` | Deep execution module |
| `cognidb/security/statement_policy.py` | Read/write policy |
| `tests/` | TDD living specs |

---

# Part I — Official links (bookmark)

- Apply: https://claude.com/contact-sales/claude-for-oss  
- Terms: https://www.anthropic.com/claude-for-oss-terms  
- Supported countries: https://www.anthropic.com/supported-countries  
- CogniDB: https://github.com/boxed-dev/cognidb  
- Profile: https://github.com/boxed-dev  

---

*This document supersedes scattered notes for day-to-day decisions. Update checkboxes as TDD slices merge. Do not expand scope past ADR 0010 without a new ADR.*
