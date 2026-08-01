"""
CogniDB - Secure Natural Language Database Interface

Production-oriented natural language to SQL with security-first validation.
Supported databases today: MySQL, PostgreSQL, SQLite.
"""

__version__ = "4.0.0"
__author__ = "Rishabh Kumar"

from .client import CogniDB, create_cognidb
from .core.exceptions import (
    CogniDBError,
    ExecutionError,
    SecurityError,
    TranslationError,
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
