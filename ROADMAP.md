# Roadmap

CogniDB stays a **security-first NL→SQL library** — depth in the validation pipeline, not chat/BI product breadth.

## Near term

- Publish `cognidb==3.0.1` on PyPI (source/GitHub release already tagged)
- Deeper schema retrieval for large databases (top-k tables, not full dumps)
- Structured audit events and optional OpenTelemetry hooks
- Broader adversarial corpus and dialect golden tests

## Later

- Row-level policy hooks (caller context → forced predicates)
- Async / streaming query API
- First-class adapter for a popular agent framework (one path, done well)
- Public mini-benchmark on a curated text-to-SQL sample

## Non-goals

- Full BI chat product with charts
- Hosted fine-tuned models
- Treating NoSQL as equal to the SQL path until the SQL security story is settled

Design decisions live in [`docs/adr/`](docs/adr/) and the domain glossary in [`CONTEXT.md`](CONTEXT.md).
