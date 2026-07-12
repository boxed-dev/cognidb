# Multi-statement: banned in read mode; second opt-in in write mode

**Status:** accepted

Read mode always enforces single-statement execution. Multi-statement batches are allowed only when (1) write mode is on and (2) the library consumer enables a separate explicit multi-statement opt-in. Defaults remain single-statement.

**Considered:** never allow multi-statement; allow in write mode with second flag; fully configurable max statements.

**Why:** preserves fail-closed defaults aligned with common NL2SQL injection defenses, while still supporting deliberate advanced consumers who need short DML batches. The second flag avoids silent widening of write mode. Implementation must keep adversarial tests for `SELECT …; DELETE …` style bypasses.
