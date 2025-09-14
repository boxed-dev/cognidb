"""Advanced prompt builder for SQL generation."""

from typing import Dict, List, Any, Optional
from ..core.query_intent import QueryIntent


class PromptBuilder:
    """
    Builds optimized prompts for SQL generation.
    
    Features:
    - Schema-aware prompts
    - Few-shot examples
    - Database-specific hints
    - Query optimization suggestions
    """
    
    # Database-specific SQL dialects
    SQL_DIALECTS = {
        'mysql': {
            'limit': 'LIMIT {limit}',
            'string_concat': "CONCAT({args})",
            'current_date': 'CURDATE()',
            'date_format': "DATE_FORMAT({date}, '{format}')"
        },
        'postgresql': {
            'limit': 'LIMIT {limit}',
            'string_concat': "{args}",  # Uses ||
            'current_date': 'CURRENT_DATE',
            'date_format': "TO_CHAR({date}, '{format}')"
        },
        'sqlite': {
            'limit': 'LIMIT {limit}',
            'string_concat': "{args}",  # Uses ||
            'current_date': "DATE('now')",
            'date_format': "STRFTIME('{format}', {date})"
        }
    }
    
    def __init__(self, database_type: str = 'postgresql'):
        """
        Initialize prompt builder.
        
        Args:
            database_type: Type of database (mysql, postgresql, sqlite)
        """
        self.database_type = database_type
        self.dialect = self.SQL_DIALECTS.get(database_type, self.SQL_DIALECTS['postgresql'])
    
    def build_sql_generation_prompt(self,
                                  natural_language_query: str,
                                  schema: Dict[str, Dict[str, str]],
                                  examples: Optional[List[Dict[str, str]]] = None,
                                  context: Optional[Dict[str, Any]] = None) -> str:
        """
        Build prompt for SQL generation.
        
        Args:
            natural_language_query: User's natural language query
            schema: Database schema
            examples: Optional few-shot examples
            context: Optional context (user preferences, constraints)
            
        Returns:
            Optimized prompt for LLM
        """
        # Build schema description
        schema_desc = self._build_schema_description(schema)
        
        # Build examples section
        examples_section = ""
        if examples:
            examples_section = self._build_examples_section(examples)
        
        # Build context hints
        context_hints = self._build_context_hints(context or {})
        
        # Construct the prompt
        prompt = f"""You are an expert SQL query generator for {self.database_type} databases.

Database Schema:
{schema_desc}

{context_hints}

Important Instructions:
1. Generate ONLY the SQL query, no explanations or markdown
2. Use proper {self.database_type} syntax and functions
3. Always use table aliases for clarity
4. Include appropriate JOINs when querying multiple tables
5. Use parameterized placeholders (?) for any user-provided values
6. Ensure the query is optimized for performance
7. Handle NULL values appropriately
8. Use appropriate data type conversions when needed

{examples_section}

Now generate a SQL query for the following request:
User Query: {natural_language_query}

SQL Query:"""
        
        return prompt
    
    def build_query_explanation_prompt(self,
                                     sql_query: str,
                                     schema: Dict[str, Dict[str, str]]) -> str:
        """
        Build prompt for explaining SQL query.
        
        Args:
            sql_query: SQL query to explain
            schema: Database schema
            
        Returns:
            Prompt for explanation
        """
        schema_desc = self._build_schema_description(schema)
        
        return f"""Explain the following SQL query in simple terms:

Database Schema:
{schema_desc}

SQL Query:
{sql_query}

Provide a clear, concise explanation of:
1. What the query does
2. Which tables and columns it uses
3. Any filters or conditions applied
4. The expected result format

Explanation:"""
    
    def build_optimization_prompt(self,
                                sql_query: str,
                                schema: Dict[str, Dict[str, str]],
                                performance_stats: Optional[Dict[str, Any]] = None) -> str:
        """
        Build prompt for query optimization suggestions.
        
        Args:
            sql_query: SQL query to optimize
            schema: Database schema with index information
            performance_stats: Optional query performance statistics
            
        Returns:
            Prompt for optimization
        """
        schema_desc = self._build_schema_description(schema, include_indexes=True)
        
        perf_section = ""
        if performance_stats:
            perf_section = f"\nPerformance Stats:\n{self._format_performance_stats(performance_stats)}"
        
        return f"""Analyze and optimize the following SQL query:

Database Schema:
{schema_desc}

Current Query:
{sql_query}
{perf_section}

Provide optimization suggestions considering:
1. Index usage
2. JOIN optimization
3. Subquery elimination
4. Filtering efficiency
5. Result set size reduction

Optimized Query and Explanation:"""
    
    def build_intent_to_sql_prompt(self,
                                 query_intent: QueryIntent,
                                 database_type: str) -> str:
        """
        Build prompt to convert QueryIntent to SQL.
        
        Args:
            query_intent: Parsed query intent
            database_type: Target database type
            
        Returns:
            Prompt for SQL generation
        """
        intent_desc = self._describe_query_intent(query_intent)
        
        return f"""Convert the following query specification to {database_type} SQL:

Query Specification:
{intent_desc}

Generate a properly formatted {database_type} SQL query that implements this specification.
Use appropriate syntax and functions for {database_type}.

SQL Query:"""
    
    def _build_schema_description(self, 
                                schema: Dict[str, Dict[str, str]],
                                include_indexes: bool = False) -> str:
        """Build formatted schema description."""
        lines = []
        
        for table_name, columns in schema.items():
            lines.append(f"Table: {table_name}")
            
            for col_name, col_type in columns.items():
                lines.append(f"  - {col_name}: {col_type}")
            
            if include_indexes and f"{table_name}_indexes" in schema:
                lines.append("  Indexes:")
                for index in schema[f"{table_name}_indexes"]:
                    lines.append(f"    - {index}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _build_examples_section(self, examples: List[Dict[str, str]]) -> str:
        """Build few-shot examples section."""
        if not examples:
            return ""
        
        lines = ["Examples of similar queries:\n"]
        
        for i, example in enumerate(examples, 1):
            lines.append(f"Example {i}:")
            lines.append(f"User Query: {example['query']}")
            lines.append(f"SQL: {example['sql']}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _build_context_hints(self, context: Dict[str, Any]) -> str:
        """Build context-specific hints."""
        hints = []
        
        if context.get('timezone'):
            hints.append(f"Timezone: {context['timezone']} (adjust date/time queries accordingly)")
        
        if context.get('date_format'):
            hints.append(f"Preferred date format: {context['date_format']}")
        
        if context.get('limit_default'):
            hints.append(f"Default result limit: {context['limit_default']}")
        
        if context.get('case_sensitive'):
            hints.append("Use case-sensitive string comparisons")
        
        if context.get('exclude_deleted'):
            hints.append("Exclude soft-deleted records (check for deleted_at IS NULL)")
        
        if hints:
            return "Context:\n" + "\n".join(f"- {hint}" for hint in hints) + "\n"
        
        return ""
    
    def _describe_query_intent(self, query_intent: QueryIntent) -> str:
        """Convert QueryIntent to human-readable description."""
        lines = []
        
        lines.append(f"Query Type: {query_intent.query_type.name}")
        lines.append(f"Tables: {', '.join(query_intent.tables)}")
        
        if query_intent.columns:
            cols = [str(col) for col in query_intent.columns]
            lines.append(f"Columns: {', '.join(cols)}")
        
        if query_intent.joins:
            lines.append("Joins:")
            for join in query_intent.joins:
                lines.append(
                    f"  - {join.join_type.value} JOIN {join.right_table} "
                    f"ON {join.left_table}.{join.left_column} = "
                    f"{join.right_table}.{join.right_column}"
                )
        
        if query_intent.conditions:
            lines.append("Conditions: [Complex condition group]")
        
        if query_intent.group_by:
            cols = [str(col) for col in query_intent.group_by]
            lines.append(f"Group By: {', '.join(cols)}")
        
        if query_intent.order_by:
            order_specs = []
            for order in query_intent.order_by:
                direction = "ASC" if order.ascending else "DESC"
                order_specs.append(f"{order.column} {direction}")
            lines.append(f"Order By: {', '.join(order_specs)}")
        
        if query_intent.limit:
            lines.append(f"Limit: {query_intent.limit}")
            if query_intent.offset:
                lines.append(f"Offset: {query_intent.offset}")
        
        return "\n".join(lines)
    
    def _format_performance_stats(self, stats: Dict[str, Any]) -> str:
        """Format performance statistics."""
        lines = []
        
        if 'execution_time' in stats:
            lines.append(f"- Execution Time: {stats['execution_time']}ms")
        
        if 'rows_examined' in stats:
            lines.append(f"- Rows Examined: {stats['rows_examined']}")
        
        if 'rows_returned' in stats:
            lines.append(f"- Rows Returned: {stats['rows_returned']}")
        
        if 'index_used' in stats:
            lines.append(f"- Index Used: {stats['index_used']}")
        
        return "\n".join(lines)