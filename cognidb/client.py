"""
CogniDB - Secure Natural Language Database Interface

A production-ready natural language to SQL interface with comprehensive
security, multi-database support, and intelligent query generation.
"""

from __future__ import annotations

__version__ = "4.0.0"
__author__ = "Rishabh Kumar"

import logging
from typing import Any

from .ai import LLMManager, QueryGenerator
from .config import ConfigLoader, DatabaseType

# Core imports
from .core.exceptions import CogniDBError
from .drivers import (
    MySQLDriver,
    PostgreSQLDriver,
    SQLiteDriver,
)
from .pipeline import SecureQueryPipeline
from .security import AccessController, InputSanitizer, QuerySecurityValidator
from .security.statement_policy import StatementMode, StatementPolicy

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
    - Multi-database support (MySQL, PostgreSQL, SQLite; more planned)
    - Comprehensive security validation
    - Query optimization and caching
    - Cost tracking and limits
    - Audit logging
    """
    
    def __init__(self, 
                 config_file: str | None = None,
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

        # Deep secure pipeline (single path for NL→SQL→execute)
        sec = self.settings.security
        mode = StatementMode.READ if sec.allow_only_select else StatementMode.WRITE
        # Second opt-in: multi-statement only valid with write mode
        allow_ms = bool(sec.allow_multi_statement) and mode == StatementMode.WRITE
        policy = StatementPolicy(mode=mode, allow_multi_statement=allow_ms)
        # Align validator with mode
        self.security_validator.allowed_operations = list(policy.allowed_operations)
        audit_path = getattr(sec, "audit_log_path", None)
        self.pipeline = SecureQueryPipeline(
            driver=self.driver,
            generator=self.query_generator,
            validator=self.security_validator,
            sanitizer=self.input_sanitizer,
            schema=self.schema,
            access_controller=self.access_controller,
            enable_access_control=sec.enable_access_control,
            few_shot_examples=self.settings.llm.few_shot_examples,
            audit_path=audit_path,
            enable_audit=sec.enable_audit_logging,
            policy=policy,
            enable_schema_linking=sec.enable_schema_linking,
            schema_top_k=sec.schema_top_k,
            max_schema_tables=sec.max_schema_tables,
            repair_budget=sec.repair_budget,
        )
        
        logger.info("CogniDB initialized successfully")
    
    def query(self, 
              natural_language_query: str,
              user_id: str | None = None,
              explain: bool = False) -> dict[str, Any]:
        """
        Execute a natural language query through the secure pipeline.
        
        Args:
            natural_language_query: Query in natural language
            user_id: Optional user ID for access control
            explain: Whether to include query explanation
            
        Returns:
            Dictionary with results and metadata
        """
        return self.pipeline.run(
            natural_language_query,
            user_id=user_id,
            explain=explain,
        ).to_dict()

    def optimize_query(self, sql_query: str) -> dict[str, Any]:
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
    
    def suggest_queries(self, partial_query: str) -> list[str]:
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
    
    def get_schema(self, table_name: str | None = None) -> dict[str, Any]:
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
    
    def get_usage_stats(self) -> dict[str, Any]:
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
            DatabaseType.SQLITE: SQLiteDriver,
        }
        
        db_type = self.settings.database.type
        driver_class = driver_map.get(db_type)
        if not driver_class:
            raise CogniDBError(
                f"Unsupported database type: {db_type}. "
                f"Supported: MySQL, PostgreSQL, SQLite. "
                f"(MongoDB/DynamoDB planned.)"
            )
        
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
        if db_type == DatabaseType.SQLITE:
            # SQLite uses database/path field only
            driver_config['database'] = self.settings.database.database or ':memory:'
        
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
    
    def _apply_config_overrides(self, overrides: dict[str, Any]):
        """Apply configuration overrides."""
        for key, value in overrides.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
    
    def _audit_log(self, 
                   user_id: str | None,
                   natural_language_query: str,
                   sql_query: str | None,
                   success: bool,
                   error: str | None = None):
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