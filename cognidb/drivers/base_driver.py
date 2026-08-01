"""Base implementation for database drivers with common functionality."""

from __future__ import annotations

import logging
import time
from abc import abstractmethod
from contextlib import contextmanager
from typing import Any

from ..core.exceptions import ConnectionError, ExecutionError, SchemaError
from ..core.interfaces import DatabaseDriver
from ..security.sanitizer import InputSanitizer

logger = logging.getLogger(__name__)


class BaseDriver(DatabaseDriver):
    """
    Base database driver with common functionality.
    
    Provides:
    - Connection management
    - Query execution with timeouts
    - Schema caching
    - Security validation
    - Error handling
    """
    
    def __init__(self, config: dict[str, Any]):
        """
        Initialize base driver.
        
        Args:
            config: Database configuration
        """
        self.config = config
        self.connection = None
        self.schema_cache = None
        self.schema_cache_time = 0
        self.schema_cache_ttl = 3600  # 1 hour
        self.sanitizer = InputSanitizer()
        self._connection_time = None
        
    @contextmanager
    def transaction(self):
        """Context manager for database transactions."""
        if not self.supports_transactions:
            yield
            return
        
        try:
            self._begin_transaction()
            yield
            self._commit_transaction()
        except Exception as e:
            self._rollback_transaction()
            raise ExecutionError(f"Transaction failed: {str(e)}") from e
    
    def execute_native_query(self, 
                           query: str, 
                           params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """
        Execute a native query with parameters.
        
        Args:
            query: Native query string with parameter placeholders
            params: Parameter values for the query
            
        Returns:
            List of result rows as dictionaries
        """
        if not self.connection:
            raise ConnectionError("Not connected to database")

        # Log query for debugging (without params for security)
        logger.debug(f"Executing query: {query[:100]}...")

        start_time = time.time()

        try:
            # Execute with timeout
            results = self._execute_with_timeout(query, params)

            # Log execution time
            execution_time = time.time() - start_time
            logger.info(f"Query executed in {execution_time:.2f}s")

            return results

        except (ExecutionError, ConnectionError):
            # Drivers already surface a generic, caller-safe message and log the
            # raw detail at debug level — never re-wrap it (that would leak the
            # underlying DB error string back to the caller).
            raise
        except Exception as e:
            # Full detail to the driver log only; the caller gets a generic
            # message so raw DB internals never leak.
            logger.debug("Query execution failed", exc_info=True)
            raise ExecutionError("query execution failed") from e
    
    @staticmethod
    def _returns_rows(query: str) -> bool:
        """Best-effort check for a row-returning statement from its leading verb.

        Drives fetch strategy (streaming cursor vs. affected-row count) without
        executing the query first. Leading parentheses (``(SELECT ...)``) are
        skipped so wrapped SELECTs are still recognised.
        """
        stripped = query.lstrip()
        while stripped.startswith("("):
            stripped = stripped[1:].lstrip()
        if not stripped:
            return False
        first = stripped.split(None, 1)[0].upper()
        return first in {
            "SELECT",
            "WITH",
            "VALUES",
            "TABLE",
            "SHOW",
            "EXPLAIN",
            "DESCRIBE",
            "DESC",
        }

    def fetch_schema(self) -> dict[str, dict[str, str]]:
        """
        Fetch database schema with caching.
        
        Returns:
            Dictionary mapping table names to column info
        """
        # Check cache
        if self.schema_cache and (time.time() - self.schema_cache_time) < self.schema_cache_ttl:
            logger.debug("Using cached schema")
            return self.schema_cache
        
        logger.info("Fetching database schema")
        
        try:
            schema = self._fetch_schema_impl()
            
            # Cache the schema
            self.schema_cache = schema
            self.schema_cache_time = time.time()
            
            logger.info(f"Schema fetched: {len(schema)} tables")
            return schema
            
        except Exception as e:
            logger.error(f"Failed to fetch schema: {str(e)}")
            raise SchemaError(f"Failed to fetch schema: {str(e)}") from e
    
    def validate_table_name(self, table_name: str) -> bool:
        """Validate that a table name exists and is safe."""
        # Sanitize the table name
        try:
            sanitized = self.sanitizer.sanitize_identifier(table_name)
        except ValueError:
            return False
        
        # Check if table exists in schema
        schema = self.fetch_schema()
        return sanitized in schema
    
    def validate_column_name(self, table_name: str, column_name: str) -> bool:
        """Validate that a column exists in the table."""
        # Validate table first
        if not self.validate_table_name(table_name):
            return False
        
        # Sanitize column name
        try:
            sanitized_column = self.sanitizer.sanitize_identifier(column_name)
        except ValueError:
            return False
        
        # Check if column exists
        schema = self.fetch_schema()
        table_columns = schema.get(table_name, {})
        return sanitized_column in table_columns
    
    def get_connection_info(self) -> dict[str, Any]:
        """Get connection information (for debugging, minus secrets)."""
        info = {
            'driver': self.__class__.__name__,
            'host': self.config.get('host', 'N/A'),
            'port': self.config.get('port', 'N/A'),
            'database': self.config.get('database', 'N/A'),
            'connected': self.connection is not None,
            'connection_time': self._connection_time,
            'schema_tables': len(self.schema_cache) if self.schema_cache else 0
        }
        
        # Add driver-specific info
        info.update(self._get_driver_info())
        
        return info
    
    def invalidate_schema_cache(self):
        """Invalidate the schema cache."""
        self.schema_cache = None
        self.schema_cache_time = 0
        logger.info("Schema cache invalidated")
    
    def ping(self) -> bool:
        """Check if connection is alive."""
        try:
            # Simple query to test connection
            self.execute_native_query("SELECT 1")
            return True
        except Exception:
            return False
    
    def reconnect(self):
        """Reconnect to the database."""
        logger.info("Attempting to reconnect")
        self.disconnect()
        self.connect()
    
    # Abstract methods to be implemented by subclasses
    
    @abstractmethod
    def _create_connection(self):
        """Create the actual database connection."""
        pass
    
    @abstractmethod
    def _close_connection(self):
        """Close the database connection."""
        pass
    
    @abstractmethod
    def _execute_with_timeout(
        self, query: str, params: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        """Execute query with timeout (implementation specific)."""
        pass
    
    @abstractmethod
    def _fetch_schema_impl(self) -> dict[str, dict[str, str]]:
        """Fetch schema implementation."""
        pass
    
    @abstractmethod
    def _begin_transaction(self):
        """Begin a transaction."""
        pass
    
    @abstractmethod
    def _commit_transaction(self):
        """Commit a transaction."""
        pass
    
    @abstractmethod
    def _rollback_transaction(self):
        """Rollback a transaction."""
        pass
    
    @abstractmethod
    def _get_driver_info(self) -> dict[str, Any]:
        """Get driver-specific information."""
        pass