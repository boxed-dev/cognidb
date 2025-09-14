"""
Basic usage examples for CogniDB.

This demonstrates how to use CogniDB for natural language database queries
with various configurations and features.
"""

import os
from cognidb import CogniDB, create_cognidb


def basic_example():
    """Basic usage with environment variables."""
    # Set environment variables (in production, use .env file or secrets manager)
    os.environ['DB_TYPE'] = 'postgresql'
    os.environ['DB_HOST'] = 'localhost'
    os.environ['DB_PORT'] = '5432'
    os.environ['DB_NAME'] = 'mydb'
    os.environ['DB_USER'] = 'myuser'
    os.environ['DB_PASSWORD'] = 'mypassword'
    os.environ['LLM_API_KEY'] = 'your-openai-api-key'
    
    # Create CogniDB instance
    with CogniDB() as db:
        # Simple query
        result = db.query("Show me all customers who made a purchase last month")
        
        if result['success']:
            print(f"Generated SQL: {result['sql']}")
            print(f"Found {result['row_count']} results")
            for row in result['results'][:5]:  # Show first 5
                print(row)
        else:
            print(f"Error: {result['error']}")


def config_file_example():
    """Usage with configuration file."""
    # Use configuration file
    with CogniDB(config_file='cognidb.yaml') as db:
        # Query with explanation
        result = db.query(
            "What are the top 5 products by revenue?",
            explain=True
        )
        
        if result['success']:
            print(f"SQL: {result['sql']}")
            print(f"\nExplanation: {result['explanation']}")
            print(f"\nResults:")
            for row in result['results']:
                print(f"  {row}")


def advanced_features_example():
    """Demonstrate advanced features."""
    db = create_cognidb(
        database={
            'type': 'postgresql',
            'host': 'localhost',
            'database': 'analytics_db'
        },
        llm={
            'provider': 'openai',
            'model_name': 'gpt-4',
            'temperature': 0.1
        }
    )
    
    try:
        # 1. Query suggestions
        suggestions = db.suggest_queries("customers who")
        print("Query suggestions:")
        for suggestion in suggestions:
            print(f"  - {suggestion}")
        
        # 2. Query optimization
        sql = "SELECT * FROM orders WHERE customer_id IN (SELECT id FROM customers WHERE country = 'USA')"
        optimization = db.optimize_query(sql)
        
        if optimization['success']:
            print(f"\nOriginal: {optimization['original_query']}")
            print(f"Optimized: {optimization['optimized_query']}")
            print(f"Explanation: {optimization['explanation']}")
        
        # 3. Schema inspection
        schema = db.get_schema('customers')
        print(f"\nCustomers table schema:")
        for column, dtype in schema['customers'].items():
            print(f"  {column}: {dtype}")
        
        # 4. Usage statistics
        stats = db.get_usage_stats()
        print(f"\nUsage stats:")
        print(f"  Total cost: ${stats['total_cost']:.2f}")
        print(f"  Requests today: {stats['request_count']}")
        
    finally:
        db.close()


def multi_database_example():
    """Example with different database types."""
    databases = [
        {
            'type': 'mysql',
            'config': {
                'host': 'mysql.example.com',
                'database': 'app_db'
            }
        },
        {
            'type': 'postgresql',
            'config': {
                'host': 'postgres.example.com',
                'database': 'analytics_db'
            }
        },
        {
            'type': 'sqlite',
            'config': {
                'database': '/path/to/local.db'
            }
        }
    ]
    
    for db_info in databases:
        print(f"\nQuerying {db_info['type']} database:")
        
        with create_cognidb(database=db_info['config']) as db:
            result = db.query("Count the total number of records in the main table")
            
            if result['success']:
                print(f"  SQL: {result['sql']}")
                print(f"  Result: {result['results']}")


def security_example():
    """Demonstrate security features."""
    # Configure with strict security
    db = create_cognidb(
        security={
            'allow_only_select': True,
            'max_query_complexity': 5,
            'allow_subqueries': False,
            'enable_rate_limiting': True,
            'rate_limit_per_minute': 10
        }
    )
    
    # These queries will be validated
    safe_queries = [
        "Show me all active users",
        "What's the average order value?",
        "List products with low stock"
    ]
    
    # These will be rejected
    unsafe_queries = [
        "Delete all users where active = false",  # Not SELECT
        "Update products set price = price * 1.1",  # Not SELECT
        "'; DROP TABLE users; --",  # SQL injection attempt
    ]
    
    print("Testing safe queries:")
    for query in safe_queries:
        result = db.query(query)
        print(f"  '{query}' - Success: {result['success']}")
    
    print("\nTesting unsafe queries (should be rejected):")
    for query in unsafe_queries:
        result = db.query(query)
        print(f"  '{query}' - Success: {result['success']}, Error: {result.get('error', '')[:50]}...")
    
    db.close()


def custom_llm_example():
    """Example with custom LLM configuration."""
    # Use Anthropic Claude
    db_claude = create_cognidb(
        llm={
            'provider': 'anthropic',
            'api_key': os.environ.get('ANTHROPIC_API_KEY'),
            'model_name': 'claude-3-sonnet',
            'temperature': 0.0
        }
    )
    
    # Use local model
    db_local = create_cognidb(
        llm={
            'provider': 'local',
            'local_model_path': '/path/to/model.gguf',
            'max_tokens': 500
        }
    )
    
    # Use Azure OpenAI
    db_azure = create_cognidb(
        llm={
            'provider': 'azure_openai',
            'api_key': os.environ.get('AZURE_OPENAI_KEY'),
            'azure_endpoint': 'https://myorg.openai.azure.com/',
            'azure_deployment': 'gpt-4-deployment'
        }
    )


if __name__ == "__main__":
    # Run examples
    print("=== Basic Example ===")
    basic_example()
    
    print("\n=== Config File Example ===")
    config_file_example()
    
    print("\n=== Advanced Features ===")
    advanced_features_example()
    
    print("\n=== Security Example ===")
    security_example()