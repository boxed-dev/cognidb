"""Query generator using LLM with advanced features."""

from __future__ import annotations

import re
from typing import Any

from ..core.exceptions import TranslationError
from ..core.query_intent import QueryIntent
from ..security.sanitizer import InputSanitizer
from .intent_schema import intent_from_json
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
                    schema: dict[str, dict[str, str]],
                    examples: list[dict[str, str]] | None = None,
                    context: dict[str, Any] | None = None) -> str:
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
            raise TranslationError(f"Failed to generate SQL: {str(e)}") from e
    
    def generate_intent(self,
                       natural_language_query: str,
                       schema: dict[str, dict[str, str]],
                       examples: list[dict[str, str]] | None = None) -> QueryIntent:
        """Generate a structured QueryIntent from natural language (intent mode).

        The LLM emits a JSON intent (never raw SQL); it is deserialized fail-closed
        and later rendered with bound parameters. This is the secure default path.

        Raises:
            TranslationError: If generation or intent parsing fails.
        """
        sanitized_query = self.sanitizer.sanitize_natural_language(natural_language_query)
        prompt = self.prompt_builder.build_intent_generation_prompt(
            sanitized_query, schema, examples
        )
        try:
            response = self.llm_manager.generate(prompt)
            return intent_from_json(response.content)
        except Exception as e:
            raise TranslationError(f"Failed to generate query intent: {e}") from e
    
    def explain_query(self,
                     sql_query: str,
                     schema: dict[str, dict[str, str]]) -> str:
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
                      schema: dict[str, dict[str, str]],
                      performance_stats: dict[str, Any] | None = None) -> tuple[str, str]:
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
                       schema: dict[str, dict[str, str]],
                       num_suggestions: int = 3) -> list[str]:
        """
        Generate query suggestions based on partial input.
        
        Args:
            partial_query: Partial natural language query
            schema: Database schema
            num_suggestions: Number of suggestions to generate
            
        Returns:
            List of suggested queries
        """
        prompt = (
            f"Based on the database schema and partial query, "
            f"suggest {num_suggestions} complete queries."
            f"""

Database Schema:
{self.prompt_builder._build_schema_description(schema)}

Partial Query: {partial_query}

Generate {num_suggestions} relevant query suggestions that complete or expand on the partial query.
Format each suggestion on a new line starting with "- ".

Suggestions:"""
        )

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