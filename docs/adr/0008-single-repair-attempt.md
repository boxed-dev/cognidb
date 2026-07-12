# One automatic repair attempt per pipeline run

**Status:** accepted

When validation-after-generation is not the failure mode, but execution (or a post-check) fails with a database or dialect error, the pipeline may perform **at most one repair attempt**: prior SQL + error → model → full policy/access re-check → execute. If that fails, return the error to the library consumer. No multi-step unbounded repair loop in v2 defaults.

**Considered:** fail immediately; one repair; multi-step repair (N>1).

**Why:** matches common SoTA generate-then-repair practice for typos and minor schema mistakes while bounding cost, latency, and surprise. Every repaired statement still passes statement policy and allowlists — repair is not an escape hatch from security.
