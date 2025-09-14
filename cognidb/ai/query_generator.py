"""Query generator using LLM with advanced features."""

import re
from typing import Dict, Any, List, Optional, Tuple
from ..core.query_intent import QueryIntent, QueryType, Column, Condition, ComparisonOperator
from ..core.exceptions import TranslationError
from ..security.sanitizer import InputSanitizer
from .llm_manager import LLMManager
from .prompt_builder import PromptBuilder


class QueryGenerator:
    """
    Generates SQL queries from natural language using LLM.
    
    Features:
    - Natural language to SQL conversion
    - Query intent parsing
    - Schema-aware generation
    - Query validation and correction
    - Caching for repeated queries
    """
    
    def __init__(self,
                 llm_manager: LLMManager,
                 database_type: str = 'postgresql'):
        """
        Initialize query generator.
        
        Args:
            llm_manager: LLM manager instance
            database_type: Type of database
        """
        self.llm_manager = llm_manager
        self.database_type = database_type
        self.prompt_builder = PromptBuilder(database_type)
        self.sanitizer = InputSanitizer()
    
    def generate_sql(self,
                    natural_language_query: str,
                    schema: Dict[str, Dict[str, str]],
                    examples: Optional[List[Dict[str, str]]] = None,
                    context: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate SQL from natural language query.
        
        Args:
            natural_language_query: User's query in natural language
            schema: Database schema
            examples: Optional few-shot examples
            context: Optional context information
            
        Returns:
            Generated SQL query
            
        Raises:
            TranslationError: If SQL generation fails
        """
        # Sanitize input
        sanitized_query = self.sanitizer.sanitize_natural_language(natural_language_query)
        
        # Build prompt
        prompt = self.prompt_builder.build_sql_generation_prompt(
            sanitized_query,
            schema,
            examples,
            context
        )
        
        # Generate SQL
        try:
            response = self.llm_manager.generate(prompt)
            sql_query = self._extract_sql(response.content)
            
            # Validate basic SQL structure
            if not self._is_valid_sql(sql_query):
                raise TranslationError("Generated SQL is invalid")
            
            return sql_query
            
        except Exception as e:
            raise TranslationError(f"Failed to generate SQL: {str(e)}")
    
    def parse_to_intent(self,
                       natural_language_query: str,
                       schema: Dict[str, Dict[str, str]]) -> QueryIntent:
        """
        Parse natural language to QueryIntent.
        
        Args:
            natural_language_query: User's query
            schema: Database schema
            
        Returns:
            Parsed QueryIntent
        """
        # First generate SQL
        sql_query = self.generate_sql(natural_language_query, schema)
        
        # Then parse SQL to QueryIntent
        return self._parse_sql_to_intent(sql_query, schema)
    
    def explain_query(self,
                     sql_query: str,
                     schema: Dict[str, Dict[str, str]]) -> str:
        """
        Generate natural language explanation of SQL query.
        
        Args:
            sql_query: SQL query to explain
            schema: Database schema
            
        Returns:
            Natural language explanation
        """
        prompt = self.prompt_builder.build_query_explanation_prompt(sql_query, schema)
        
        try:
            response = self.llm_manager.generate(prompt, temperature=0.3)
            return response.content
        except Exception as e:
            return f"Could not generate explanation: {str(e)}"
    
    def optimize_query(self,
                      sql_query: str,
                      schema: Dict[str, Dict[str, str]],
                      performance_stats: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        """
        Generate optimized version of SQL query.
        
        Args:
            sql_query: SQL query to optimize
            schema: Database schema with indexes
            performance_stats: Optional performance statistics
            
        Returns:
            Tuple of (optimized_query, explanation)
        """
        prompt = self.prompt_builder.build_optimization_prompt(
            sql_query,
            schema,
            performance_stats
        )
        
        try:
            response = self.llm_manager.generate(prompt, temperature=0.2)
            
            # Extract optimized query and explanation
            content = response.content
            if "```sql" in content:
                # Extract SQL from markdown
                sql_match = re.search(r'```sql\n(.*?)\n```', content, re.DOTALL)
                if sql_match:
                    optimized_query = sql_match.group(1).strip()
                    explanation = content.replace(sql_match.group(0), '').strip()
                    return optimized_query, explanation
            
            # Try to split by common patterns
            lines = content.split('\n')
            sql_lines = []
            explanation_lines = []
            in_sql = True
            
            for line in lines:
                if line.strip() and not line.startswith(('--', '#', '//')):
                    if in_sql and any(keyword in line.upper() for keyword in 
                                    ['EXPLANATION:', 'CHANGES:', 'OPTIMIZATION:']):
                        in_sql = False
                    
                    if in_sql:
                        sql_lines.append(line)
                    else:
                        explanation_lines.append(line)
            
            optimized_query = '\n'.join(sql_lines).strip()
            explanation = '\n'.join(explanation_lines).strip()
            
            return optimized_query, explanation
            
        except Exception as e:
            return sql_query, f"Could not optimize: {str(e)}"
    
    def suggest_queries(self,
                       partial_query: str,
                       schema: Dict[str, Dict[str, str]],
                       num_suggestions: int = 3) -> List[str]:
        """
        Generate query suggestions based on partial input.
        
        Args:
            partial_query: Partial natural language query
            schema: Database schema
            num_suggestions: Number of suggestions to generate
            
        Returns:
            List of suggested queries
        """
        prompt = f"""Based on the database schema and partial query, suggest {num_suggestions} complete queries.

Database Schema:
{self.prompt_builder._build_schema_description(schema)}

Partial Query: {partial_query}

Generate {num_suggestions} relevant query suggestions that complete or expand on the partial query.
Format each suggestion on a new line starting with "- ".

Suggestions:"""
        
        try:
            response = self.llm_manager.generate(prompt, temperature=0.7)
            
            # Extract suggestions
            suggestions = []
            for line in response.content.split('\n'):
                if line.strip().startswith('- '):
                    suggestion = line.strip()[2:].strip()
                    if suggestion:
                        suggestions.append(suggestion)
            
            return suggestions[:num_suggestions]
            
        except Exception:
            return []
    
    def _extract_sql(self, llm_response: str) -> str:
        """Extract SQL query from LLM response."""
        # Remove markdown code blocks if present
        if "```sql" in llm_response:
            match = re.search(r'```sql\n(.*?)\n```', llm_response, re.DOTALL)
            if match:
                llm_response = match.group(1)
        elif "```" in llm_response:
            match = re.search(r'```\n(.*?)\n```', llm_response, re.DOTALL)
            if match:
                llm_response = match.group(1)
        
        # Clean up the response
        sql_query = llm_response.strip()
        
        # Remove any leading/trailing quotes
        if sql_query.startswith('"') and sql_query.endswith('"'):
            sql_query = sql_query[1:-1]
        elif sql_query.startswith("'") and sql_query.endswith("'"):
            sql_query = sql_query[1:-1]
        
        # Ensure it ends with semicolon
        if not sql_query.endswith(';'):
            sql_query += ';'
        
        return sql_query
    
    def _is_valid_sql(self, sql_query: str) -> bool:
        """Basic SQL validation."""
        if not sql_query or not sql_query.strip():
            return False
        
        # Check for basic SQL structure
        sql_upper = sql_query.upper()
        valid_starts = ['SELECT', 'WITH', 'SHOW', 'DESCRIBE', 'EXPLAIN']
        
        return any(sql_upper.strip().startswith(start) for start in valid_starts)
    
    def _parse_sql_to_intent(self, sql_query: str, schema: Dict[str, Dict[str, str]]) -> QueryIntent:
        """
        Parse SQL query to QueryIntent (simplified version).
        
        This is a basic implementation. In production, you'd want
        a full SQL parser.
        """
        # Extract tables (basic regex approach)
        tables = []
        from_match = re.search(r'FROM\s+(\w+)', sql_query, re.IGNORECASE)
        if from_match:
            tables.append(from_match.group(1))
        
        # Extract columns (basic approach)
        columns = []
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql_query, re.IGNORECASE | re.DOTALL)
        if select_match:
            column_str = select_match.group(1)
            if column_str.strip() == '*':
                columns = [Column('*')]
            else:
                # Simple split by comma (doesn't handle complex cases)
                for col in column_str.split(','):
                    col = col.strip()
                    if ' AS ' in col.upper():
                        parts = re.split(r'\s+AS\s+', col, flags=re.IGNORECASE)
                        columns.append(Column(parts[0].strip(), alias=parts[1].strip()))
                    else:
                        columns.append(Column(col))
        
        # Create basic QueryIntent
        intent = QueryIntent(
            query_type=QueryType.SELECT,
            tables=tables,
            columns=columns,
            natural_language_query=sql_query
        )
        
        return intent