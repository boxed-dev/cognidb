# Security Policy

CogniDB is designed to keep LLM-generated SQL on a constrained path.

## Threat model (summary)

- Prompt injection influencing SQL generation
- Classic SQL injection patterns in generated/native queries
- Destructive statements (DROP/DELETE/UPDATE/UPDATE/INSERT/…)
- Over-broad data access without table/column ACLs

## Built-in controls

- SELECT-oriented allowlists (configurable)
- Forbidden keyword and injection pattern checks
- Identifier validation
- Optional table/column access control
- Audit logging hooks

## Supported databases (current)

- MySQL
- PostgreSQL

## Reporting a vulnerability

Open a private security advisory on GitHub or email the maintainer via the address on the GitHub profile. Please do not open public issues for unpatched critical vulnerabilities.
