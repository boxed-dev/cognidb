"""Allow ``python -m benchmarks`` and ``python -m benchmarks.run``."""

from __future__ import annotations

from benchmarks.run import main

if __name__ == "__main__":
    raise SystemExit(main())
