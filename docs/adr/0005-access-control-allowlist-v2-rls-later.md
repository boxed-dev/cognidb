# Access control: table/column allowlist in v2; row hooks later

**Status:** accepted

v2 enforces optional **table and column allowlists** keyed by **caller identity** inside the secure query pipeline when access control is enabled. Full row-level security is not the v2 deliverable; we design a **row predicate hook** seam so RLS-style injection can land in a later major without rewriting the pipeline.

**Considered:** statement policy only; allowlist only; allowlist + full RLS now; allowlist now with RLS seam later.

**Why:** SoTA systems combine statement shape checks with scope limits. Allowlists are implementable and testable against existing AccessController shapes. Full RLS is high-value but easy to get wrong; delaying implementation while reserving the seam avoids theater and rewrite cost.
