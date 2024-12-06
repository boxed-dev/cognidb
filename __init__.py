# cognidb/__init__.py
import os
from typing import Any, Dict, List, Optional
from .db_connection import DBConnection
from .schema_fetcher import SchemaFetcher
from .user_input_processor import UserInputProcessor
from .llm_query_generator import LLMQueryGenerator
from .query_validator import QueryValidator
from .query_executor import QueryExecutor
from .clarification_handler import ClarificationHandler
from .utils import Utils
from .databases.mysql_db import MySQLDB
from .databases.postgres_db import PostgresDB

class CogniDB:
    def __init__(self, 
                 db_type: str = "mysql",
                 host: str = None,
                 port: int = None,
                 dbname: str = None,
                 user: str = None,
                 password: str = None,
                 api_key: str = None):
        
        # Try loading from environment variables if not provided
        self.host = host or os.getenv("HOST", "localhost")
        self.port = port or int(os.getenv("PORT", 3306 if db_type == "mysql" else 5432))
        self.dbname = dbname or os.getenv("DATABASE")
        self.user = user or os.getenv("USER")
        self.password = password or os.getenv("PASSWORD")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        if not all([self.dbname, self.user, self.password, self.api_key]):
            raise ValueError("Missing required configuration. Please provide all credentials.")
        
        # Initialize components
        self.db_driver = MySQLDB(self.host, self.port, self.dbname, self.user, self.password) if db_type == "mysql" \
            else PostgresDB(self.host, self.port, self.dbname, self.user, self.password)
        
        self.db_driver.connect()
        self.schema_fetcher = SchemaFetcher(self.db_driver)
        self.llm_generator = LLMQueryGenerator(self.api_key)
        self.validator = QueryValidator()
        self.executor = QueryExecutor(self.db_driver)
        
        # Cache the schema
        self.schema = self.schema_fetcher.fetch_schema()
    
    def query(self, natural_language_query: str) -> Dict[str, Any]:
        """
        Execute a natural language query and return results
        """
        try:
            # Generate SQL from natural language
            sql_query = self.llm_generator.generate_sql(natural_language_query, self.schema)
            
            # Validate the generated SQL
            self.validator.validate_sql(sql_query)
            
            # Execute the query
            results = self.executor.execute_sql(sql_query)
            
            return {
                "success": True,
                "sql_query": sql_query,
                "results": results
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def __del__(self):
        """Cleanup connection on deletion"""
        if hasattr(self, 'db_driver'):
            self.db_driver.conn.close()
