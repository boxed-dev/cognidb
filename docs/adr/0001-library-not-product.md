# Library product shape, not hosted chat product

**Status:** accepted

For the next major line of work we ship CogniDB as an **embeddable Python library** only. We do not build a first-class multi-user chat UI, charts product, or hosted workspace. Optional examples (e.g. a thin FastAPI demo) may exist for documentation, but they are not the product.

**Considered:** library-only; library + operated public demo; full product competing with Vanna-class apps.

**Why:** matches the current codebase and north star (depth in safe NL→SQL execution); avoids diluting security and packaging work into product ops; keeps the public interface small (`CogniDB` / secure query pipeline).
