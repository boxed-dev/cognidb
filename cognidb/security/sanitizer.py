"""Input sanitization utilities."""

import re
import html
from typing import Any, Dict, List, Union


class InputSanitizer:
    """
    Comprehensive input sanitizer for all user inputs.
    
    Provides multiple sanitization strategies:
    1. SQL identifiers (tables, columns)
    2. String values
    3. Numeric values
    4. Natural language queries
    """
    
    # Characters allowed in natural language queries
    ALLOWED_NL_CHARS = re.compile(r'[^a-zA-Z0-9\s\-_.,!?\'"\(\)%$#@]')
    
    # Maximum lengths for various inputs
    MAX_NATURAL_LANGUAGE_LENGTH = 500
    MAX_IDENTIFIER_LENGTH = 64
    MAX_STRING_VALUE_LENGTH = 1000
    
    @staticmethod
    def sanitize_natural_language(query: str) -> str:
        """
        Sanitize natural language query.
        
        Args:
            query: Raw natural language query
            
        Returns:
            Sanitized query safe for LLM processing
        """
        if not query:
            return ""
        
        # Truncate if too long
        query = query[:InputSanitizer.MAX_NATURAL_LANGUAGE_LENGTH]
        
        # Remove potentially harmful characters while preserving readability
        query = InputSanitizer.ALLOWED_NL_CHARS.sub(' ', query)
        
        # Normalize whitespace
        query = ' '.join(query.split())
        
        # HTML escape for additional safety
        query = html.escape(query, quote=False)
        
        return query.strip()
    
    @staticmethod
    def sanitize_identifier(identifier: str) -> str:
        """
        Sanitize database identifier (table/column name).
        
        Args:
            identifier: Raw identifier
            
        Returns:
            Sanitized identifier
            
        Raises:
            ValueError: If identifier cannot be sanitized
        """
        if not identifier:
            raise ValueError("Identifier cannot be empty")
        
        # Remove any quotes or special characters
        identifier = re.sub(r'[^a-zA-Z0-9_]', '', identifier)
        
        # Ensure it starts with a letter or underscore
        if not re.match(r'^[a-zA-Z_]', identifier):
            identifier = f"_{identifier}"
        
        # Truncate if too long
        identifier = identifier[:InputSanitizer.MAX_IDENTIFIER_LENGTH]
        
        if not identifier:
            raise ValueError("Identifier contains no valid characters")
        
        return identifier
    
    @staticmethod
    def sanitize_string_value(value: str, allow_wildcards: bool = False) -> str:
        """
        Sanitize string value for use in queries.
        
        Args:
            value: Raw string value
            allow_wildcards: Whether to allow SQL wildcards (% and _)
            
        Returns:
            Sanitized string value
        """
        if not isinstance(value, str):
            return str(value)
        
        # Truncate if too long
        value = value[:InputSanitizer.MAX_STRING_VALUE_LENGTH]
        
        # Remove null bytes
        value = value.replace('\x00', '')
        
        # Handle SQL wildcards
        if not allow_wildcards:
            value = value.replace('%', '\\%').replace('_', '\\_')
        
        # Note: Actual SQL escaping should be done by parameterized queries
        # This is just an additional safety layer
        
        return value
    
    @staticmethod
    def sanitize_numeric_value(value: Union[int, float, str]) -> Union[int, float, None]:
        """
        Sanitize numeric value.
        
        Args:
            value: Raw numeric value
            
        Returns:
            Sanitized numeric value or None if invalid
        """
        if isinstance(value, (int, float)):
            return value
        
        if isinstance(value, str):
            try:
                # Try to parse as float first
                if '.' in value:
                    return float(value)
                else:
                    return int(value)
            except ValueError:
                return None
        
        return None
    
    @staticmethod
    def sanitize_list_value(values: List[Any], sanitize_func=None) -> List[Any]:
        """
        Sanitize a list of values.
        
        Args:
            values: List of raw values
            sanitize_func: Function to apply to each value
            
        Returns:
            List of sanitized values
        """
        if not isinstance(values, (list, tuple, set)):
            raise ValueError("Input must be a list, tuple, or set")
        
        if sanitize_func is None:
            sanitize_func = InputSanitizer.sanitize_string_value
        
        sanitized = []
        for value in values:
            try:
                sanitized_value = sanitize_func(value)
                if sanitized_value is not None:
                    sanitized.append(sanitized_value)
            except Exception:
                # Skip invalid values
                continue
        
        return sanitized
    
    @staticmethod
    def sanitize_dict_value(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively sanitize dictionary values.
        
        Args:
            data: Dictionary with raw values
            
        Returns:
            Dictionary with sanitized values
        """
        if not isinstance(data, dict):
            raise ValueError("Input must be a dictionary")
        
        sanitized = {}
        for key, value in data.items():
            # Sanitize key
            safe_key = InputSanitizer.sanitize_identifier(key)
            
            # Sanitize value based on type
            if isinstance(value, str):
                sanitized[safe_key] = InputSanitizer.sanitize_string_value(value)
            elif isinstance(value, (int, float)):
                sanitized[safe_key] = InputSanitizer.sanitize_numeric_value(value)
            elif isinstance(value, (list, tuple, set)):
                sanitized[safe_key] = InputSanitizer.sanitize_list_value(value)
            elif isinstance(value, dict):
                sanitized[safe_key] = InputSanitizer.sanitize_dict_value(value)
            elif value is None:
                sanitized[safe_key] = None
            else:
                # Convert to string and sanitize
                sanitized[safe_key] = InputSanitizer.sanitize_string_value(str(value))
        
        return sanitized
    
    @staticmethod
    def escape_like_pattern(pattern: str) -> str:
        """
        Escape special characters in LIKE patterns.
        
        Args:
            pattern: Raw LIKE pattern
            
        Returns:
            Escaped pattern
        """
        # Escape LIKE special characters
        pattern = pattern.replace('\\', '\\\\')
        pattern = pattern.replace('%', '\\%')
        pattern = pattern.replace('_', '\\_')
        return pattern
    
    @staticmethod
    def validate_and_sanitize_limit(limit: Any) -> int:
        """
        Validate and sanitize LIMIT value.
        
        Args:
            limit: Raw limit value
            
        Returns:
            Sanitized limit value
            
        Raises:
            ValueError: If limit is invalid
        """
        try:
            limit = int(limit)
            if limit < 1:
                raise ValueError("Limit must be positive")
            if limit > 10000:  # Reasonable maximum
                return 10000
            return limit
        except (TypeError, ValueError):
            raise ValueError("Invalid limit value")
    
    @staticmethod
    def validate_and_sanitize_offset(offset: Any) -> int:
        """
        Validate and sanitize OFFSET value.
        
        Args:
            offset: Raw offset value
            
        Returns:
            Sanitized offset value
            
        Raises:
            ValueError: If offset is invalid
        """
        try:
            offset = int(offset)
            if offset < 0:
                raise ValueError("Offset must be non-negative")
            if offset > 1000000:  # Reasonable maximum
                raise ValueError("Offset too large")
            return offset
        except (TypeError, ValueError):
            raise ValueError("Invalid offset value")