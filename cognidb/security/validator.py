"""Security validator implementation.

``validate_native_query`` is a thin delegation to :mod:`cognidb.security.sql_guard`,
the single source of parsing truth. The previous regex/sqlparse denylist
(tautologies, ``UNION SELECT``, time/file functions) is deleted: the audit proved
it bypassable, and with a read-only role + parameter binding + ACL + row caps a
textual denylist is a false guarantee. Gating is now purely structural (AST).

The intent-path methods (``validate_query_intent``, ``sanitize_identifier``,
``sanitize_value``, ``_is_valid_identifier``) operate on structured intent
objects and identifiers, not raw SQL, and keep their original behavior.
"""

from __future__ import annotations

import re

from ..core.exceptions import SecurityError
from ..core.interfaces import SecurityValidator
from ..core.query_intent import QueryIntent
from . import sql_guard


class QuerySecurityValidator(SecurityValidator):
    """
    Comprehensive security validator for queries.

    Implements multiple layers of security:
    1. Query intent validation
    2. Native query validation (delegated to the AST guard)
    3. Identifier sanitization
    4. Value sanitization
    """

    # Valid identifier pattern (alphanumeric + underscore)
    VALID_IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

    # Maximum identifier length
    MAX_IDENTIFIER_LENGTH = 64

    def __init__(self,
                 allowed_operations: list[str] | None = None,
                 max_query_complexity: int = 10,
                 allow_subqueries: bool = False,
                 dialect: str | None = None,
                 allow_multi_statement: bool = False):
        """
        Initialize security validator.

        Args:
            allowed_operations: List of allowed query types (default: SELECT only)
            max_query_complexity: Maximum allowed intent complexity score
            allow_subqueries: Retained for intent-path compatibility
            dialect: Target SQL dialect passed to the guard (sqlite/postgres/mysql)
            allow_multi_statement: Permit multiple statements (write-mode opt-in)
        """
        self._allowed_operations = allowed_operations or ['SELECT']
        self.max_query_complexity = max_query_complexity
        self.allow_subqueries = allow_subqueries
        self.dialect = dialect
        self.allow_multi_statement = allow_multi_statement

    @property
    def allowed_operations(self) -> list[str]:
        """List of allowed query operations."""
        return self._allowed_operations

    @allowed_operations.setter
    def allowed_operations(self, value: list[str]) -> None:
        self._allowed_operations = list(value)

    def validate_query_intent(self, query_intent: QueryIntent) -> tuple[bool, str | None]:
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
            return False, (
                f"Query too complex (score: {complexity}, max: {self.max_query_complexity})"
            )

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

    def validate_native_query(self, query: str) -> tuple[bool, str | None]:
        """
        Validate a native SQL query by delegating to the AST security guard.

        Returns ``(True, None)`` when the guard accepts the statement, or
        ``(False, message)`` when it raises :class:`sql_guard.GuardError`. The
        guard fails closed on unparseable SQL, stacked statements, DDL/admin
        nodes anywhere in the tree, and data-modifying CTEs.
        """
        try:
            sql_guard.analyze(
                query,
                dialect=self.dialect,
                allowed_operations=frozenset(self._allowed_operations),
                allow_multi_statement=self.allow_multi_statement,
            )
        except sql_guard.GuardError as err:
            return False, str(err)
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

    def _validate_conditions(self, condition_group) -> tuple[bool, str | None]:
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

        return True, None
