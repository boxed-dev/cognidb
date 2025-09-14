"""SQL query parser for security validation."""

import re
from typing import Dict, Any, List, Optional
import sqlparse
from sqlparse.sql import IdentifierList, Identifier, Token
from sqlparse.tokens import Keyword, DML


class SQLQueryParser:
    """
    SQL query parser for security analysis.
    
    Parses SQL queries to extract structure and identify
    potential security issues.
    """
    
    def __init__(self):
        """Initialize the parser."""
        self.parsed_cache = {}
    
    def parse(self, query: str) -> Dict[str, Any]:
        """
        Parse SQL query and extract security-relevant information.
        
        Args:
            query: SQL query string
            
        Returns:
            Dictionary with parsed query information:
            {
                'type': 'SELECT',
                'tables': ['users', 'orders'],
                'columns': ['id', 'name'],
                'has_subquery': False,
                'has_union': False,
                'has_join': True,
                'has_where': True,
                'complexity': 5
            }
        """
        # Clean and normalize query
        query = query.strip()
        
        # Check cache
        cache_key = hash(query)
        if cache_key in self.parsed_cache:
            return self.parsed_cache[cache_key]
        
        # Parse with sqlparse
        parsed = sqlparse.parse(query)[0]
        
        result = {
            'type': self._get_query_type(parsed),
            'tables': self._extract_tables(parsed),
            'columns': self._extract_columns(parsed),
            'has_subquery': self._has_subquery(parsed),
            'has_union': self._has_union(query),
            'has_join': self._has_join(parsed),
            'has_where': self._has_where(parsed),
            'has_having': self._has_having(parsed),
            'has_order_by': self._has_order_by(parsed),
            'has_group_by': self._has_group_by(parsed),
            'complexity': self._calculate_complexity(parsed)
        }
        
        # Cache result
        self.parsed_cache[cache_key] = result
        
        return result
    
    def _get_query_type(self, parsed) -> str:
        """Extract the main query type."""
        for token in parsed.tokens:
            if token.ttype is DML:
                return token.value.upper()
        return "UNKNOWN"
    
    def _extract_tables(self, parsed) -> List[str]:
        """Extract table names from the query."""
        tables = []
        from_seen = False
        
        for token in parsed.tokens:
            if from_seen:
                if isinstance(token, IdentifierList):
                    for identifier in token.get_identifiers():
                        tables.append(self._get_name(identifier))
                elif isinstance(token, Identifier):
                    tables.append(self._get_name(token))
                elif token.ttype is None:
                    tables.append(token.value)
            
            if token.ttype is Keyword and token.value.upper() == 'FROM':
                from_seen = True
            elif token.ttype is Keyword and token.value.upper() in ('WHERE', 'GROUP', 'ORDER', 'HAVING'):
                from_seen = False
        
        return [t.strip() for t in tables if t.strip()]
    
    def _extract_columns(self, parsed) -> List[str]:
        """Extract column names from SELECT clause."""
        columns = []
        select_seen = False
        
        for token in parsed.tokens:
            if select_seen and token.ttype is Keyword:
                break
            
            if select_seen:
                if isinstance(token, IdentifierList):
                    for identifier in token.get_identifiers():
                        columns.append(self._get_name(identifier))
                elif isinstance(token, Identifier):
                    columns.append(self._get_name(token))
                elif token.ttype is None and token.value not in (',', ' '):
                    columns.append(token.value)
            
            if token.ttype is DML and token.value.upper() == 'SELECT':
                select_seen = True
        
        return [c.strip() for c in columns if c.strip()]
    
    def _get_name(self, identifier) -> str:
        """Get the name from an identifier."""
        if hasattr(identifier, 'get_name'):
            return identifier.get_name()
        return str(identifier)
    
    def _has_subquery(self, parsed) -> bool:
        """Check if query contains subqueries."""
        query_str = str(parsed)
        # Simple check for nested SELECT
        return query_str.count('SELECT') > 1
    
    def _has_union(self, query: str) -> bool:
        """Check if query contains UNION."""
        return bool(re.search(r'\bUNION\b', query, re.IGNORECASE))
    
    def _has_join(self, parsed) -> bool:
        """Check if query contains JOIN."""
        for token in parsed.tokens:
            if token.ttype is Keyword and 'JOIN' in token.value.upper():
                return True
        return False
    
    def _has_where(self, parsed) -> bool:
        """Check if query has WHERE clause."""
        for token in parsed.tokens:
            if token.ttype is Keyword and token.value.upper() == 'WHERE':
                return True
        return False
    
    def _has_having(self, parsed) -> bool:
        """Check if query has HAVING clause."""
        for token in parsed.tokens:
            if token.ttype is Keyword and token.value.upper() == 'HAVING':
                return True
        return False
    
    def _has_order_by(self, parsed) -> bool:
        """Check if query has ORDER BY clause."""
        query_str = str(parsed).upper()
        return 'ORDER BY' in query_str
    
    def _has_group_by(self, parsed) -> bool:
        """Check if query has GROUP BY clause."""
        query_str = str(parsed).upper()
        return 'GROUP BY' in query_str
    
    def _calculate_complexity(self, parsed) -> int:
        """
        Calculate query complexity score.
        
        Higher scores indicate more complex queries that might
        need additional scrutiny.
        """
        score = 1  # Base score
        
        # Add complexity for various features
        if self._has_subquery(parsed):
            score += 3
        if self._has_union(str(parsed)):
            score += 2
        if self._has_join(parsed):
            score += 2
        if self._has_where(parsed):
            score += 1
        if self._has_group_by(parsed):
            score += 2
        if self._has_having(parsed):
            score += 2
        if self._has_order_by(parsed):
            score += 1
        
        # Add complexity for number of tables
        tables = self._extract_tables(parsed)
        if len(tables) > 1:
            score += len(tables) - 1
        
        return score
    
    def validate_structure(self, query: str) -> Optional[str]:
        """
        Validate query structure and return error if invalid.
        
        Args:
            query: SQL query string
            
        Returns:
            Error message if invalid, None if valid
        """
        try:
            parsed = sqlparse.parse(query)
            if not parsed:
                return "Empty or invalid query"
            
            # Check for multiple statements
            if len(parsed) > 1:
                return "Multiple statements not allowed"
            
            # Get query type
            query_type = self._get_query_type(parsed[0])
            if query_type == "UNKNOWN":
                return "Unknown query type"
            
            return None
            
        except Exception as e:
            return f"Query parsing error: {str(e)}"