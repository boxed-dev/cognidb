"""Secure PostgreSQL driver implementation."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

import psycopg2
from psycopg2 import DatabaseError, OperationalError, extras, sql
from psycopg2.extensions import ISOLATION_LEVEL_READ_COMMITTED

from ..core.exceptions import ConnectionError, ExecutionError
from .base_driver import BaseDriver

logger = logging.getLogger(__name__)


class PostgreSQLDriver(BaseDriver):
    """
    PostgreSQL database driver with security enhancements.
    
    Features:
    - Connection pooling with pgbouncer support
    - Parameterized queries with proper escaping
    - SSL/TLS enforcement
    - Statement timeout enforcement
    - Prepared statements
    - EXPLAIN ANALYZE integration
    """
    
    def __init__(self, config: dict[str, Any]):
        """Initialize PostgreSQL driver."""
        super().__init__(config)
        self.pool = None
        self._prepared_statements = {}
        
    def _connect_params(self) -> dict[str, Any]:
        """Assemble psycopg2 connect kwargs with TLS and timeouts enforced.

        TLS defaults to ``sslmode=verify-full`` (full hostname + chain
        verification) and is *never* silently downgraded — a caller must set an
        explicit ``sslmode`` in config to relax it. ``statement_timeout`` is
        pushed server-side via the ``options`` startup parameter.
        """
        query_timeout = self.config.get('query_timeout', 30)
        params: dict[str, Any] = {
            'host': self.config.get('host'),
            'port': self.config.get('port', 5432),
            'database': self.config.get('database'),
            'user': self.config.get('username'),
            'password': self.config.get('password'),
            'connect_timeout': self.config.get('connection_timeout', 10),
            'application_name': 'CogniDB',
            'options': f"-c statement_timeout={query_timeout}s",
            # Fail closed on TLS: full verification unless explicitly overridden.
            'sslmode': self.config.get('sslmode', 'verify-full'),
        }

        # Root CA — accept the new `sslrootcert` key and the legacy
        # `ssl_ca_cert` alias; either wires the trust anchor (no downgrade).
        sslrootcert = self.config.get('sslrootcert') or self.config.get('ssl_ca_cert')
        if sslrootcert:
            params['sslrootcert'] = sslrootcert
        if self.config.get('ssl_client_cert'):
            params['sslcert'] = self.config['ssl_client_cert']
        if self.config.get('ssl_client_key'):
            params['sslkey'] = self.config['ssl_client_key']

        return params

    def connect(self) -> None:
        """Establish connection to PostgreSQL database."""
        try:
            conn_params = self._connect_params()

            # Create connection pool
            self.pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=self.config.get('pool_size', 5),
                **conn_params
            )
            
            # Test connection
            self.connection = self.pool.getconn()
            self.connection.set_isolation_level(ISOLATION_LEVEL_READ_COMMITTED)
            self._connection_time = time.time()
            
            # Set additional session parameters
            with self.connection.cursor() as cursor:
                cursor.execute("SET TIME ZONE 'UTC'")
                cursor.execute("SET lock_timeout = '5s'")
                cursor.execute("SET idle_in_transaction_session_timeout = '60s'")
            
            self.connection.commit()
            
            logger.info(f"Connected to PostgreSQL database: {self.config['database']}")
            
        except (OperationalError, DatabaseError) as e:
            logger.error(f"PostgreSQL connection failed: {str(e)}")
            raise ConnectionError(f"Failed to connect to PostgreSQL: {str(e)}") from e
    
    def disconnect(self) -> None:
        """Close the database connection."""
        if self.connection:
            try:
                # Clear prepared statements
                for stmt_name in self._prepared_statements:
                    try:
                        with self.connection.cursor() as cursor:
                            cursor.execute(f"DEALLOCATE {stmt_name}")
                    except Exception:  # noqa: S110 - best-effort prepared-statement cleanup on disconnect
                        pass
                
                self._prepared_statements.clear()
                
                # Return connection to pool
                if self.pool:
                    self.pool.putconn(self.connection)
                
                logger.info("Disconnected from PostgreSQL database")
                
            except Exception as e:
                logger.error(f"Error closing connection: {str(e)}")
            finally:
                self.connection = None
                self._connection_time = None
        
        # Close the pool
        if self.pool:
            self.pool.closeall()
            self.pool = None
    
    def _create_connection(self):
        """Get connection from pool."""
        if not self.pool:
            raise ConnectionError("Connection pool not initialized")
        return self.pool.getconn()
    
    def _close_connection(self):
        """Return connection to pool."""
        if self.connection and self.pool:
            self.pool.putconn(self.connection)
    
    def _execute_with_timeout(self,
                            query: str,
                            params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute a query, streaming row-returning results to the cap.

        Row-returning statements run through a *server-side named cursor* so the
        backend holds the result set and we pull it incrementally with
        ``fetchmany(cap + 1)`` — this kills the ``fetchall()``-then-slice DoS at
        the fetch, not the slice. Non-row-returning statements use an ordinary
        client cursor and report ``affected_rows``.
        """
        cursor = None
        max_results = int(self.config.get('max_result_size', 10000))

        try:
            # Ensure we have a valid connection
            if not self.connection or self.connection.closed:
                self.connection = self._create_connection()

            if self._returns_rows(query):
                # Server-side (named) cursor: the result set never fully
                # materialises client-side.
                name = f"cognidb_ss_{uuid.uuid4().hex}"
                cursor = self.connection.cursor(
                    name=name, cursor_factory=extras.RealDictCursor
                )
                cursor.itersize = max_results
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
                return [dict(row) for row in rows]

            # Non-row-returning: ordinary client cursor + affected-row count.
            cursor = self.connection.cursor(cursor_factory=extras.RealDictCursor)
            if params is not None:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            self.connection.commit()
            return [{'affected_rows': cursor.rowcount}]

        except Exception as e:
            try:
                if self.connection:
                    self.connection.rollback()
            except Exception:  # noqa: S110  # pragma: no cover - rollback best-effort
                pass
            # Full detail to the driver log only; the caller gets a generic
            # message so raw DB internals never leak.
            logger.debug("PostgreSQL execution failed: %s", e, exc_info=True)
            raise ExecutionError("query execution failed") from e
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:  # noqa: S110  # pragma: no cover - cursor close best-effort
                    pass
    
    def execute_prepared(self, 
                        name: str,
                        query: str,
                        params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute a prepared statement for better performance."""
        cursor = None
        
        try:
            cursor = self.connection.cursor(cursor_factory=extras.RealDictCursor)
            
            # Prepare statement if not already prepared
            if name not in self._prepared_statements:
                cursor.execute(f"PREPARE {name} AS {query}")
                self._prepared_statements[name] = query
            
            # Execute prepared statement
            if params:
                execute_query = sql.SQL("EXECUTE {} ({})").format(
                    sql.Identifier(name),
                    sql.SQL(', ').join(sql.Placeholder() * len(params))
                )
                cursor.execute(execute_query, list(params.values()))
            else:
                cursor.execute(f"EXECUTE {name}")
            
            # Fetch results
            if cursor.description:
                return [dict(row) for row in cursor.fetchall()]
            else:
                self.connection.commit()
                return [{'affected_rows': cursor.rowcount}]
            
        except Exception as e:
            if self.connection:
                self.connection.rollback()
            raise ExecutionError(f"Prepared statement execution failed: {str(e)}") from e
        finally:
            if cursor:
                cursor.close()
    
    def explain_query(self, query: str, analyze: bool = False) -> dict[str, Any]:
        """Get query execution plan."""
        explain_query = f"EXPLAIN {'ANALYZE' if analyze else ''} {query}"
        
        try:
            results = self._execute_with_timeout(explain_query)
            return {
                'plan': results,
                'query': query
            }
        except Exception as e:
            raise ExecutionError(f"Failed to explain query: {str(e)}") from e
    
    def _fetch_schema_impl(self) -> dict[str, dict[str, str]]:
        """Fetch PostgreSQL schema using information_schema."""
        query = """
        SELECT 
            t.table_name,
            c.column_name,
            c.data_type,
            c.character_maximum_length,
            c.numeric_precision,
            c.numeric_scale,
            c.is_nullable,
            c.column_default,
            tc.constraint_type
        FROM information_schema.tables t
        JOIN information_schema.columns c 
            ON t.table_schema = c.table_schema 
            AND t.table_name = c.table_name
        LEFT JOIN information_schema.key_column_usage kcu
            ON c.table_schema = kcu.table_schema
            AND c.table_name = kcu.table_name
            AND c.column_name = kcu.column_name
        LEFT JOIN information_schema.table_constraints tc
            ON kcu.constraint_schema = tc.constraint_schema
            AND kcu.constraint_name = tc.constraint_name
        WHERE t.table_schema = 'public'
            AND t.table_type = 'BASE TABLE'
        ORDER BY t.table_name, c.ordinal_position
        """
        
        cursor = None
        try:
            cursor = self.connection.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute(query)
            
            schema = {}
            for row in cursor:
                table_name = row['table_name']
                if table_name not in schema:
                    schema[table_name] = {}
                
                # Build column type
                col_type = row['data_type']
                if row['character_maximum_length']:
                    col_type += f"({row['character_maximum_length']})"
                elif row['numeric_precision']:
                    col_type += f"({row['numeric_precision']}"
                    if row['numeric_scale']:
                        col_type += f",{row['numeric_scale']}"
                    col_type += ")"
                
                if row['is_nullable'] == 'NO':
                    col_type += ' NOT NULL'
                if row['constraint_type'] == 'PRIMARY KEY':
                    col_type += ' PRIMARY KEY'
                if row['column_default']:
                    col_type += ' DEFAULT'
                
                schema[table_name][row['column_name']] = col_type
            
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
            tablename,
            indexname,
            indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
            AND indexname NOT LIKE '%_pkey'
        ORDER BY tablename, indexname
        """
        
        cursor.execute(query)
        
        for row in cursor:
            table_name = row['tablename']
            if table_name in schema:
                index_key = f"{table_name}_indexes"
                if index_key not in schema:
                    schema[index_key] = []
                schema[index_key].append(f"{row['indexname']}")
    
    def _begin_transaction(self):
        """Begin a transaction."""
        # PostgreSQL starts transaction automatically
        pass
    
    def _commit_transaction(self):
        """Commit a transaction."""
        self.connection.commit()
    
    def _rollback_transaction(self):
        """Rollback a transaction."""
        self.connection.rollback()
    
    def _get_driver_info(self) -> dict[str, Any]:
        """Get PostgreSQL-specific information."""
        info = {
            'server_version': None,
            'connection_id': None,
            'current_schema': None,
            'encoding': None
        }
        
        if self.connection and not self.connection.closed:
            try:
                cursor = self.connection.cursor()
                cursor.execute("""
                    SELECT 
                        version(),
                        pg_backend_pid(),
                        current_schema(),
                        pg_encoding_to_char(encoding)
                    FROM pg_database
                    WHERE datname = current_database()
                """)
                result = cursor.fetchone()
                info['server_version'] = result[0]
                info['connection_id'] = result[1]
                info['current_schema'] = result[2]
                info['encoding'] = result[3]
                cursor.close()
            except Exception:  # noqa: S110 - server metadata is optional; absence is non-fatal
                pass
        
        return info
    
    @property
    def supports_transactions(self) -> bool:
        """PostgreSQL supports transactions."""
        return True
    
    @property
    def supports_schemas(self) -> bool:
        """PostgreSQL supports schemas."""
        return True