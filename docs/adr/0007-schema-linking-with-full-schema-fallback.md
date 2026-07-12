# Schema context: linking by default, full-schema fallback with limits

**Status:** accepted

Generation receives a **schema context** per run. Default behavior is **schema linking** (select top relevant tables for the question). If linking is disabled or returns nothing useful, fall back to a **full schema dump only up to a configured size limit**; if still too large, fail closed with a clear error rather than stuffing the entire catalog into the prompt.

**Considered:** always full dump; linking only; consumer-supplied slice only; linking with limited full-schema fallback.

**Why:** SoTA text-to-SQL failures are dominated by wrong schema selection. Linking matches agentic systems; limited full dump preserves simple SQLite/demo DX; fail-closed avoids silent quality and cost collapse on large databases.
