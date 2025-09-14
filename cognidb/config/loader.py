"""Configuration loader with multiple source support."""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from .settings import Settings, DatabaseConfig, LLMConfig, CacheConfig, SecurityConfig
from .settings import DatabaseType, LLMProvider, CacheProvider
from .secrets import SecretsManager
from ..core.exceptions import ConfigurationError


class ConfigLoader:
    """
    Load configuration from multiple sources.
    
    Priority order (highest to lowest):
    1. Environment variables
    2. Config file (JSON/YAML)
    3. Defaults
    """
    
    def __init__(self, 
                 config_file: Optional[str] = None,
                 secrets_manager: Optional[SecretsManager] = None):
        """
        Initialize config loader.
        
        Args:
            config_file: Path to configuration file
            secrets_manager: Secrets manager instance
        """
        self.config_file = config_file or self._find_config_file()
        self.secrets_manager = secrets_manager or SecretsManager()
        self._config_data: Dict[str, Any] = {}
    
    def load(self) -> Settings:
        """
        Load configuration from all sources.
        
        Returns:
            Settings object
        """
        # Load from file if exists
        if self.config_file and Path(self.config_file).exists():
            self._load_from_file()
        
        # Override with environment variables
        self._load_from_env()
        
        # Load secrets
        self._load_secrets()
        
        # Create settings object
        settings = self._create_settings()
        
        # Validate
        errors = settings.validate()
        if errors:
            raise ConfigurationError(f"Configuration errors: {', '.join(errors)}")
        
        return settings
    
    def _find_config_file(self) -> Optional[str]:
        """Find configuration file in standard locations."""
        # Check environment variable
        if 'COGNIDB_CONFIG' in os.environ:
            return os.environ['COGNIDB_CONFIG']
        
        # Check standard locations
        locations = [
            'cognidb.yaml',
            'cognidb.yml',
            'cognidb.json',
            '.cognidb.yaml',
            '.cognidb.yml',
            '.cognidb.json',
            str(Path.home() / '.cognidb' / 'config.yaml'),
            str(Path.home() / '.cognidb' / 'config.yml'),
            str(Path.home() / '.cognidb' / 'config.json'),
            '/etc/cognidb/config.yaml',
            '/etc/cognidb/config.yml',
            '/etc/cognidb/config.json',
        ]
        
        for location in locations:
            if Path(location).exists():
                return location
        
        return None
    
    def _load_from_file(self) -> None:
        """Load configuration from file."""
        try:
            with open(self.config_file, 'r') as f:
                if self.config_file.endswith(('.yaml', '.yml')):
                    self._config_data = yaml.safe_load(f)
                else:
                    self._config_data = json.load(f)
        except Exception as e:
            raise ConfigurationError(f"Failed to load config file: {e}")
    
    def _load_from_env(self) -> None:
        """Load configuration from environment variables."""
        # Database settings
        if 'DB_TYPE' in os.environ:
            self._set_nested('database.type', os.environ['DB_TYPE'])
        if 'DB_HOST' in os.environ:
            self._set_nested('database.host', os.environ['DB_HOST'])
        if 'DB_PORT' in os.environ:
            self._set_nested('database.port', int(os.environ['DB_PORT']))
        if 'DB_NAME' in os.environ:
            self._set_nested('database.database', os.environ['DB_NAME'])
        if 'DB_USER' in os.environ:
            self._set_nested('database.username', os.environ['DB_USER'])
        if 'DB_PASSWORD' in os.environ:
            self._set_nested('database.password', os.environ['DB_PASSWORD'])
        
        # LLM settings
        if 'LLM_PROVIDER' in os.environ:
            self._set_nested('llm.provider', os.environ['LLM_PROVIDER'])
        if 'LLM_API_KEY' in os.environ:
            self._set_nested('llm.api_key', os.environ['LLM_API_KEY'])
        if 'LLM_MODEL' in os.environ:
            self._set_nested('llm.model_name', os.environ['LLM_MODEL'])
        
        # Cache settings
        if 'CACHE_PROVIDER' in os.environ:
            self._set_nested('cache.provider', os.environ['CACHE_PROVIDER'])
        
        # Security settings
        if 'SECURITY_SELECT_ONLY' in os.environ:
            self._set_nested('security.allow_only_select', 
                           os.environ['SECURITY_SELECT_ONLY'].lower() == 'true')
        
        # Application settings
        if 'ENVIRONMENT' in os.environ:
            self._set_nested('environment', os.environ['ENVIRONMENT'])
        if 'DEBUG' in os.environ:
            self._set_nested('debug', os.environ['DEBUG'].lower() == 'true')
        if 'LOG_LEVEL' in os.environ:
            self._set_nested('log_level', os.environ['LOG_LEVEL'])
    
    def _load_secrets(self) -> None:
        """Load secrets from secrets manager."""
        # Database password
        if not self._get_nested('database.password'):
            password = self.secrets_manager.get_secret('DB_PASSWORD')
            if password:
                self._set_nested('database.password', password)
        
        # LLM API key
        if not self._get_nested('llm.api_key'):
            api_key = self.secrets_manager.get_secret('LLM_API_KEY')
            if api_key:
                self._set_nested('llm.api_key', api_key)
        
        # Redis password
        if not self._get_nested('cache.redis_password'):
            redis_password = self.secrets_manager.get_secret('REDIS_PASSWORD')
            if redis_password:
                self._set_nested('cache.redis_password', redis_password)
        
        # Encryption key
        if not self._get_nested('security.encryption_key'):
            encryption_key = self.secrets_manager.get_secret('ENCRYPTION_KEY')
            if encryption_key:
                self._set_nested('security.encryption_key', encryption_key)
    
    def _create_settings(self) -> Settings:
        """Create Settings object from loaded configuration."""
        # Database configuration
        db_config = self._get_nested('database', {})
        database = DatabaseConfig(
            type=DatabaseType(db_config.get('type', 'postgresql')),
            host=db_config.get('host', 'localhost'),
            port=db_config.get('port', 5432),
            database=db_config.get('database', 'cognidb'),
            username=db_config.get('username'),
            password=db_config.get('password'),
            pool_size=db_config.get('pool_size', 5),
            max_overflow=db_config.get('max_overflow', 10),
            pool_timeout=db_config.get('pool_timeout', 30),
            pool_recycle=db_config.get('pool_recycle', 3600),
            ssl_enabled=db_config.get('ssl_enabled', False),
            ssl_ca_cert=db_config.get('ssl_ca_cert'),
            ssl_client_cert=db_config.get('ssl_client_cert'),
            ssl_client_key=db_config.get('ssl_client_key'),
            query_timeout=db_config.get('query_timeout', 30),
            max_result_size=db_config.get('max_result_size', 10000),
            options=db_config.get('options', {})
        )
        
        # LLM configuration
        llm_config = self._get_nested('llm', {})
        llm = LLMConfig(
            provider=LLMProvider(llm_config.get('provider', 'openai')),
            api_key=llm_config.get('api_key'),
            model_name=llm_config.get('model_name', 'gpt-4'),
            temperature=llm_config.get('temperature', 0.1),
            max_tokens=llm_config.get('max_tokens', 1000),
            timeout=llm_config.get('timeout', 30),
            max_tokens_per_query=llm_config.get('max_tokens_per_query', 2000),
            max_queries_per_minute=llm_config.get('max_queries_per_minute', 60),
            max_cost_per_day=llm_config.get('max_cost_per_day', 100.0),
            system_prompt=llm_config.get('system_prompt'),
            few_shot_examples=llm_config.get('few_shot_examples', []),
            azure_endpoint=llm_config.get('azure_endpoint'),
            azure_deployment=llm_config.get('azure_deployment'),
            huggingface_model_id=llm_config.get('huggingface_model_id'),
            local_model_path=llm_config.get('local_model_path'),
            enable_function_calling=llm_config.get('enable_function_calling', True),
            enable_streaming=llm_config.get('enable_streaming', False),
            retry_attempts=llm_config.get('retry_attempts', 3),
            retry_delay=llm_config.get('retry_delay', 1.0)
        )
        
        # Cache configuration
        cache_config = self._get_nested('cache', {})
        cache = CacheConfig(
            provider=CacheProvider(cache_config.get('provider', 'in_memory')),
            query_result_ttl=cache_config.get('query_result_ttl', 3600),
            schema_ttl=cache_config.get('schema_ttl', 86400),
            llm_response_ttl=cache_config.get('llm_response_ttl', 7200),
            max_cache_size_mb=cache_config.get('max_cache_size_mb', 100),
            max_entry_size_mb=cache_config.get('max_entry_size_mb', 10),
            eviction_policy=cache_config.get('eviction_policy', 'lru'),
            redis_host=cache_config.get('redis_host', 'localhost'),
            redis_port=cache_config.get('redis_port', 6379),
            redis_password=cache_config.get('redis_password'),
            redis_db=cache_config.get('redis_db', 0),
            redis_ssl=cache_config.get('redis_ssl', False),
            disk_cache_path=cache_config.get('disk_cache_path', 
                                            str(Path.home() / '.cognidb' / 'cache')),
            enable_compression=cache_config.get('enable_compression', True),
            enable_async_writes=cache_config.get('enable_async_writes', True)
        )
        
        # Security configuration
        security_config = self._get_nested('security', {})
        security = SecurityConfig(
            allow_only_select=security_config.get('allow_only_select', True),
            max_query_complexity=security_config.get('max_query_complexity', 10),
            allow_subqueries=security_config.get('allow_subqueries', False),
            allow_unions=security_config.get('allow_unions', False),
            enable_rate_limiting=security_config.get('enable_rate_limiting', True),
            rate_limit_per_minute=security_config.get('rate_limit_per_minute', 100),
            rate_limit_per_hour=security_config.get('rate_limit_per_hour', 1000),
            enable_access_control=security_config.get('enable_access_control', True),
            default_user_permissions=security_config.get('default_user_permissions', ['SELECT']),
            require_authentication=security_config.get('require_authentication', False),
            enable_audit_logging=security_config.get('enable_audit_logging', True),
            audit_log_path=security_config.get('audit_log_path', 
                                             str(Path.home() / '.cognidb' / 'audit.log')),
            log_query_results=security_config.get('log_query_results', False),
            encrypt_cache=security_config.get('encrypt_cache', True),
            encrypt_logs=security_config.get('encrypt_logs', True),
            encryption_key=security_config.get('encryption_key'),
            allowed_ip_ranges=security_config.get('allowed_ip_ranges', []),
            require_ssl=security_config.get('require_ssl', True)
        )
        
        # Create settings
        return Settings(
            database=database,
            llm=llm,
            cache=cache,
            security=security,
            app_name=self._get_nested('app_name', 'CogniDB'),
            environment=self._get_nested('environment', 'production'),
            debug=self._get_nested('debug', False),
            log_level=self._get_nested('log_level', 'INFO'),
            data_dir=self._get_nested('data_dir', str(Path.home() / '.cognidb')),
            log_dir=self._get_nested('log_dir', str(Path.home() / '.cognidb' / 'logs')),
            enable_natural_language=self._get_nested('enable_natural_language', True),
            enable_query_explanation=self._get_nested('enable_query_explanation', True),
            enable_query_optimization=self._get_nested('enable_query_optimization', True),
            enable_auto_indexing=self._get_nested('enable_auto_indexing', False),
            enable_metrics=self._get_nested('enable_metrics', True),
            metrics_port=self._get_nested('metrics_port', 9090),
            enable_tracing=self._get_nested('enable_tracing', True),
            tracing_endpoint=self._get_nested('tracing_endpoint')
        )
    
    def _get_nested(self, path: str, default: Any = None) -> Any:
        """Get nested configuration value."""
        keys = path.split('.')
        value = self._config_data
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def _set_nested(self, path: str, value: Any) -> None:
        """Set nested configuration value."""
        keys = path.split('.')
        target = self._config_data
        
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
        
        target[keys[-1]] = value