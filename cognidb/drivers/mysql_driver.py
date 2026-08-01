"""Secure MySQL driver implementation."""

from __future__ import annotations

import logging
import time
from typing import Any

from mysql.connector import Error, pooling

from ..core.exceptions import ConnectionError, ExecutionError
from .base_driver import BaseDriver

logger = logging.getLogger(__name__)


class MySQLDriver(BaseDriver):
    """
    MySQL database driver with security enhancements.
    
    Features:
    - Connection pooling
    - Parameterized queries only
    - SSL/TLS support
    - Query timeout enforcement
    - Automatic reconnection
    """
    
    def __init__(self, config: dict[str, Any]):
        """Initialize MySQL driver."""
        super().__init__(config)
        self.pool = None
        
    def _pool_config(self) -> dict[str, Any]:
        """Assemble the connection-pool kwargs with TLS enforced when enabled.

        With SSL on we require a verified certificate *and* hostname identity
        (``ssl_verify_identity``) — no silent downgrade to an unverified channel.
        With SSL off the connection is cleanly marked ``ssl_disabled`` so the
        state is explicit rather than implied.
        """
        config: dict[str, Any] = {
            'pool_name': 'cognidb_mysql_pool',
            'pool_size': self.config.get('pool_size', 5),
            'host': self.config.get('host'),
            'port': self.config.get('port', 3306),
            'database': self.config.get('database'),
            'user': self.config.get('username'),
            'password': self.config.get('password'),
            'autocommit': False,
            'raise_on_warnings': True,
            'sql_mode': 'TRADITIONAL',
            'time_zone': '+00:00',
            'connect_timeout': self.config.get('connection_timeout', 10),
        }

        if self.config.get('ssl_enabled'):
            config['ssl_disabled'] = False
            config['ssl_verify_cert'] = True
            config['ssl_verify_identity'] = True
            if self.config.get('ssl_ca_cert'):
                config['ca'] = self.config['ssl_ca_cert']
            if self.config.get('ssl_client_cert'):
                config['cert'] = self.config['ssl_client_cert']
            if self.config.get('ssl_client_key'):
                config['key'] = self.config['ssl_client_key']
        else:
            config['ssl_disabled'] = True

        return config

    def connect(self) -> None:
        """Establish connection to MySQL database."""
        try:
            pool_config = self._pool_config()

            # Create connection pool
            self.pool = pooling.MySQLConnectionPool(**pool_config)
            
            # Test connection
            self.connection = self.pool.get_connection()
            self._connection_time = time.time()
            
            logger.info(f"Connected to MySQL database: {self.config['database']}")
            
        except Error as e:
            logger.error(f"MySQL connection failed: {str(e)}")
            raise ConnectionError(f"Failed to connect to MySQL: {str(e)}") from e
    
    def disconnect(self) -> None:
        """Close the database connection."""
        if self.connection:
            try:
                self.connection.close()
                logger.info("Disconnected from MySQL database")
            except Error as e:
                logger.error(f"Error closing connection: {str(e)}")
            finally:
                self.connection = None
                self._connection_time = None
    
    def _create_connection(self):
        """Get connection from pool."""
        if not self.pool:
            raise ConnectionError("Connection pool not initialized")
        return self.pool.get_connection()
    
    def _close_connection(self):
        """Return connection to pool."""
        if self.connection:
            self.connection.close()
    
    def _execute_with_timeout(self,
                            query: str,
                            params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute a query, streaming row-returning results to the cap.

        Row-returning statements use an *unbuffered* (streaming) cursor plus a
        session ``MAX_EXECUTION_TIME`` bound, and are pulled with
        ``fetchmany(cap + 1)`` — the result set is never fully materialised, so
        the ``fetchall()``-then-slice DoS is killed at the fetch. Params are
        handed to ``cursor.execute`` unchanged (DBAPI binding, never formatted).
        """
        cursor = None
        max_results = int(self.config.get('max_result_size', 10000))

        try:
            # Get connection from pool if needed
            if not self.connection or not self.connection.is_connected():
                self.connection = self._create_connection()

            if self._returns_rows(query):
                # MAX_EXECUTION_TIME (ms) bounds SELECT runtime server-side.
                timeout = int(self.config.get('query_timeout', 30))
                self.connection.cmd_query(
                    f"SET SESSION MAX_EXECUTION_TIME={timeout * 1000}"
                )

                # Unbuffered cursor: rows stream from the server on demand.
                cursor = self.connection.cursor(dictionary=True, buffered=False)
                if params is not None:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)

                # Pull one past the cap so truncation is detectable, never more.
                rows = cursor.fetchmany(max_results + 1)
                if len(rows) > max_results:
                    logger.warning(
                        "Result truncated to max_result_size=%d rows", max_results
                    )
                    rows = rows[:max_results]
                return list(rows)

            # Non-row-returning: buffered cursor + affected-row count.
            cursor = self.connection.cursor(dictionary=True, buffered=True)
            if params is not None:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            self.connection.commit()
            return [{'affected_rows': cursor.rowcount}]

        except Error as e:
            try:
                if self.connection:
                    self.connection.rollback()
            except Exception:  # noqa: S110  # pragma: no cover - rollback best-effort
                pass
            # Full detail to the driver log only; the caller gets a generic
            # message so raw DB internals never leak.
            logger.debug("MySQL execution failed: %s", e, exc_info=True)
            raise ExecutionError("query execution failed") from e
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:  # noqa: S110  # pragma: no cover - cursor close best-effort
                    pass
    
    def _fetch_schema_impl(self) -> dict[str, dict[str, str]]:
        """Fetch MySQL schema using INFORMATION_SCHEMA."""
        query = """
        SELECT 
            TABLE_NAME,
            COLUMN_NAME,
            DATA_TYPE,
            IS_NULLABLE,
            COLUMN_KEY,
            COLUMN_DEFAULT,
            EXTRA
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s
        ORDER BY TABLE_NAME, ORDINAL_POSITION
        """
        
        cursor = None
        try:
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(query, (self.config['database'],))
            
            schema = {}
            for row in cursor:
                table_name = row['TABLE_NAME']
                if table_name not in schema:
                    schema[table_name] = {}
                
                # Build column info
                col_type = row['DATA_TYPE']
                if row['IS_NULLABLE'] == 'NO':
                    col_type += ' NOT NULL'
                if row['COLUMN_KEY'] == 'PRI':
                    col_type += ' PRIMARY KEY'
                if row['EXTRA']:
                    col_type += f" {row['EXTRA']}"
                
                schema[table_name][row['COLUMN_NAME']] = col_type
            
            # Fetch indexes
            self._fetch_indexes(schema, cursor)
            
            return schema
            
        finally:
            if cursor:
                cursor.close()
    
    def _fetch_indexes(self, schema: dict[str, dict[str, str]], cursor):
        """Fetch index information."""
        query = """
        SELECT 
            TABLE_NAME,
            INDEX_NAME,
            GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) as COLUMNS
        FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = %s AND INDEX_NAME != 'PRIMARY'
        GROUP BY TABLE_NAME, INDEX_NAME
        """
        
        cursor.execute(query, (self.config['database'],))
        
        for row in cursor:
            table_name = row['TABLE_NAME']
            if table_name in schema:
                index_key = f"{table_name}_indexes"
                if index_key not in schema:
                    schema[index_key] = []
                schema[index_key].append(f"{row['INDEX_NAME']} ({row['COLUMNS']})")
    
    def _begin_transaction(self):
        """Begin a transaction."""
        self.connection.start_transaction()
    
    def _commit_transaction(self):
        """Commit a transaction."""
        self.connection.commit()
    
    def _rollback_transaction(self):
        """Rollback a transaction."""
        self.connection.rollback()
    
    def _get_driver_info(self) -> dict[str, Any]:
        """Get MySQL-specific information."""
        info = {
            'server_version': None,
            'connection_id': None,
            'character_set': None
        }
        
        if self.connection and self.connection.is_connected():
            try:
                cursor = self.connection.cursor()
                cursor.execute("SELECT VERSION(), CONNECTION_ID(), @@character_set_database")
                result = cursor.fetchone()
                info['server_version'] = result[0]
                info['connection_id'] = result[1]
                info['character_set'] = result[2]
                cursor.close()
            except Exception:  # noqa: S110 - server metadata is optional; absence is non-fatal
                pass
        
        return info
    
    @property
    def supports_transactions(self) -> bool:
        """MySQL supports transactions."""
        return True
    
    @property
    def supports_schemas(self) -> bool:
        """MySQL supports schemas (databases)."""
        return True