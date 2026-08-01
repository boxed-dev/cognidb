"""Settings and configuration classes."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class DatabaseType(Enum):
    """Supported database types."""
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    MONGODB = "mongodb"
    DYNAMODB = "dynamodb"
    SQLITE = "sqlite"


class LLMProvider(Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    LOCAL = "local"
    HUGGINGFACE = "huggingface"


class CacheProvider(Enum):
    """Supported cache providers."""
    IN_MEMORY = "in_memory"
    REDIS = "redis"
    MEMCACHED = "memcached"
    DISK = "disk"


@dataclass
class DatabaseConfig:
    """Database configuration."""
    type: DatabaseType
    host: str
    port: int
    database: str
    username: str | None = None
    password: str | None = field(default=None, repr=False)
    
    # Connection pool settings
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600
    
    # SSL/TLS settings
    ssl_enabled: bool = False
    ssl_ca_cert: str | None = None
    ssl_client_cert: str | None = None
    ssl_client_key: str | None = None
    
    # Query settings
    query_timeout: int = 30  # seconds
    max_result_size: int = 10000  # rows
    
    # Additional options
    options: dict[str, Any] = field(default_factory=dict)
    
    def get_connection_string(self) -> str:
        """Generate connection string (without password)."""
        if self.type == DatabaseType.SQLITE:
            return f"sqlite:///{self.database}"
        
        auth = ""
        if self.username:
            auth = f"{self.username}:***@"
        
        return f"{self.type.value}://{auth}{self.host}:{self.port}/{self.database}"


@dataclass
class LLMConfig:
    """LLM configuration."""
    provider: LLMProvider
    api_key: str | None = field(default=None, repr=False)
    
    # Model settings
    model_name: str = "gpt-4"
    temperature: float = 0.1
    max_tokens: int = 1000
    timeout: int = 30
    
    # Cost control
    max_tokens_per_query: int = 2000
    max_queries_per_minute: int = 60
    max_cost_per_day: float = 100.0
    
    # Prompt settings
    system_prompt: str | None = None
    few_shot_examples: list[dict[str, str]] = field(default_factory=list)
    
    # Provider-specific settings
    azure_endpoint: str | None = None
    azure_deployment: str | None = None
    huggingface_model_id: str | None = None
    local_model_path: str | None = None
    
    # Advanced settings
    enable_function_calling: bool = True
    enable_streaming: bool = False
    retry_attempts: int = 3
    retry_delay: float = 1.0


@dataclass
class CacheConfig:
    """Cache configuration."""
    provider: CacheProvider
    
    # TTL settings (in seconds)
    query_result_ttl: int = 3600  # 1 hour
    schema_ttl: int = 86400  # 24 hours
    llm_response_ttl: int = 7200  # 2 hours
    
    # Size limits
    max_cache_size_mb: int = 100
    max_entry_size_mb: int = 10
    eviction_policy: str = "lru"  # lru, lfu, ttl
    
    # Redis settings
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str | None = field(default=None, repr=False)
    redis_db: int = 0
    redis_ssl: bool = False
    
    # Disk cache settings
    disk_cache_path: str = str(Path.home() / ".cognidb" / "cache")
    
    # Performance settings
    enable_compression: bool = True
    enable_async_writes: bool = True


@dataclass
class SecurityConfig:
    """Security configuration (major-release statement policy + access)."""
    # Statement policy (ADR 0002–0004)
    # allow_only_select=True means read mode; False enables write mode (DML)
    allow_only_select: bool = True
    allow_multi_statement: bool = False  # requires write mode (not allow_only_select)
    max_query_complexity: int = 10
    allow_subqueries: bool = False
    allow_unions: bool = False
    repair_budget: int = 1

    # Schema linking (ADR 0007)
    enable_schema_linking: bool = True
    schema_top_k: int = 8
    max_schema_tables: int = 40

    # Rate limiting
    enable_rate_limiting: bool = True
    rate_limit_per_minute: int = 100
    rate_limit_per_hour: int = 1000

    # Access control (ADR 0005)
    enable_access_control: bool = False  # opt-in; when on, require caller identity allowlists
    default_user_permissions: list[str] = field(default_factory=lambda: ["SELECT"])
    require_authentication: bool = False

    # Audit logging
    enable_audit_logging: bool = True
    audit_log_path: str = str(Path.home() / ".cognidb" / "audit.log")
    log_query_results: bool = False

    # Encryption
    encrypt_cache: bool = True
    encrypt_logs: bool = True
    encryption_key: str | None = field(default=None, repr=False)

    # Network security
    allowed_ip_ranges: list[str] = field(default_factory=list)
    require_ssl: bool = True


@dataclass
class Settings:
    """Main settings container."""
    # Core configurations
    database: DatabaseConfig
    llm: LLMConfig
    cache: CacheConfig
    security: SecurityConfig
    
    # Application settings
    app_name: str = "CogniDB"
    environment: str = "production"
    debug: bool = False
    log_level: str = "INFO"
    
    # Paths
    data_dir: str = str(Path.home() / ".cognidb")
    log_dir: str = str(Path.home() / ".cognidb" / "logs")
    
    # Feature flags
    enable_natural_language: bool = True
    enable_query_explanation: bool = True
    enable_query_optimization: bool = True
    enable_auto_indexing: bool = False
    
    # Monitoring
    enable_metrics: bool = True
    metrics_port: int = 9090
    enable_tracing: bool = True
    tracing_endpoint: str | None = None
    
    @classmethod
    def from_env(cls) -> Settings:
        """Create settings from environment variables."""
        return cls(
            database=DatabaseConfig(
                type=DatabaseType(os.getenv('DB_TYPE', 'postgresql')),
                host=os.getenv('DB_HOST', 'localhost'),
                port=int(os.getenv('DB_PORT', '5432')),
                database=os.getenv('DB_NAME', 'cognidb'),
                username=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD')
            ),
            llm=LLMConfig(
                provider=LLMProvider(os.getenv('LLM_PROVIDER', 'openai')),
                api_key=os.getenv('LLM_API_KEY'),
                model_name=os.getenv('LLM_MODEL', 'gpt-4')
            ),
            cache=CacheConfig(
                provider=CacheProvider(os.getenv('CACHE_PROVIDER', 'in_memory'))
            ),
            security=SecurityConfig(
                allow_only_select=os.getenv('SECURITY_SELECT_ONLY', 'true').lower() == 'true'
            ),
            environment=os.getenv('ENVIRONMENT', 'production'),
            debug=os.getenv('DEBUG', 'false').lower() == 'true'
        )
    
    def validate(self) -> list[str]:
        """Validate settings and return list of errors."""
        errors = []
        
        # Database validation
        if not self.database.host:
            errors.append("Database host is required")
        if self.database.port <= 0 or self.database.port > 65535:
            errors.append("Invalid database port")
        
        # LLM validation
        if self.llm.provider != LLMProvider.LOCAL and not self.llm.api_key:
            errors.append("LLM API key is required for non-local providers")
        if self.llm.temperature < 0 or self.llm.temperature > 2:
            errors.append("LLM temperature must be between 0 and 2")
        
        # Security validation
        if self.security.encrypt_cache and not self.security.encryption_key:
            errors.append("Encryption key required when encryption is enabled")
        
        # Path validation
        for path_attr in ['data_dir', 'log_dir']:
            path = getattr(self, path_attr)
            try:
                Path(path).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create {path_attr}: {e}")
        
        return errors