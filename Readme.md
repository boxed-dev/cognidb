# CogniDB 🧠

**A secure, production-ready natural language database interface** that empowers users to query databases using plain English while maintaining enterprise-grade security and performance.

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/adrienckr/cognidb)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org)

---

> **🔒 Security First**: CogniDB has been completely rebuilt with security as the top priority. All queries are validated, sanitized, and executed with proper parameterization to prevent SQL injection and other attacks.

---

## ✨ Features

### Core Capabilities
- **🗣️ Natural Language Querying**: Ask questions in plain English
- **🔍 Intelligent SQL Generation**: Context-aware query generation with schema understanding
- **🛡️ Enterprise Security**: Multi-layer security validation and sanitization
- **🚀 High Performance**: Query caching, connection pooling, and optimization
- **📊 Multi-Database Support**: MySQL, PostgreSQL, MongoDB, DynamoDB, SQLite
- **💰 Cost Control**: LLM usage tracking with configurable limits
- **📈 Query Optimization**: AI-powered query performance suggestions

### Security Features
- **SQL Injection Prevention**: Parameterized queries and comprehensive validation
- **Access Control**: Table and column-level permissions
- **Rate Limiting**: Configurable request limits
- **Audit Logging**: Complete query audit trail
- **Encryption**: At-rest and in-transit encryption support

### AI/LLM Features
- **Multi-Provider Support**: OpenAI, Anthropic, Azure, HuggingFace, Local models
- **Cost Tracking**: Real-time usage and cost monitoring
- **Smart Caching**: Reduce costs with intelligent response caching
- **Few-Shot Learning**: Improve accuracy with custom examples

---

## 🚀 Quick Start

### Installation

```bash
# Basic installation
pip install cognidb

# With all optional dependencies
pip install cognidb[all]

# With specific features
pip install cognidb[redis,azure]
```

### Basic Usage

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

### Using Context Manager

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

## 🔧 Configuration

### Environment Variables

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

### Configuration File (YAML)

Create a `cognidb.yaml` file:

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

See `cognidb.example.yaml` for a complete configuration example.

---

## 🎯 Advanced Features

### Query Optimization

```python
# Get optimization suggestions
sql = "SELECT * FROM orders WHERE customer_id IN (SELECT id FROM customers WHERE country = 'USA')"
optimization = db.optimize_query(sql)

print(f"Original: {optimization['original_query']}")
print(f"Optimized: {optimization['optimized_query']}")
print(f"Explanation: {optimization['explanation']}")
```

### Query Suggestions

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

### Access Control

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

### Cost Tracking

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

## 🏗️ Architecture

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

### Key Components

1. **Security Layer**: Multi-stage validation and sanitization
2. **LLM Manager**: Handles all AI interactions with fallback support
3. **Query Generator**: Converts natural language to SQL with schema awareness
4. **Database Drivers**: Secure, parameterized database connections
5. **Cache Layer**: Reduces costs and improves performance

---

## 🔒 Security Best Practices

1. **Never expose credentials**: Use environment variables or secrets managers
2. **Enable SSL/TLS**: Always use encrypted connections
3. **Restrict permissions**: Use read-only database users when possible
4. **Monitor usage**: Enable audit logging and review regularly
5. **Update regularly**: Keep CogniDB and dependencies up to date

---

## 🧪 Testing

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

## 📊 Performance Tips

1. **Use connection pooling**: Enabled by default for better performance
2. **Enable caching**: Reduces LLM costs and improves response time
3. **Optimize schemas**: Add appropriate indexes based on query patterns
4. **Use prepared statements**: For frequently executed queries
5. **Monitor query performance**: Use the optimization feature regularly

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

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

## 📜 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- OpenAI, Anthropic, and the open-source LLM community
- Contributors to SQLParse, psycopg2, and other dependencies
- The CogniDB community for feedback and contributions

---

## 📞 Support

- **Documentation**: [https://cognidb.readthedocs.io](https://cognidb.readthedocs.io)
- **Issues**: [GitHub Issues](https://github.com/adrienckr/cognidb/issues)
- **Discussions**: [GitHub Discussions](https://github.com/adrienckr/cognidb/discussions)
- **Email**: support@cognidb.io

---

**Built with ❤️ for data democratization**