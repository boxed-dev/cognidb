# Statement policy: read mode default, write mode opt-in

**Status:** accepted

Default execution uses **read mode** (SELECT / read-only CTE only). **Write mode** exists as an explicit opt-in for library consumers who need mutating statements. Write mode is never the default.

**Considered:** read-only forever; read default + write opt-in; fully consumer-configured allowlist with no strong default.

**Why:** fails closed for the common embedding case (agents and apps asking questions of data); still allows real write use cases without forking the library; matches current validator defaults while leaving a documented escape hatch.
