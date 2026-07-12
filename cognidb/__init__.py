"""
CogniDB - Secure Natural Language Database Interface

Production-oriented natural language to SQL with security-first validation.
Supported databases today: MySQL, PostgreSQL.
"""

__version__ = "2.0.0"
__author__ = "Rishabh Kumar"

from .client import CogniDB, create_cognidb
from .core.exceptions import (
    CogniDBError,
    SecurityError,
    TranslationError,
    ExecutionError,
    ValidationError,
)

__all__ = [
    "CogniDB",
    "create_cognidb",
    "CogniDBError",
    "SecurityError",
    "TranslationError",
    "ExecutionError",
    "ValidationError",
    "__version__",
]
