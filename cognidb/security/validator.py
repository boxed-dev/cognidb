"""Security validator implementation."""

import re
from typing import Tuple, Optional, List, Set
from ..core.interfaces import SecurityValidator
from ..core.query_intent import QueryIntent, QueryType
from ..core.exceptions import SecurityError
from .query_parser import SQLQueryParser


class QuerySecurityValidator(SecurityValidator):
    """
    Comprehensive security validator for queries.
    
    Implements multiple layers of security:
    1. Query intent validation
    2. Native query validation
    3. Identifier sanitization
    4. Value sanitization
    """
    
    # Dangerous SQL keywords that should never appear
    FORBIDDEN_KEYWORDS = {
        'DROP', 'DELETE', 'TRUNCATE', 'UPDATE', 'INSERT', 'ALTER',
        'CREATE', 'REPLACE', 'RENAME', 'GRANT', 'REVOKE', 'EXECUTE',
        'EXEC', 'CALL', 'MERGE', 'LOCK', 'UNLOCK'
    }
    
    # Patterns that might indicate SQL injection
    SQL_INJECTION_PATTERNS = [
        r';\s*--',  # Statement termination followed by comment
        r';\s*\/\*',  # Statement termination followed by comment
        r'UNION\s+SELECT',  # UNION-based injection
        r'OR\s+1\s*=\s*1',  # Classic SQL injection
        r'OR\s+\'1\'\s*=\s*\'1\'',  # Classic SQL injection with quotes
        r'WAITFOR\s+DELAY',  # Time-based injection
        r'BENCHMARK\s*\(',  # MySQL time-based injection
        r'PG_SLEEP\s*\(',  # PostgreSQL time-based injection
        r'LOAD_FILE\s*\(',  # File system access
        r'INTO\s+OUTFILE',  # File system write
        r'xp_cmdshell',  # SQL Server command execution
    ]
    
    # Valid identifier pattern (alphanumeric + underscore)
    VALID_IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    
    # Maximum identifier length
    MAX_IDENTIFIER_LENGTH = 64
    
    def __init__(self, 
                 allowed_operations: Optional[List[str]] = None,
                 max_query_complexity: int = 10,
                 allow_subqueries: bool = False):
        """
        Initialize security validator.
        
        Args:
            allowed_operations: List of allowed query types (default: SELECT only)
            max_query_complexity: Maximum allowed query complexity score
            allow_subqueries: Whether to allow subqueries
        """
        self._allowed_operations = allowed_operations or ['SELECT']
        self.max_query_complexity = max_query_complexity
        self.allow_subqueries = allow_subqueries
        self.parser = SQLQueryParser()
    
    @property
    def allowed_operations(self) -> List[str]:
        """List of allowed query operations."""
        return self._allowed_operations
    
    def validate_query_intent(self, query_intent: QueryIntent) -> Tuple[bool, Optional[str]]:
        """
        Validate query intent for security issues.
        
        Checks:
        1. Query type is allowed
        2. Table/column names are valid
        3. Query complexity is within limits
        4. No forbidden patterns in conditions
        """
        # Check query type
        if query_intent.query_type.name not in self.allowed_operations:
            return False, f"Query type {query_intent.query_type.name} is not allowed"
        
        # Validate table names
        for table in query_intent.tables:
            if not self._is_valid_identifier(table):
                return False, f"Invalid table name: {table}"
        
        # Validate column names
        for column in query_intent.columns:
            if column.name != "*" and not self._is_valid_identifier(column.name):
                return False, f"Invalid column name: {column.name}"
            if column.table and not self._is_valid_identifier(column.table):
                return False, f"Invalid table reference in column: {column.table}"
        
        # Check query complexity
        complexity = self._calculate_complexity(query_intent)
        if complexity > self.max_query_complexity:
            return False, f"Query too complex (score: {complexity}, max: {self.max_query_complexity})"
        
        # Validate conditions
        if query_intent.conditions:
            valid, error = self._validate_conditions(query_intent.conditions)
            if not valid:
                return False, error
        
        # Validate joins
        for join in query_intent.joins:
            if not self._is_valid_identifier(join.left_table):
                return False, f"Invalid table in join: {join.left_table}"
            if not self._is_valid_identifier(join.right_table):
                return False, f"Invalid table in join: {join.right_table}"
            if not self._is_valid_identifier(join.left_column):
                return False, f"Invalid column in join: {join.left_column}"
            if not self._is_valid_identifier(join.right_column):
                return False, f"Invalid column in join: {join.right_column}"
        
        return True, None
    
    def validate_native_query(self, query: str) -> Tuple[bool, Optional[str]]:
        """
        Validate native SQL query for security issues.
        
        Performs comprehensive security checks including:
        1. Forbidden keyword detection
        2. SQL injection pattern matching
        3. Query parsing and analysis
        """
        # Normalize query for analysis
        normalized_query = query.upper().strip()
        
        # Check for forbidden keywords
        for keyword in self.FORBIDDEN_KEYWORDS:
            if re.search(rf'\b{keyword}\b', normalized_query):
                return False, f"Forbidden keyword detected: {keyword}"
        
        # Check for SQL injection patterns
        for pattern in self.SQL_INJECTION_PATTERNS:
            if re.search(pattern, normalized_query, re.IGNORECASE):
                return False, f"Potential SQL injection pattern detected"
        
        # Parse and validate query structure
        try:
            parsed = self.parser.parse(query)
            if parsed['type'] not in self.allowed_operations:
                return False, f"Query type {parsed['type']} is not allowed"
            
            # Additional checks based on parsed structure
            if not self.allow_subqueries and parsed.get('has_subquery'):
                return False, "Subqueries are not allowed"
            
        except Exception as e:
            return False, f"Query parsing failed: {str(e)}"
        
        return True, None
    
    def sanitize_identifier(self, identifier: str) -> str:
        """
        Sanitize a table/column identifier.
        
        Args:
            identifier: The identifier to sanitize
            
        Returns:
            Sanitized identifier
            
        Raises:
            SecurityError: If identifier cannot be sanitized safely
        """
        # Remove any quotes
        identifier = identifier.strip().strip('"\'`[]')
        
        # Validate
        if not self._is_valid_identifier(identifier):
            raise SecurityError(f"Invalid identifier: {identifier}")
        
        return identifier
    
    def sanitize_value(self, value: any) -> any:
        """
        Sanitize a parameter value.
        
        Args:
            value: The value to sanitize
            
        Returns:
            Sanitized value
        """
        if value is None:
            return None
        
        if isinstance(value, str):
            # Remove any SQL comment indicators
            value = re.sub(r'--.*$', '', value, flags=re.MULTILINE)
            value = re.sub(r'/\*.*?\*/', '', value, flags=re.DOTALL)
            
            # Escape special characters
            # Note: Actual escaping should be done by the database driver
            # This is just an additional safety layer
            value = value.replace('\x00', '')  # Remove null bytes
            
        elif isinstance(value, (list, tuple)):
            # Recursively sanitize collections
            return type(value)(self.sanitize_value(v) for v in value)
        
        elif isinstance(value, dict):
            # Recursively sanitize dictionaries
            return {k: self.sanitize_value(v) for k, v in value.items()}
        
        return value
    
    def _is_valid_identifier(self, identifier: str) -> bool:
        """Check if an identifier is valid."""
        if not identifier or len(identifier) > self.MAX_IDENTIFIER_LENGTH:
            return False
        return bool(self.VALID_IDENTIFIER_PATTERN.match(identifier))
    
    def _calculate_complexity(self, query_intent: QueryIntent) -> int:
        """
        Calculate query complexity score.
        
        Factors:
        - Number of tables
        - Number of joins
        - Number of conditions
        - Aggregations
        - Subqueries (if parsed)
        """
        score = 0
        
        # Base score for tables
        score += len(query_intent.tables)
        
        # Joins add complexity
        score += len(query_intent.joins) * 2
        
        # Conditions add complexity
        if query_intent.conditions:
            score += self._count_conditions(query_intent.conditions)
        
        # Aggregations add complexity
        score += len(query_intent.aggregations)
        
        # Group by adds complexity
        if query_intent.group_by:
            score += 1
        
        # Having clause adds complexity
        if query_intent.having:
            score += 2
        
        return score
    
    def _count_conditions(self, condition_group) -> int:
        """Recursively count conditions in a group."""
        count = 0
        for condition in condition_group.conditions:
            if hasattr(condition, 'conditions'):  # It's a group
                count += self._count_conditions(condition)
            else:
                count += 1
        return count
    
    def _validate_conditions(self, condition_group) -> Tuple[bool, Optional[str]]:
        """Validate conditions in a condition group."""
        for condition in condition_group.conditions:
            if hasattr(condition, 'conditions'):  # It's a group
                valid, error = self._validate_conditions(condition)
                if not valid:
                    return False, error
            else:
                # Validate column name
                if not self._is_valid_identifier(condition.column.name):
                    return False, f"Invalid column in condition: {condition.column.name}"
                
                # Validate value isn't attempting injection
                if isinstance(condition.value, str):
                    if any(keyword in condition.value.upper() for keyword in self.FORBIDDEN_KEYWORDS):
                        return False, f"Forbidden keyword in condition value"
        
        return True, None