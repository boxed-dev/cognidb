"""Custom exceptions for CogniDB."""


class CogniDBError(Exception):
    """Base exception for all CogniDB errors."""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class SecurityError(CogniDBError):
    """Raised when a security violation is detected."""
    pass


class ValidationError(CogniDBError):
    """Raised when validation fails."""
    pass


class TranslationError(CogniDBError):
    """Raised when query translation fails."""
    pass


class ExecutionError(CogniDBError):
    """Raised when query execution fails."""
    pass


class ConnectionError(CogniDBError):
    """Raised when database connection fails."""
    pass


class SchemaError(CogniDBError):
    """Raised when schema-related operations fail."""
    pass


class ConfigurationError(CogniDBError):
    """Raised when configuration is invalid."""
    pass


class CacheError(CogniDBError):
    """Raised when cache operations fail."""
    pass


class RateLimitError(CogniDBError):
    """Raised when rate limits are exceeded."""
    
    def __init__(self, message: str, retry_after: int = None, details: dict = None):
        super().__init__(message, details)
        self.retry_after = retry_after