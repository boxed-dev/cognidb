"""Secure PostgreSQL driver implementation."""

import time
import logging
from typing import Dict, List, Any, Optional
import psycopg2
from psycopg2 import pool, sql, extras, OperationalError, DatabaseError
from psycopg2.extensions import ISOLATION_LEVEL_READ_COMMITTED
from .base_driver import BaseDriver
from ..core.exceptions import ConnectionError, ExecutionError

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
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize PostgreSQL driver."""
        super().__init__(config)
        self.pool = None
        self._prepared_statements = {}
        
    def connect(self) -> None:
        """Establish connection to PostgreSQL database."""
        try:
            # Prepare connection config
            conn_params = {
                'host': self.config['host'],
                'port': self.config.get('port', 5432),
                'database': self.config['database'],
                'user': self.config.get('username'),
                'password': self.config.get('password'),
                'connect_timeout': self.config.get('connection_timeout', 10),
                'application_name': 'CogniDB',
                'options': f"-c statement_timeout={self.config.get('query_timeout', 30)}s"
            }
            
            # SSL configuration
            if self.config.get('ssl_enabled', True):
                conn_params['sslmode'] = 'require'
                if self.config.get('ssl_ca_cert'):
                    conn_params['sslrootcert'] = self.config['ssl_ca_cert']
                if self.config.get('ssl_client_cert'):
                    conn_params['sslcert'] = self.config['ssl_client_cert']
                if self.config.get('ssl_client_key'):
                    conn_params['sslkey'] = self.config['ssl_client_key']
            
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
            raise ConnectionError(f"Failed to connect to PostgreSQL: {str(e)}")
    
    def disconnect(self) -> None:
        """Close the database connection."""
        if self.connection:
            try:
                # Clear prepared statements
                for stmt_name in self._prepared_statements:
                    try:
                        with self.connection.cursor() as cursor:
                            cursor.execute(f"DEALLOCATE {stmt_name}")
                    except Exception:
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
                            params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute query with timeout and proper parameterization."""
        cursor = None
        
        try:
            # Ensure we have a valid connection
            if not self.connection or self.connection.closed:
                self.connection = self._create_connection()
            
            # Create cursor with RealDictCursor for dict results
            cursor = self.connection.cursor(cursor_factory=extras.RealDictCursor)
            
            # Execute query with parameters
            if params:
                # Use psycopg2's parameter substitution
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Handle results
            if cursor.description:
                results = cursor.fetchall()
                
                # Convert RealDictRow to regular dict
                results = [dict(row) for row in results]
                
                # Apply result size limit
                max_results = self.config.get('max_result_size', 10000)
                if len(results) > max_results:
                    logger.warning(f"Result truncated from {len(results)} to {max_results} rows")
                    results = results[:max_results]
                
                return results
            else:
                # For non-SELECT queries
                self.connection.commit()
                return [{'affected_rows': cursor.rowcount}]
            
        except (OperationalError, DatabaseError) as e:
            if self.connection:
                self.connection.rollback()
            raise ExecutionError(f"Query execution failed: {str(e)}")
        finally:
            if cursor:
                cursor.close()
    
    def execute_prepared(self, 
                        name: str,
                        query: str,
                        params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
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
            raise ExecutionError(f"Prepared statement execution failed: {str(e)}")
        finally:
            if cursor:
                cursor.close()
    
    def explain_query(self, query: str, analyze: bool = False) -> Dict[str, Any]:
        """Get query execution plan."""
        explain_query = f"EXPLAIN {'ANALYZE' if analyze else ''} {query}"
        
        try:
            results = self._execute_with_timeout(explain_query)
            return {
                'plan': results,
                'query': query
            }
        except Exception as e:
            raise ExecutionError(f"Failed to explain query: {str(e)}")
    
    def _fetch_schema_impl(self) -> Dict[str, Dict[str, str]]:
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
    
    def _fetch_indexes(self, schema: Dict[str, Dict[str, str]], cursor):
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
    
    def _get_driver_info(self) -> Dict[str, Any]:
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
            except Exception:
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