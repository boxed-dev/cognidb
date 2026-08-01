"""SQLite database driver — local demos and tests without a server."""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from ..core.exceptions import ConnectionError, ExecutionError
from .base_driver import BaseDriver

logger = logging.getLogger(__name__)


class SQLiteDriver(BaseDriver):
    """SQLite adapter for CogniDB (file or :memory:)."""

    dialect = "sqlite"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        # Accept database path via database/path/host keys
        self.db_path = (
            config.get("database")
            or config.get("path")
            or config.get("host")
            or ":memory:"
        )
        self.connection: sqlite3.Connection | None = None

    def connect(self) -> None:
        try:
            if self.db_path != ":memory:":
                Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=float(self.config.get("query_timeout", 30)),
            )
            self.connection.row_factory = sqlite3.Row
            self._connection_time = time.time()
            logger.info("Connected to SQLite database: %s", self.db_path)
        except Exception as e:
            raise ConnectionError(f"Failed to connect to SQLite: {e}") from e

    def disconnect(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None
            self._connection_time = None
            logger.info("Disconnected from SQLite")

    def _create_connection(self):
        return self.connection

    def _close_connection(self):
        pass

    def _execute_with_timeout(
        self, query: str, params: Any | None = None
    ) -> list[dict[str, Any]]:
        if self.connection is None:
            raise ConnectionError("Not connected to SQLite")

        max_results = int(self.config.get("max_result_size", 10000))
        timeout = float(self.config.get("query_timeout", 30))

        # sqlite3's connect(timeout=...) is only the busy/lock wait, not an
        # execution-time bound. A watchdog thread calls connection.interrupt()
        # after `timeout` seconds so a runaway query (e.g. a huge recursive CTE
        # or cartesian product) is aborted instead of pinning a core forever.
        done = threading.Event()

        def _watchdog() -> None:
            if not done.wait(timeout):
                conn = self.connection
                if conn is not None:
                    try:
                        conn.interrupt()
                    except Exception:  # noqa: S110  # pragma: no cover - watchdog abort best-effort
                        pass

        watcher = threading.Thread(
            target=_watchdog, name="sqlite-query-watchdog", daemon=True
        )
        watcher.start()

        cur = None
        try:
            cur = self.connection.cursor()
            # Bind via the DBAPI — params may be a sequence (?) or mapping
            # (:name); values are never string-formatted into the SQL.
            if params is not None:
                cur.execute(query, params)
            else:
                cur.execute(query)
            if cur.description:
                cols = [d[0] for d in cur.description]
                # Stream rows and stop one past the cap: memory is bounded to
                # the cap even for an effectively unbounded result set. We never
                # fetchall() — that was the DoS.
                rows = cur.fetchmany(max_results + 1)
                if len(rows) > max_results:
                    logger.warning(
                        "Result truncated to max_result_size=%d rows", max_results
                    )
                    rows = rows[:max_results]
                return [dict(zip(cols, row, strict=False)) for row in rows]
            self.connection.commit()
            return [{"affected_rows": cur.rowcount}]
        except Exception as e:
            try:
                self.connection.rollback()
            except Exception:  # noqa: S110  # pragma: no cover - rollback best-effort
                pass
            # Full detail to the driver log only; the caller gets a generic
            # message so raw DB internals never leak.
            logger.debug("SQLite execution failed: %s", e, exc_info=True)
            raise ExecutionError("query execution failed") from e
        finally:
            done.set()
            watcher.join(timeout=timeout + 1)
            if cur is not None:
                try:
                    cur.close()
                except Exception:  # noqa: S110  # pragma: no cover - cursor close best-effort
                    pass

    def _fetch_schema_impl(self) -> dict[str, dict[str, str]]:
        if self.connection is None:
            raise ConnectionError("Not connected")
        cur = self.connection.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = [r[0] for r in cur.fetchall()]
        schema: dict[str, dict[str, str]] = {}
        for table in tables:
            # table names from sqlite_master are trusted identifiers
            cur.execute(f'PRAGMA table_info("{table}")')
            cols = cur.fetchall()
            schema[table] = {c[1]: c[2] for c in cols}
        return schema

    def supports_transactions(self) -> bool:
        return True

    def supports_schemas(self) -> bool:
        return False

    def _get_driver_info(self) -> dict[str, Any]:
        return {"driver": "sqlite", "path": self.db_path, "sqlite_version": sqlite3.sqlite_version}

    def _begin_transaction(self) -> None:
        if self.connection:
            self.connection.execute("BEGIN")

    def _commit_transaction(self) -> None:
        if self.connection:
            self.connection.commit()

    def _rollback_transaction(self) -> None:
        if self.connection:
            self.connection.rollback()
