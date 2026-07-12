# Contributing to CogniDB

Thanks for helping improve secure NL→SQL tooling.

## Setup

```bash
git clone https://github.com/boxed-dev/cognidb
cd cognidb
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Guidelines

1. Prefer small, focused PRs.
2. Add tests for security-sensitive changes under `tests/security/`.
3. Do not weaken SELECT-only defaults without discussion.
4. Keep dependencies lean — heavy ML stacks belong in optional extras.

## Good first contributions

- More security regression tests
- Docs/examples for PostgreSQL and MySQL
- SQLite driver for local demos
- CI improvements
