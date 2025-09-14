"""Core interfaces for CogniDB components."""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
from .query_intent import QueryIntent


class DatabaseDriver(ABC):
    """Abstract base class for database drivers."""
    
    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the database."""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Close the database connection."""
        pass
    
    @abstractmethod
    def execute_native_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a native query with parameters.
        
        Args:
            query: Native query string with parameter placeholders
            params: Parameter values for the query
            
        Returns:
            List of result rows as dictionaries
        """
        pass
    
    @abstractmethod
    def fetch_schema(self) -> Dict[str, Dict[str, str]]:
        """
        Fetch database schema.
        
        Returns:
            Dictionary mapping table names to column info:
            {
                'table_name': {
                    'column_name': 'data_type',
                    ...
                },
                ...
            }
        """
        pass
    
    @abstractmethod
    def validate_table_name(self, table_name: str) -> bool:
        """Validate that a table name exists and is safe."""
        pass
    
    @abstractmethod
    def validate_column_name(self, table_name: str, column_name: str) -> bool:
        """Validate that a column exists in the table."""
        pass
    
    @abstractmethod
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information (for debugging, minus secrets)."""
        pass
    
    @property
    @abstractmethod
    def supports_transactions(self) -> bool:
        """Whether this driver supports transactions."""
        pass
    
    @property
    @abstractmethod
    def supports_schemas(self) -> bool:
        """Whether this database supports schemas/namespaces."""
        pass


class QueryTranslator(ABC):
    """Abstract base class for query translators."""
    
    @abstractmethod
    def translate(self, query_intent: QueryIntent) -> Tuple[str, Dict[str, Any]]:
        """
        Translate a QueryIntent into a native query.
        
        Args:
            query_intent: The query intent to translate
            
        Returns:
            Tuple of (query_string, parameters_dict)
        """
        pass
    
    @abstractmethod
    def validate_intent(self, query_intent: QueryIntent) -> List[str]:
        """
        Validate that the query intent can be translated.
        
        Returns:
            List of validation errors (empty if valid)
        """
        pass
    
    @property
    @abstractmethod
    def supported_features(self) -> Dict[str, bool]:
        """
        Return supported features for this translator.
        
        Example:
            {
                'joins': True,
                'subqueries': False,
                'window_functions': True,
                'cte': False
            }
        """
        pass


class SecurityValidator(ABC):
    """Abstract base class for security validators."""
    
    @abstractmethod
    def validate_query_intent(self, query_intent: QueryIntent) -> Tuple[bool, Optional[str]]:
        """
        Validate query intent for security issues.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        pass
    
    @abstractmethod
    def validate_native_query(self, query: str) -> Tuple[bool, Optional[str]]:
        """
        Validate native query for security issues.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        pass
    
    @abstractmethod
    def sanitize_identifier(self, identifier: str) -> str:
        """Sanitize a table/column identifier."""
        pass
    
    @abstractmethod
    def sanitize_value(self, value: Any) -> Any:
        """Sanitize a parameter value."""
        pass
    
    @property
    @abstractmethod
    def allowed_operations(self) -> List[str]:
        """List of allowed query operations."""
        pass


class ResultNormalizer(ABC):
    """Abstract base class for result normalizers."""
    
    @abstractmethod
    def normalize(self, raw_results: Any) -> List[Dict[str, Any]]:
        """
        Normalize database-specific results to standard format.
        
        Args:
            raw_results: Raw results from database driver
            
        Returns:
            List of dictionaries with consistent structure
        """
        pass
    
    @abstractmethod
    def format_for_output(self, 
                         normalized_results: List[Dict[str, Any]], 
                         output_format: str = 'json') -> Any:
        """
        Format normalized results for final output.
        
        Args:
            normalized_results: Normalized result set
            output_format: One of 'json', 'csv', 'table', 'dataframe'
            
        Returns:
            Formatted results
        """
        pass


class CacheProvider(ABC):
    """Abstract base class for cache providers."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache."""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Store value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None = no expiration)
            
        Returns:
            Success status
        """
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """Clear all cached values."""
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        pass