# Supported dialects for the major line: SQLite, PostgreSQL, MySQL

**Status:** accepted

The major release line commits to three first-class SQL dialects: **SQLite** (demos and offline tests), **PostgreSQL** (production reference), and **MySQL** (kept as a full peer). Cloud warehouses and NoSQL are explicitly out of scope until statement policy, allowlists, schema linking, and repair are solid.

**Why:** SoTA library depth over dialect sprawl; matches existing drivers; warehouse auth/cost models are a different product surface.
