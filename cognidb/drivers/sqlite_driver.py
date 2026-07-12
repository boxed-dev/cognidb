"""SQLite database driver — local demos and tests without a server."""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.exceptions import ConnectionError, ExecutionError
from .base_driver import BaseDriver

logger = logging.getLogger(__name__)


class SQLiteDriver(BaseDriver):
    """SQLite adapter for CogniDB (file or :memory:)."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Accept database path via database/path/host keys
        self.db_path = (
            config.get("database")
            or config.get("path")
            or config.get("host")
            or ":memory:"
        )
        self.connection: Optional[sqlite3.Connection] = None

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
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        if self.connection is None:
            raise ConnectionError("Not connected to SQLite")
        try:
            cur = self.connection.cursor()
            if params:
                # sqlite uses :name or ?
                cur.execute(query, params)
            else:
                cur.execute(query)
            if cur.description:
                cols = [d[0] for d in cur.description]
                rows = cur.fetchall()
                results = [dict(zip(cols, row)) for row in rows]
                max_results = self.config.get("max_result_size", 10000)
                return results[:max_results]
            self.connection.commit()
            return [{"affected_rows": cur.rowcount}]
        except Exception as e:
            self.connection.rollback()
            raise ExecutionError(f"SQLite execution failed: {e}") from e

    def _fetch_schema_impl(self) -> Dict[str, Dict[str, str]]:
        if self.connection is None:
            raise ConnectionError("Not connected")
        cur = self.connection.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = [r[0] for r in cur.fetchall()]
        schema: Dict[str, Dict[str, str]] = {}
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

    def _get_driver_info(self) -> Dict[str, Any]:
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
