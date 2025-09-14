"""Secure MySQL driver implementation."""

import time
import logging
from typing import Dict, List, Any, Optional
import mysql.connector
from mysql.connector import pooling, Error
from .base_driver import BaseDriver
from ..core.exceptions import ConnectionError, ExecutionError

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
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize MySQL driver."""
        super().__init__(config)
        self.pool = None
        
    def connect(self) -> None:
        """Establish connection to MySQL database."""
        try:
            # Prepare connection config
            pool_config = {
                'pool_name': 'cognidb_mysql_pool',
                'pool_size': self.config.get('pool_size', 5),
                'host': self.config['host'],
                'port': self.config.get('port', 3306),
                'database': self.config['database'],
                'user': self.config.get('username'),
                'password': self.config.get('password'),
                'autocommit': False,
                'raise_on_warnings': True,
                'sql_mode': 'TRADITIONAL',
                'time_zone': '+00:00',
                'connect_timeout': self.config.get('connection_timeout', 10)
            }
            
            # SSL configuration
            if self.config.get('ssl_enabled'):
                ssl_config = {}
                if self.config.get('ssl_ca_cert'):
                    ssl_config['ca'] = self.config['ssl_ca_cert']
                if self.config.get('ssl_client_cert'):
                    ssl_config['cert'] = self.config['ssl_client_cert']
                if self.config.get('ssl_client_key'):
                    ssl_config['key'] = self.config['ssl_client_key']
                pool_config['ssl_disabled'] = False
                pool_config['ssl_verify_cert'] = True
                pool_config['ssl_verify_identity'] = True
                pool_config.update(ssl_config)
            
            # Create connection pool
            self.pool = pooling.MySQLConnectionPool(**pool_config)
            
            # Test connection
            self.connection = self.pool.get_connection()
            self._connection_time = time.time()
            
            logger.info(f"Connected to MySQL database: {self.config['database']}")
            
        except Error as e:
            logger.error(f"MySQL connection failed: {str(e)}")
            raise ConnectionError(f"Failed to connect to MySQL: {str(e)}")
    
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
                            params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute query with timeout."""
        cursor = None
        
        try:
            # Get connection from pool if needed
            if not self.connection or not self.connection.is_connected():
                self.connection = self._create_connection()
            
            # Set query timeout
            timeout = self.config.get('query_timeout', 30)
            self.connection.cmd_query(f"SET SESSION MAX_EXECUTION_TIME={timeout * 1000}")
            
            # Create cursor
            cursor = self.connection.cursor(dictionary=True, buffered=True)
            
            # Execute query with parameters
            if params:
                # Convert dict params to list for MySQL
                cursor.execute(query, list(params.values()))
            else:
                cursor.execute(query)
            
            # Fetch results
            if cursor.description:
                results = cursor.fetchall()
                
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
            
        except Error as e:
            if self.connection:
                self.connection.rollback()
            raise ExecutionError(f"Query execution failed: {str(e)}")
        finally:
            if cursor:
                cursor.close()
    
    def _fetch_schema_impl(self) -> Dict[str, Dict[str, str]]:
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
    
    def _fetch_indexes(self, schema: Dict[str, Dict[str, str]], cursor):
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
    
    def _get_driver_info(self) -> Dict[str, Any]:
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
            except Exception:
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