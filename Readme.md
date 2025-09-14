# <i><b>`CogniDB`</b></i>

A secure, production-ready natural language database interface that empowers users to query databases using plain English while maintaining enterprise-grade security and performance.<br>

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/adrienckr/cognidb)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org)

---

<samp>

## <b>Features</b>

### <b>Core Capabilities</b><br>
- <b>🗣️ Natural Language Querying</b>: Ask questions in plain English<br>
- <b>🔍 Intelligent SQL Generation</b>: Context-aware query generation with schema understanding<br>
- <b>🛡️ Enterprise Security</b>: Multi-layer security validation and sanitization<br>
- <b>🚀 High Performance</b>: Query caching, connection pooling, and optimization<br>
- <b>📊 Multi-Database Support</b>: MySQL, PostgreSQL, MongoDB, DynamoDB, SQLite<br>
- <b>💰 Cost Control</b>: LLM usage tracking with configurable limits<br>
- <b>📈 Query Optimization</b>: AI-powered query performance suggestions

### <b>Security Features</b><br>
- <b>SQL Injection Prevention</b>: Parameterized queries and comprehensive validation<br>
- <b>Access Control</b>: Table and column-level permissions<br>
- <b>Rate Limiting</b>: Configurable request limits<br>
- <b>Audit Logging</b>: Complete query audit trail<br>
- <b>Encryption</b>: At-rest and in-transit encryption support

### <b>AI/LLM Features</b><br>
- <b>Multi-Provider Support</b>: OpenAI, Anthropic, Azure, HuggingFace, Local models<br>
- <b>Cost Tracking</b>: Real-time usage and cost monitoring<br>
- <b>Smart Caching</b>: Reduce costs with intelligent response caching<br>
- <b>Few-Shot Learning</b>: Improve accuracy with custom examples

---

## <b>Quick Start</b>

### <b>Installation</b>

1. <b>`Install dependencies`</b><br>
   <code>pip install cognidb</code>

2. <b>`With all optional dependencies`</b><br>
   <code>pip install cognidb[all]</code>

3. <b>`With specific features`</b><br>
   <code>pip install cognidb[redis,azure]</code>

### <b>Basic Usage</b>

```python
from cognidb import create_cognidb

# Initialize with configuration
db = create_cognidb(
    database={
        'type': 'postgresql',
        'host': 'localhost',
        'database': 'mydb',
        'username': 'user',
        'password': 'pass'
    },
    llm={
        'provider': 'openai',
        'api_key': 'your-api-key'
    }
)

# Query in natural language
result = db.query("Show me the top 10 customers by total purchase amount")

if result['success']:
    print(f"SQL: {result['sql']}")
    print(f"Results: {result['results']}")

# Always close when done
db.close()
```

### <b>Using Context Manager</b>

```python
from cognidb import CogniDB

# Automatically handles connection cleanup
with CogniDB(config_file='cognidb.yaml') as db:
    result = db.query(
        "What were the sales trends last quarter?",
        explain=True  # Get explanation of the query
    )

    if result['success']:
        print(f"Explanation: {result['explanation']}")
        for row in result['results']:
            print(row)
```

---

## <b>Configuration</b>

### <b>Environment Variables</b>

```bash
# Database settings
export DB_TYPE=postgresql
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=mydb
export DB_USER=dbuser
export DB_PASSWORD=secure_password

# LLM settings
export LLM_PROVIDER=openai
export LLM_API_KEY=your_api_key
export LLM_MODEL=gpt-4

# Optional: Use configuration file instead
export COGNIDB_CONFIG=/path/to/cognidb.yaml
```

### <b>Configuration File (YAML)</b>

Create a <code>cognidb.yaml</code> file:

```yaml
database:
  type: postgresql
  host: localhost
  port: 5432
  database: analytics_db
  username: ${DB_USER}  # Use environment variable
  password: ${DB_PASSWORD}

  # Connection settings
  pool_size: 5
  query_timeout: 30
  ssl_enabled: true

llm:
  provider: openai
  api_key: ${LLM_API_KEY}
  model_name: gpt-4
  temperature: 0.1
  max_cost_per_day: 100.0

  # Improve accuracy with examples
  few_shot_examples:
    - query: "Show total sales by month"
      sql: "SELECT DATE_TRUNC('month', order_date) as month, SUM(amount) as total FROM orders GROUP BY month ORDER BY month"

security:
  allow_only_select: true
  enable_rate_limiting: true
  rate_limit_per_minute: 100
  enable_audit_logging: true
```

See <code>cognidb.example.yaml</code> for a complete configuration example.

---

## <b>Advanced Features</b>

### <b>Query Optimization</b>

```python
# Get optimization suggestions
sql = "SELECT * FROM orders WHERE customer_id IN (SELECT id FROM customers WHERE country = 'USA')"
optimization = db.optimize_query(sql)

print(f"Original: {optimization['original_query']}")
print(f"Optimized: {optimization['optimized_query']}")
print(f"Explanation: {optimization['explanation']}")
```

### <b>Query Suggestions</b>

```python
# Get AI-powered query suggestions
suggestions = db.suggest_queries("customers who haven't")
for suggestion in suggestions:
    print(f"- {suggestion}")
# Output:
# - customers who haven't made a purchase in the last 30 days
# - customers who haven't updated their profile
# - customers who haven't verified their email
```

### <b>Access Control</b>

```python
from cognidb.security import AccessController

# Set up user permissions
access = AccessController()
access.create_restricted_user(
    user_id="analyst_1",
    table_permissions={
        'customers': {
            'operations': ['SELECT'],
            'columns': ['id', 'name', 'email', 'country'],
            'row_filter': "country = 'USA'"  # Row-level security
        }
    }
)

# Query with user context
result = db.query(
    "Show me all customer emails",
    user_id="analyst_1"  # Will only see US customers
)
```

### <b>Cost Tracking</b>

```python
# Monitor LLM usage and costs
stats = db.get_usage_stats()
print(f"Total cost today: ${stats['daily_cost']:.2f}")
print(f"Remaining budget: ${stats['remaining_budget']:.2f}")
print(f"Queries today: {stats['request_count']}")

# Export usage report
report = db.export_usage_report(
    start_date='2024-01-01',
    end_date='2024-01-31',
    format='csv'
)
```

---

## <b>Architecture</b>

CogniDB uses a modular, secure architecture:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  User Input     │────▶│  Security Layer │────▶│  LLM Manager    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                │                         │
                                ▼                         ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │  Query Validator│     │ Query Generator │
                        └─────────────────┘     └─────────────────┘
                                │                         │
                                ▼                         ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │ Database Driver │────▶│  Result Cache   │
                        └─────────────────┘     └─────────────────┘
```

### <b>Key Components</b><br>
1. <b>Security Layer</b>: Multi-stage validation and sanitization<br>
2. <b>LLM Manager</b>: Handles all AI interactions with fallback support<br>
3. <b>Query Generator</b>: Converts natural language to SQL with schema awareness<br>
4. <b>Database Drivers</b>: Secure, parameterized database connections<br>
5. <b>Cache Layer</b>: Reduces costs and improves performance

---

## <b>Security Best Practices</b><br>
1. <b>Never expose credentials</b>: Use environment variables or secrets managers<br>
2. <b>Enable SSL/TLS</b>: Always use encrypted connections<br>
3. <b>Restrict permissions</b>: Use read-only database users when possible<br>
4. <b>Monitor usage</b>: Enable audit logging and review regularly<br>
5. <b>Update regularly</b>: Keep CogniDB and dependencies up to date

---

## <b>Testing</b>

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=cognidb

# Run security tests only
pytest tests/security/

# Run integration tests
pytest tests/integration/ --db-host=localhost
```

---

## <b>Performance Tips</b><br>
1. <b>Use connection pooling</b>: Enabled by default for better performance<br>
2. <b>Enable caching</b>: Reduces LLM costs and improves response time<br>
3. <b>Optimize schemas</b>: Add appropriate indexes based on query patterns<br>
4. <b>Use prepared statements</b>: For frequently executed queries<br>
5. <b>Monitor query performance</b>: Use the optimization feature regularly

---

## <b>Contributing</b>

We welcome contributions! Please see <a href="CONTRIBUTING.md">CONTRIBUTING.md</a> for guidelines.

### <b>Development Setup</b>

```bash
# Clone the repository
git clone https://github.com/adrienckr/cognidb
cd cognidb

# Install in development mode
pip install -e .[dev]

# Run pre-commit hooks
pre-commit install

# Run tests
pytest
```

---

## <b>License</b>

This project is licensed under the MIT License - see <a href="LICENSE">LICENSE</a> for details.

---

## <b>Acknowledgments</b><br>
- OpenAI, Anthropic, and the open-source LLM community<br>
- Contributors to SQLParse, psycopg2, and other dependencies<br>
- The CogniDB community for feedback and contributions

---

## <b>Support</b><br>
- <b>Documentation</b>: <a href="https://cognidb.readthedocs.io">https://cognidb.readthedocs.io</a><br>
- <b>Issues</b>: <a href="https://github.com/adrienckr/cognidb/issues">GitHub Issues</a><br>
- <b>Discussions</b>: <a href="https://github.com/adrienckr/cognidb/discussions">GitHub Discussions</a><br>
- <b>Email</b>: support@cognidb.io

---

<i>Built with ❤️ for data democratization</i>

</samp>
**Built with ❤️ for data democratization**