# CogniDB Revival → State-of-the-Art Plan

**Product north star:** The safest, simplest open-source library for turning natural language into **read-only SQL** against real databases — with security as the product, not a bullet point.

**Not the north star:** Becoming a second Vanna (agent UI, charts, enterprise chat) or PandasAI (dataframe chat). We win by **depth in the security pipeline**, not feature breadth.

| | |
|---|---|
| **Repo** | https://github.com/boxed-dev/cognidb |
| **Baseline** | v2.0.1 (`46eb8d7`) — MIT, installable API, SecureQueryPipeline, MySQL/PG/SQLite, 11 tests |
| **Stars / forks** | ~215 / 19 |
| **Plan date** | 2026-07-13 |
| **Success horizon** | 90 days to “credible SoTA niche”; 6–12 months to category reference |

---

## 0. Principles (non-negotiable)

1. **Honesty over hype** — if a driver/feature isn’t implemented, it is “planned,” not listed as shipping.
2. **Security locality** — all NL→SQL→execute paths go through one deep module (`SecureQueryPipeline`). No bypass routes.
3. **Deep modules** — small public interface, large implementation; test through the interface (see codebase-design vocabulary).
4. **Two adapters minimum for a real seam** — e.g. Postgres + SQLite for drivers; OpenAI + Anthropic (already) or + fake for LLM.
5. **Delete theater** — dead AccessController paths, empty cache, fake CLI: wire them or remove them.
6. **Legal growth only** — no bot stars/downloads; real users, real docs, real reverse-deps.

---

## 1. Current state (baseline truth)

### What already works (post-revive)

| Area | Status |
|---|---|
| MIT LICENSE | Detected on GitHub |
| Public API `from cognidb import CogniDB` | Works |
| SecureQueryPipeline | sanitize → generate → validate → multi-stmt guard → execute → audit |
| Drivers | MySQL, PostgreSQL, **SQLite** |
| CI | GitHub Actions pytest |
| Tests | 102 passed / 1 skipped (adversarial corpus, intent, allowlists, SQLite E2E) |
| Packaging | `pyproject.toml` + setuptools |

### Gaps vs state-of-the-art (peer-informed)

| Gap | Why it matters | Peer reference |
|---|---|---|
| Coverage / corpus depth | 44-payload corpus covers classic + tautology variants (`OR 2=2`, `'a'='a'`, `TRUE`); depth toward ≥50 still open | Vanna: broad tests + examples |
| Access control depth | Table + column allowlists enforced; row predicates still a seam | Vanna: user-aware filters |
| Free-form SQL still default | Intent mode is opt-in; residual injection / logic risk on raw path | Research: intent→SQL builders; DAIL-SQL few-shot |
| No schema RAG / memory | Accuracy plateaus on large schemas | Vanna: agent memory / retrieval |
| No PyPI 3.x release | Git tag `v3.0.0`; PyPI still historical 0.2.x | Modern Python packaging norms |
| README was marketing-heavy (fixed in 3.0 prep) | Trust | Honest quickstart + RELEASE-CHECKLIST |
| Zero community issues/PRs | Looks single-dev abandoned | Issue templates + good-first-issues |
| No row-level security | Enterprise pass/fail | Vanna 2.0 RLS story |
| No observability hooks | Production adoption | Lifecycle hooks / tracing |
| Heavy optional deps story messy | `requirements.txt` still lists torch-era junk | Slim core + extras |

### Honest positioning (use everywhere)

> **CogniDB** is a Python library for **secure, SELECT-oriented natural-language SQL** against PostgreSQL, MySQL, and SQLite. It prioritizes validation, allowlisting, and audit over chat UIs.

---

## 2. Definition of “perfection” (exit criteria)

Perfection is **measurable**, not vibes.

### P0 perfection (library is trustworthy)

- [ ] `pip install cognidb` installs **3.x** from PyPI matching Git tag (source/build prep done; publish needs human token)
- [x] Public API stable and documented with copy-paste quickstart (SQLite under 30 lines; `examples/sqlite_offline_demo.py`)
- [x] **≥80 automated tests**, including adversarial security suite (102 passed + corpus)
- [x] CI green on Python 3.10–3.12; coverage ≥70% on `cognidb/security` + `cognidb/pipeline` (coverage ~80% met; matrix includes 3.12)
- [ ] Single execution path: no way to hit the driver without pipeline validation
- [x] Access control either **enforced** or **removed** from docs (no theater) — table + column allowlists wired
- [x] Community health files complete: LICENSE, SECURITY, CONTRIBUTING, CODE_OF_CONDUCT, issue/PR templates
- [x] README accuracy audit (honest claims; no “PyPI published” until upload)

### P1 perfection (SoTA *in niche*)

- [ ] Schema-aware generation with **retrieval of relevant tables** (not full dump for large DBs)
- [x] Structured **QueryIntent** path optional alongside free-form SQL (deeper safety)
- [ ] Pluggable LLM port + **FakeLLM** for offline tests
- [ ] JSONL/structured audit + optional OpenTelemetry hooks
- [x] Dialect test matrix: SQLite always; Postgres via Testcontainers/docker in CI
- [x] Published security threat model + “what we don’t guarantee”
- [ ] ≥1 real external reverse-dep or documented production user
- [ ] Benchmark notebook: accuracy on a public text-to-SQL subset (Spider sample / custom mini)

### P2 perfection (category reference)

- [ ] Row-level policy hooks (user context → forced predicates)
- [ ] Streaming / async query API
- [ ] Minimal reference UI **or** first-class LangChain/LlamaIndex adapter (pick one)
- [ ] Signed releases, OpenSSF Scorecard ≥ pass on critical checks
- [ ] 20+ unique external contributors over 12 months **or** 100+ external merged PRs (maintainer track options)
- [ ] Stable semver policy + changelog automation

---

## 3. Architecture target

### Target deep modules (public)

```
┌─────────────────────────────────────────────┐
│  CogniDB  (factory / config only)           │
└───────────────────┬─────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│  SecureQueryPipeline.run(nl, user=…)        │  ← PRIMARY deep interface
│  - sanitize NL                              │
│  - retrieve schema context                  │
│  - generate SQL (LLM port)                  │
│  - validate (allowlist, multi-stmt, AST)    │
│  - apply access / RLS hooks                 │
│  - execute (driver port)                    │
│  - audit + metrics                          │
└─────────────────────────────────────────────┘
         │                        │
         ▼                        ▼
   DatabaseDriver              LLMPort
   (PG, MySQL, SQLite,…)       (OpenAI, Anthropic, Fake)
```

### Internal seams (not public API)

- `QuerySecurityValidator`, `SQLQueryParser`, `InputSanitizer`
- `PromptBuilder`, providers, `CostTracker`
- Schema retriever / embedder (future)

### Explicit non-goals (12 months)

- Full BI chat product with charts (Vanna’s lane)
- NoSQL as first-class equals until SQL path is bulletproof
- Fine-tuned foundation models hosted by us
- Claiming OpenSSF criticality ≥0.4 without real dependents

---

## 4. Phased roadmap

### Phase A — Trust foundation (Week 1)

**Goal:** Nobody can call the package “abandoned” or “broken.”

| ID | Work item | Done when | Effort |
|---|---|---|---|
| A1 | Publish **PyPI 2.0.1** + GitHub Release + changelog | `pip install cognidb==2.0.1` works | 2h |
| A2 | Rewrite README: 30-line SQLite quickstart, honest features, badges (CI, license, PyPI) | Cold user succeeds | 3h |
| A3 | Fix/delete root `__init__.py` confusion; single package story | No dual entrypoints | 1h |
| A4 | Slim `requirements.txt` to match `pyproject` core; move torch/etc out forever | Clean install &lt;1 min | 1h |
| A5 | Issue templates + PR template + CODE_OF_CONDUCT | Community health ↑ | 1h |
| A6 | Pin repo on profile; topics already set | Optics | 15m |
| A7 | Open 8–12 `good first issue` labels with acceptance criteria | External contrib funnel | 2h |
| A8 | Wire or strip AccessController (decision: **wire table allowlist**) | No dead code path | 4h |
| A9 | Expand security tests to ≥30 cases (union, comment tricks, stacked queries, case tricks) | Suite green | 4h |
| A10 | FakeLLM adapter + pipeline unit tests without network | CI fully offline for unit | 3h |

**Exit:** PyPI 2.x live, README honest, ≥40 tests, access control real or gone.

### Phase B — Security SoTA core (Weeks 2–3)

**Goal:** Best-in-class *library* security for SELECT-only NL2SQL.

| ID | Work item | Done when | Effort |
|---|---|---|---|
| B1 | AST/sqlparse allowlist: only SELECT/WITH; ban INTO OUTFILE, functions denylist | Documented policy + tests | 2d |
| B2 | Optional **QueryIntent** generation → deterministic SQL renderer | Feature flag `mode=intent\|raw` | 3–4d |
| B3 | Schema retrieval: top-k tables by embedding or name overlap | Large-schema fixture test | 2–3d |
| B4 | Cost limits enforced end-to-end (not just tracked) | Hard fail over budget | 1d |
| B5 | Audit: JSONL default + structured schema; redaction of secrets | SECURITY.md updated | 1d |
| B6 | Rate limit middleware on pipeline | Config-driven | 1d |
| B7 | Threat model doc (`docs/threat-model.md`) | Public, linked from SECURITY | 0.5d |
| B8 | Property-based tests on sanitizer/validator (Hypothesis) | CI | 1d |

**Exit:** Security policy document + adversarial suite; intent mode MVP.

### Phase C — Correctness & dialects (Weeks 3–5)

**Goal:** Results people trust.

| ID | Work item | Done when | Effort |
|---|---|---|---|
| C1 | Postgres integration tests (Testcontainers or service container) | CI job green | 2d |
| C2 | MySQL integration tests (optional nightly if heavy) | Documented | 1–2d |
| C3 | Dialect-specific prompt packs (PG vs MySQL vs SQLite) | Golden tests | 2d |
| C4 | Mini benchmark: 50–100 hand-curated NL→SQL pairs | Score tracked in `benchmarks/` | 3d |
| C5 | Explainability: always return SQL + optional plan (`EXPLAIN`) | API stable | 1d |
| C6 | Retry/repair loop: on SQL error, one LLM repair with error text | Configurable max 1–2 | 2d |

**Exit:** Benchmark baseline published; PG CI green.

### Phase D — Productization (Weeks 5–8)

**Goal:** Easy adoption → real dependents.

| ID | Work item | Done when | Effort |
|---|---|---|---|
| D1 | First-class CLI (`cognidb query "…"` with SQLite/PG URL) | Documented | 2d |
| D2 | `examples/`: SQLite demo DB + notebook | Runs in codespaces | 1d |
| D3 | LangChain **or** LlamaIndex tool wrapper (one ecosystem only first) | Example + test | 2d |
| D4 | FastAPI reference server (optional extra) | `examples/server` | 2d |
| D5 | Observability: OpenTelemetry spans around pipeline stages | Extra `otel` | 2d |
| D6 | Docs site (MkDocs or Sphinx) — API + security | GitHub Pages | 3d |
| D7 | Semantic versioning + release-please / manual CHANGELOG | v2.1, v2.2… | 1d |

**Exit:** New user to first successful query in &lt;10 minutes without reading source.

### Phase E — Ecosystem & SoTA ranking (Months 3–6)

**Goal:** Category reference for *secure* NL2SQL libraries.

| ID | Work item | Done when | Effort |
|---|---|---|---|
| E1 | Row-level security hooks: `user_context → predicate injector` | Tests with multi-tenant fixture | 1–2w |
| E2 | Async pipeline (`arun`) | Feature complete | 1w |
| E3 | Read-only DB user recipes + IaC snippets | Docs | 2d |
| E4 | Independent security review checklist / optional audit | Blog post | ongoing |
| E5 | Conference/blog deep dive: “NL2SQL threat model 2026” | Public artifact | 1w |
| E6 | Grow reverse-deps: publish adapters; dogfood in your apps | deps.dev / GitHub dependents &gt; 0 | ongoing |
| E7 | OpenSSF Scorecard fixes (branch protection, signed tags, pinned actions) | Scorecard improved | 1w |
| E8 | Contributor ladder: triage SLA 48h, monthly “contrib day” | 20 external contributors / year target | ongoing |

**Exit:** Cited as “use this if you care about SQL safety”; metrics support Ecosystem or Maintainer grant tracks honestly.

---

## 5. Milestone map

```
Week 0   ████ already done ── installable, MIT, pipeline, SQLite, 11 tests
Week 1   Phase A ── PyPI 2.x, README, access control, 40+ tests
Week 3   Phase B ── AST policy, intent mode MVP, threat model
Week 5   Phase C ── PG CI, benchmark baseline
Week 8   Phase D ── CLI, docs site, one framework adapter
Month 6  Phase E ── RLS hooks, async, dependents, Scorecard
```

### Version plan

| Version | Theme | Gates |
|---|---|---|
| **2.0.1** | Revive (current) | Install + pipeline + SQLite |
| **2.1.0** | Trust | PyPI, access control, expanded tests, FakeLLM |
| **2.2.0** | Secure core | AST policy, schema retrieval, enforced budgets |
| **2.3.0** | Correctness | Intent mode, repair loop, benchmark harness |
| **2.4.0** | Adopt | CLI, docs site, LC/LI adapter |
| **3.0.0** | SoTA niche | RLS hooks, async, stable API freeze |

---

## 6. Workstreams (parallelizable)

| Stream | Owner focus | Phases |
|---|---|---|
| **S1 Security** | Validator, AST, intent, RLS, threat model | A8–A9, B*, E1 |
| **S2 Runtime** | Pipeline, drivers, async, repair | A10, C*, E2 |
| **S3 DX** | README, docs, CLI, examples, PyPI | A1–A7, D* |
| **S4 Quality** | CI, coverage, benchmark, Scorecard | A9, C1–C4, E7 |
| **S5 Growth** | Issues, blog, adapters, dependents | A7, D3, E5–E6, E8 |

---

## 7. Testing strategy (perfection-grade)

| Layer | What | Tooling |
|---|---|---|
| Unit | Validator, sanitizer, pipeline guards, intent renderer | pytest |
| Contract | Driver interface across SQLite/PG | pytest + fixtures |
| Adversarial | Injection corpus, multi-stmt, encoding tricks | dedicated `tests/security/corpus/` |
| Integration | Real Postgres | Testcontainers / GHA services |
| Offline E2E | FakeLLM + SQLite full CogniDB | no network in CI unit job |
| Benchmark | Curated NL→SQL accuracy | `benchmarks/run.py` → JSON report |
| Mutation (later) | Security module resilience | mutmut optional |

**Rule:** New security behavior without a test is incomplete.

---

## 8. Packaging & API stability

### Public API (keep small)

```python
from cognidb import CogniDB, create_cognidb
from cognidb.pipeline import SecureQueryPipeline, QueryResult  # advanced
```

### Avoid exporting

Internal providers, parsers, cost tracker details (unless documented advanced).

### Config

- Prefer env + YAML (existing)
- Document every security flag default (safe by default: SELECT-only, no multi-stmt)

### Deprecation

- Semver: breaking changes only in 3.x
- Changelog for every release

---

## 9. Documentation plan

| Doc | Purpose |
|---|---|
| README | 60-second pitch + quickstart |
| SECURITY.md | Reporting + high-level controls |
| docs/threat-model.md | Assets, attackers, mitigations, non-goals |
| docs/architecture.md | Pipeline diagram, seams |
| docs/api.md | Public interface |
| examples/ | Runnable |
| ROADMAP.md | This file |

---

## 10. Metrics dashboard (track monthly)

| Metric | Now | 90-day target | 1-year target |
|---|---|---|---|
| PyPI monthly downloads | ~tens–low hundreds | 2k+ | 20k+ |
| GitHub dependents | 0 | ≥5 | ≥50 |
| Stars | ~215 | 500+ (organic) | 2k+ |
| Tests | 11 | 80+ | 200+ |
| Coverage (security+pipeline) | low | ≥70% | ≥85% |
| External merged PRs (12 mo) | 0 | 15+ | 100 (Maintainer gate) |
| Unique external contributors | 1 | 5+ | 20 (Community gate) |
| OpenSSF Scorecard | untracked | baseline + fix criticals | strong |

---

## 11. Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| Scope creep into “full agent platform” | Never ship depth | North star review each milestone |
| LLM cost in CI | Flaky/expensive | FakeLLM default; live LLM nightly optional |
| Overclaiming safety | Legal/reputation | Threat model non-goals; no “injection-proof” marketing |
| Single maintainer bus factor | Abandonment optics | Docs, issues, CONTRIBUTING, video walkthrough |
| Dialect bugs | User trust | PG CI + golden tests |
| Competing with Vanna head-on | Lose | Niche: secure library, not chat suite |

---

## 12. Immediate execution queue (start here)

Do in order — each is one PR:

1. **PR-A1** — Release engineering: CHANGELOG, tag `v2.0.1`, PyPI publish, GitHub Release  
2. **PR-A2** — README rewrite + badges + SQLite quickstart  
3. **PR-A3** — FakeLLM + 15 pipeline tests offline  
4. **PR-A4** — Enforce table allowlist via AccessController in pipeline  
5. **PR-A5** — Security corpus (20 adversarial SQL strings)  
6. **PR-A6** — Community templates + 10 good-first-issues  
7. **PR-B1** — AST allowlist policy module  

After PR-A1–A2: **apply Claude for Open Source** (Ecosystem) with honest metrics + “security-first NL2SQL” narrative.

---

## 13. Decision log (pre-answered)

| Decision | Choice | Rationale |
|---|---|---|
| Product shape | **Library first**, optional thin server | Depth &gt; surface area |
| UI | **No** first-class chat UI in v2 | Avoid Vanna clone |
| NoSQL | **Defer** Mongo/Dynamo | SQL safety first |
| Intent vs raw SQL | **Both**; default raw+strict validate; intent opt-in → default later | Migration path |
| Framework | **One** adapter first (LangChain *or* LlamaIndex) | Focus |
| License | Stay **MIT** | Already claimed; max adoption |
| Default DB for docs | **SQLite** | Zero infra |

---

## 14. What “state of the art” means here

State of the art for CogniDB is **not** “most stars in text-to-SQL.”

It is:

1. **Strongest default-safe execution path** among small open-source NL2SQL libraries  
2. **Best-documented threat model** and adversarial test corpus  
3. **Clean deep architecture** (pipeline + ports) others can learn from  
4. **Reproducible accuracy benchmarks** on a fixed suite  
5. **Real dependents** and external contributors  

If those five are true at month 6–12, the repo is “perfect” for its mission — even at &lt;5k stars.

---

## 15. References (peers & patterns)

- Vanna 2.0 — agent/SQL runner, user-aware security, production packaging  
- Dataherald — NL2SQL service patterns  
- PandasAI — deep single interface for data Q&A  
- Academic/practical: DAIL-SQL few-shot, Spider-style evaluation, sqlparse AST allowlists  
- Internal: `AUDIT-AND-REVIVE-PLAN.md`, architecture HTML review, codebase-design deep modules  

---

*This roadmap is the source of truth for prioritization. Update the checklist in place as PRs merge. Reject work that doesn’t move a checkbox or a metric above.*
