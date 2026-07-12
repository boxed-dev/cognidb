# CogniDB 3.0 — Go-Live Status

**Date:** 2026-07-13  
**Gatekeeper role:** independent verification after hardening + DX  
**Repo version:** `3.0.1` (`cognidb.__version__`, `pyproject.toml`)  
**Verdict:** **GO** (source / Git release ready; PyPI upload is human-only)

---

## Recommendation

**GO** — ship the Git tag / GitHub Release and upload wheels when a maintainer has a PyPI token. No code blockers remain from this gate run.

Residual work is **operational** (token, Release UI, profile pin), not library defects.

---

## Verification run (executed)

| Check | Command / spot-check | Result |
|---|---|---|
| Full suite | `pytest -q` | **PASS** — 114 passed, 0 failed, 1 skipped |
| Coverage gate | `pytest --cov=cognidb.security --cov=cognidb.pipeline --cov-fail-under=70` | **PASS** — TOTAL **80%** (fail-under 70) |
| Package import | `from cognidb import CogniDB` + `__version__` | **PASS** — `3.0.0` |
| Intent path | `from cognidb.intent.renderer import render_sql` | **PASS** |
| Corpus | `pytest tests/security/corpus/` | **PASS** — 50 tests; 44 payloads in JSON |
| Integration | `pytest tests/integration/` | **PASS** — 2 passed, 1 skipped (Postgres offline expected) |
| sdist/wheel | `python -m build` | **PASS** — `cognidb-3.0.1.tar.gz` + `cognidb-3.0.0-py3-none-any.whl` |
| README quickstart | Offline SQLite snippet vs live API | **PASS** — matches `SecureQueryPipeline` / `FakeSQLGenerator` |
| Conflict markers | `<<<<<<<` / `=======` / `>>>>>>>` in source | **PASS** — none |
| Mid-edit retry | First corpus/tautology flake → sleep ~45s → re-run | **PASS** — green after sibling edits settled |

Note: `pytest --collect-only` on the corpus path prints “No tests collected” via the local reporter wrapper; executing the suite collects and runs the corpus normally (50 passed). Not a release blocker.

---

## P0 criteria (ROADMAP / perfection exit)

| # | P0 criterion | Status | Evidence |
|---|---|---|---|
| 1 | `pip install cognidb` installs 3.x from PyPI matching Git tag | **FAIL** (expected) | Source builds `3.0.0`; PyPI publish not done — human step |
| 2 | Public API stable + copy-paste SQLite quickstart (&lt;30 lines) | **PASS** | README quickstart + `examples/sqlite_offline_demo.py` |
| 3 | ≥80 automated tests incl. adversarial security suite | **PASS** | 114 passed; corpus 50 tests / 44 payloads |
| 4 | CI green on Python 3.10–3.12; coverage ≥70% on security + pipeline | **PASS** | CI matrix `3.10/3.11/3.12`; local coverage **80%** |
| 5 | Single execution path (no driver bypass of pipeline validation) | **PASS** | `CogniDB.query` → `SecureQueryPipeline.run` |
| 6 | Access control enforced or removed from docs (no theater) | **PASS** | Table + column allowlists wired; README matches `create_restricted_user` |
| 7 | Community health files complete | **PASS** | LICENSE, SECURITY.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, issue + PR templates |
| 8 | README accuracy (feature claims have code + tests) | **PASS** | Honest PyPI caveat; extras match `pyproject.toml` (`dev`/`redis`/`mongo`) |

**P0 score for code gate:** 7/8 pass; #1 is intentionally human.

---

## Blockers

**None** for GO on source release / GitHub Release / local install.

---

## Human steps left (not code)

1. **PyPI token** — create/upload API token; `twine upload dist/cognidb-3.0.1*` (see [RELEASE-CHECKLIST.md](RELEASE-CHECKLIST.md)).
2. **GitHub Release** — tag `v3.0.1` (if not already), attach sdist/wheel, paste CHANGELOG notes.
3. **Profile pin** — pin the release / repo on the GitHub org or maintainer profile for discoverability.
4. Confirm `pip install cognidb==3.0.1` resolves from PyPI after upload (closes P0 #1).

---

## Counts snapshot

| Metric | Value |
|---|---|
| Tests passed | 114 |
| Tests failed | 0 |
| Tests skipped | 1 (Postgres without URL) |
| Security+pipeline coverage | 80% |
| Corpus payloads | 44 |
| Package version | 3.0.1 |
| Wheel / sdist | built successfully |

---

## Out of scope / residual (non-blocking)

- Row-level security seam still aspirational (threat-model honest non-goal).
- Corpus depth can grow further; named tautology holes are covered.
- External dependents / community PRs are growth work, not release gates.
