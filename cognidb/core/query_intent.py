"""Query intent representation - database agnostic query structure."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Dict, Any, Union


class QueryType(Enum):
    """Supported query types."""
    SELECT = auto()
    AGGREGATE = auto()
    COUNT = auto()
    DISTINCT = auto()


class ComparisonOperator(Enum):
    """Comparison operators for conditions."""
    EQ = "="
    NE = "!="
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    IN = "IN"
    NOT_IN = "NOT IN"
    LIKE = "LIKE"
    NOT_LIKE = "NOT LIKE"
    IS_NULL = "IS NULL"
    IS_NOT_NULL = "IS NOT NULL"
    BETWEEN = "BETWEEN"


class LogicalOperator(Enum):
    """Logical operators for combining conditions."""
    AND = "AND"
    OR = "OR"


class AggregateFunction(Enum):
    """Supported aggregate functions."""
    SUM = "SUM"
    AVG = "AVG"
    COUNT = "COUNT"
    MIN = "MIN"
    MAX = "MAX"
    GROUP_CONCAT = "GROUP_CONCAT"


class JoinType(Enum):
    """Types of joins."""
    INNER = "INNER"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    FULL = "FULL"


@dataclass
class Column:
    """Represents a column reference."""
    name: str
    table: Optional[str] = None
    alias: Optional[str] = None
    
    def __str__(self) -> str:
        if self.table:
            return f"{self.table}.{self.name}"
        return self.name


@dataclass
class Condition:
    """Represents a query condition."""
    column: Column
    operator: ComparisonOperator
    value: Any
    
    def __post_init__(self):
        """Validate condition parameters."""
        if self.operator == ComparisonOperator.BETWEEN:
            if not isinstance(self.value, (list, tuple)) or len(self.value) != 2:
                raise ValueError("BETWEEN operator requires a list/tuple of two values")
        elif self.operator in (ComparisonOperator.IN, ComparisonOperator.NOT_IN):
            if not isinstance(self.value, (list, tuple, set)):
                raise ValueError(f"{self.operator.value} operator requires a list/tuple/set")


@dataclass
class ConditionGroup:
    """Group of conditions with logical operator."""
    conditions: List[Union[Condition, 'ConditionGroup']]
    operator: LogicalOperator = LogicalOperator.AND
    
    def add_condition(self, condition: Union[Condition, 'ConditionGroup']):
        """Add a condition to the group."""
        self.conditions.append(condition)


@dataclass
class JoinCondition:
    """Represents a join between tables."""
    join_type: JoinType
    left_table: str
    right_table: str
    left_column: str
    right_column: str
    additional_conditions: Optional[ConditionGroup] = None


@dataclass
class Aggregation:
    """Represents an aggregation operation."""
    function: AggregateFunction
    column: Column
    alias: Optional[str] = None
    
    def __str__(self) -> str:
        return f"{self.function.value}({self.column})"


@dataclass
class OrderBy:
    """Represents ordering specification."""
    column: Column
    ascending: bool = True


@dataclass
class QueryIntent:
    """
    Database-agnostic representation of a query intent.
    
    This is the core abstraction that allows CogniDB to work with
    multiple database types by translating this intent into
    database-specific queries.
    """
    query_type: QueryType
    tables: List[str]
    columns: List[Column] = field(default_factory=list)
    conditions: Optional[ConditionGroup] = None
    joins: List[JoinCondition] = field(default_factory=list)
    aggregations: List[Aggregation] = field(default_factory=list)
    group_by: List[Column] = field(default_factory=list)
    having: Optional[ConditionGroup] = None
    order_by: List[OrderBy] = field(default_factory=list)
    limit: Optional[int] = None
    offset: Optional[int] = None
    distinct: bool = False
    
    # Metadata for optimization and caching
    natural_language_query: Optional[str] = None
    estimated_cost: Optional[float] = None
    cache_ttl: Optional[int] = None  # seconds
    
    def __post_init__(self):
        """Validate query intent."""
        if not self.tables:
            raise ValueError("At least one table must be specified")
        
        if self.query_type == QueryType.SELECT and not self.columns:
            # Default to all columns if none specified
            self.columns = [Column("*")]
        
        if self.aggregations and not self.group_by:
            # Check if all columns are aggregated
            non_aggregated = [
                col for col in self.columns 
                if not any(agg.column.name == col.name for agg in self.aggregations)
            ]
            if non_aggregated:
                raise ValueError(
                    "Non-aggregated columns must be in GROUP BY clause"
                )
        
        if self.having and not self.group_by:
            raise ValueError("HAVING clause requires GROUP BY")
    
    def add_column(self, column: Union[str, Column]):
        """Add a column to select."""
        if isinstance(column, str):
            column = Column(column)
        self.columns.append(column)
    
    def add_condition(self, condition: Condition):
        """Add a WHERE condition."""
        if not self.conditions:
            self.conditions = ConditionGroup([])
        self.conditions.add_condition(condition)
    
    def add_join(self, join: JoinCondition):
        """Add a join condition."""
        self.joins.append(join)
    
    def add_aggregation(self, aggregation: Aggregation):
        """Add an aggregation."""
        self.aggregations.append(aggregation)
        self.query_type = QueryType.AGGREGATE
    
    def set_limit(self, limit: int, offset: int = 0):
        """Set result limit and offset."""
        if limit <= 0:
            raise ValueError("Limit must be positive")
        if offset < 0:
            raise ValueError("Offset must be non-negative")
        self.limit = limit
        self.offset = offset
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'query_type': self.query_type.name,
            'tables': self.tables,
            'columns': [str(col) for col in self.columns],
            'conditions': self._condition_group_to_dict(self.conditions) if self.conditions else None,
            'joins': [self._join_to_dict(j) for j in self.joins],
            'aggregations': [str(agg) for agg in self.aggregations],
            'group_by': [str(col) for col in self.group_by],
            'having': self._condition_group_to_dict(self.having) if self.having else None,
            'order_by': [{'column': str(ob.column), 'asc': ob.ascending} for ob in self.order_by],
            'limit': self.limit,
            'offset': self.offset,
            'distinct': self.distinct,
            'natural_language_query': self.natural_language_query
        }
    
    def _condition_group_to_dict(self, group: ConditionGroup) -> Dict[str, Any]:
        """Convert condition group to dict."""
        return {
            'operator': group.operator.value,
            'conditions': [
                self._condition_to_dict(c) if isinstance(c, Condition) 
                else self._condition_group_to_dict(c)
                for c in group.conditions
            ]
        }
    
    def _condition_to_dict(self, condition: Condition) -> Dict[str, Any]:
        """Convert condition to dict."""
        return {
            'column': str(condition.column),
            'operator': condition.operator.value,
            'value': condition.value
        }
    
    def _join_to_dict(self, join: JoinCondition) -> Dict[str, Any]:
        """Convert join to dict."""
        return {
            'type': join.join_type.value,
            'left_table': join.left_table,
            'right_table': join.right_table,
            'left_column': join.left_column,
            'right_column': join.right_column
        }