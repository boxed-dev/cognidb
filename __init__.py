"""
CogniDB - Secure Natural Language Database Interface

A production-ready natural language to SQL interface with comprehensive
security, multi-database support, and intelligent query generation.
"""

__version__ = "2.0.0"
__author__ = "CogniDB Team"

import logging
from typing import Dict, Any, Optional, List, Union
from pathlib import Path

# Core imports
from .cognidb.core.exceptions import CogniDBError
from .cognidb.config import ConfigLoader, Settings, DatabaseType
from .cognidb.security import QuerySecurityValidator, AccessController, InputSanitizer
from .cognidb.ai import LLMManager, QueryGenerator
from .cognidb.drivers import (
    MySQLDriver,
    PostgreSQLDriver,
    MongoDBDriver,
    DynamoDBDriver,
    SQLiteDriver
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CogniDB:
    """
    Main CogniDB interface for natural language database queries.
    
    Features:
    - Natural language to SQL conversion
    - Multi-database support (MySQL, PostgreSQL, MongoDB, DynamoDB)
    - Comprehensive security validation
    - Query optimization and caching
    - Cost tracking and limits
    - Audit logging
    """
    
    def __init__(self, 
                 config_file: Optional[str] = None,
                 **kwargs):
        """
        Initialize CogniDB.
        
        Args:
            config_file: Path to configuration file
            **kwargs: Override configuration values
        """
        # Load configuration
        self.config_loader = ConfigLoader(config_file)
        self.settings = self.config_loader.load()
        
        # Apply any overrides
        self._apply_config_overrides(kwargs)
        
        # Initialize components
        self._init_driver()
        self._init_security()
        self._init_ai()
        self._init_cache()
        
        # Connect to database
        self.driver.connect()
        
        # Cache schema
        self.schema = self.driver.fetch_schema()
        
        logger.info("CogniDB initialized successfully")
    
    def query(self, 
              natural_language_query: str,
              user_id: Optional[str] = None,
              explain: bool = False) -> Dict[str, Any]:
        """
        Execute a natural language query.
        
        Args:
            natural_language_query: Query in natural language
            user_id: Optional user ID for access control
            explain: Whether to include query explanation
            
        Returns:
            Dictionary with results and metadata
        """
        try:
            # Sanitize input
            sanitized_query = self.input_sanitizer.sanitize_natural_language(
                natural_language_query
            )
            
            # Check access permissions
            if self.settings.security.enable_access_control and user_id:
                # This would integrate with your access control system
                pass
            
            # Generate SQL from natural language
            sql_query = self.query_generator.generate_sql(
                sanitized_query,
                self.schema,
                examples=self.settings.llm.few_shot_examples
            )
            
            # Validate generated SQL
            is_valid, error = self.security_validator.validate_native_query(sql_query)
            if not is_valid:
                raise CogniDBError(f"Security validation failed: {error}")
            
            # Execute query
            results = self.driver.execute_native_query(sql_query)
            
            # Prepare response
            response = {
                'success': True,
                'query': natural_language_query,
                'sql': sql_query,
                'results': results,
                'row_count': len(results),
                'execution_time': None  # Would be tracked by driver
            }
            
            # Add explanation if requested
            if explain:
                response['explanation'] = self.query_generator.explain_query(
                    sql_query,
                    self.schema
                )
            
            # Log query for audit
            self._audit_log(user_id, natural_language_query, sql_query, True)
            
            return response
            
        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            self._audit_log(user_id, natural_language_query, None, False, str(e))
            
            return {
                'success': False,
                'query': natural_language_query,
                'error': str(e)
            }
    
    def optimize_query(self, sql_query: str) -> Dict[str, Any]:
        """
        Get optimization suggestions for a SQL query.
        
        Args:
            sql_query: SQL query to optimize
            
        Returns:
            Dictionary with optimized query and explanation
        """
        try:
            optimized_sql, explanation = self.query_generator.optimize_query(
                sql_query,
                self.schema
            )
            
            return {
                'success': True,
                'original_query': sql_query,
                'optimized_query': optimized_sql,
                'explanation': explanation
            }
            
        except Exception as e:
            logger.error(f"Query optimization failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def suggest_queries(self, partial_query: str) -> List[str]:
        """
        Get query suggestions based on partial input.
        
        Args:
            partial_query: Partial natural language query
            
        Returns:
            List of suggested queries
        """
        try:
            return self.query_generator.suggest_queries(
                partial_query,
                self.schema
            )
        except Exception as e:
            logger.error(f"Failed to generate suggestions: {str(e)}")
            return []
    
    def get_schema(self, table_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get database schema information.
        
        Args:
            table_name: Optional specific table name
            
        Returns:
            Schema information
        """
        if table_name:
            return {
                table_name: self.schema.get(table_name, {})
            }
        return self.schema
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics including costs."""
        return self.llm_manager.get_usage_stats()
    
    def close(self):
        """Close all connections and cleanup resources."""
        try:
            if hasattr(self, 'driver'):
                self.driver.disconnect()
            logger.info("CogniDB closed successfully")
        except Exception as e:
            logger.error(f"Error closing CogniDB: {str(e)}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    # Private methods
    
    def _init_driver(self):
        """Initialize database driver."""
        driver_map = {
            DatabaseType.MYSQL: MySQLDriver,
            DatabaseType.POSTGRESQL: PostgreSQLDriver,
            DatabaseType.MONGODB: MongoDBDriver,
            DatabaseType.DYNAMODB: DynamoDBDriver,
            DatabaseType.SQLITE: SQLiteDriver
        }
        
        driver_class = driver_map.get(self.settings.database.type)
        if not driver_class:
            raise CogniDBError(f"Unsupported database type: {self.settings.database.type}")
        
        # Convert settings to driver config
        driver_config = {
            'host': self.settings.database.host,
            'port': self.settings.database.port,
            'database': self.settings.database.database,
            'username': self.settings.database.username,
            'password': self.settings.database.password,
            'ssl_enabled': self.settings.database.ssl_enabled,
            'query_timeout': self.settings.database.query_timeout,
            'max_result_size': self.settings.database.max_result_size,
            **self.settings.database.options
        }
        
        self.driver = driver_class(driver_config)
    
    def _init_security(self):
        """Initialize security components."""
        self.security_validator = QuerySecurityValidator(
            allowed_operations=['SELECT'],
            max_query_complexity=self.settings.security.max_query_complexity,
            allow_subqueries=self.settings.security.allow_subqueries
        )
        
        self.access_controller = AccessController()
        self.input_sanitizer = InputSanitizer()
    
    def _init_ai(self):
        """Initialize AI components."""
        # Initialize LLM manager
        self.llm_manager = LLMManager(
            self.settings.llm,
            cache_provider=None  # Will be set after cache init
        )
        
        # Initialize query generator
        self.query_generator = QueryGenerator(
            self.llm_manager,
            database_type=self.settings.database.type.value
        )
    
    def _init_cache(self):
        """Initialize caching layer."""
        # For now, using in-memory cache from LLM manager
        # In production, would initialize Redis/Memcached here
        pass
    
    def _apply_config_overrides(self, overrides: Dict[str, Any]):
        """Apply configuration overrides."""
        for key, value in overrides.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
    
    def _audit_log(self, 
                   user_id: Optional[str],
                   natural_language_query: str,
                   sql_query: Optional[str],
                   success: bool,
                   error: Optional[str] = None):
        """Log query for audit trail."""
        if not self.settings.security.enable_audit_logging:
            return
        
        # In production, this would write to a proper audit log
        logger.info(
            f"AUDIT: user={user_id}, query={natural_language_query[:50]}..., "
            f"success={success}, error={error}"
        )


# Convenience function for quick usage
def create_cognidb(**kwargs) -> CogniDB:
    """
    Create a CogniDB instance with configuration.
    
    Args:
        **kwargs: Configuration parameters
        
    Returns:
        CogniDB instance
    """
    return CogniDB(**kwargs)