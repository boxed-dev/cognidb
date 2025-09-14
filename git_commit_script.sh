#!/bin/bash

# Script to create multiple logical commits for CogniDB v2.0.0
# Each commit adds related files with appropriate messages

echo "Starting CogniDB v2.0.0 commit process..."

# Commit 1: Core abstractions and interfaces
echo "Creating commit 1: Core abstractions..."
git add cognidb/core/__init__.py
git add cognidb/core/exceptions.py
git add cognidb/core/interfaces.py
git add cognidb/core/query_intent.py
git commit -m "feat(core): Add core abstractions and interfaces

- Implement QueryIntent for database-agnostic query representation
- Define abstract interfaces for drivers, translators, and validators
- Add comprehensive exception hierarchy
- Create foundation for modular architecture

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

# Commit 2: Security layer
echo "Creating commit 2: Security layer..."
git add cognidb/security/__init__.py
git add cognidb/security/validator.py
git add cognidb/security/sanitizer.py
git add cognidb/security/query_parser.py
git add cognidb/security/access_control.py
git commit -m "feat(security): Implement comprehensive security layer

- Add multi-layer query validation to prevent SQL injection
- Implement input sanitization for all user inputs
- Create SQL query parser for security analysis
- Add access control with table/column/row-level permissions
- Enforce parameterized queries throughout

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

# Commit 3: Configuration management
echo "Creating commit 3: Configuration system..."
git add cognidb/config/__init__.py
git add cognidb/config/settings.py
git add cognidb/config/secrets.py
git add cognidb/config/loader.py
git add cognidb.example.yaml
git commit -m "feat(config): Add flexible configuration management

- Implement settings with dataclasses for type safety
- Add secrets manager supporting multiple providers (env, file, AWS, Vault)
- Create config loader with YAML/JSON/env support
- Add example configuration file
- Support for environment variable interpolation

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

# Commit 4: AI/LLM integration
echo "Creating commit 4: AI/LLM integration..."
git add cognidb/ai/__init__.py
git add cognidb/ai/llm_manager.py
git add cognidb/ai/providers.py
git add cognidb/ai/prompt_builder.py
git add cognidb/ai/query_generator.py
git add cognidb/ai/cost_tracker.py
git commit -m "feat(ai): Implement modern LLM integration

- Add multi-provider support (OpenAI, Anthropic, Azure, HuggingFace, Local)
- Implement cost tracking with daily limits
- Create advanced prompt builder with few-shot learning
- Add query generation with optimization suggestions
- Include response caching to reduce costs
- Support streaming and fallback providers

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

# Commit 5: Database drivers
echo "Creating commit 5: Secure database drivers..."
git add cognidb/drivers/__init__.py
git add cognidb/drivers/base_driver.py
git add cognidb/drivers/mysql_driver.py
git add cognidb/drivers/postgres_driver.py
git commit -m "feat(drivers): Add secure database drivers

- Implement base driver with common functionality
- Add MySQL driver with connection pooling and SSL support
- Add PostgreSQL driver with prepared statements
- Use parameterized queries exclusively
- Include timeout management and result limiting
- Add schema caching for performance

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

# Commit 6: Main CogniDB class
echo "Creating commit 6: Main CogniDB interface..."
git add __init__.py
git commit -m "feat: Implement main CogniDB class with new architecture

- Create unified interface for natural language queries
- Integrate all components (security, AI, drivers, config)
- Add context manager support
- Include query optimization and suggestions
- Implement audit logging
- Add comprehensive error handling

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

# Commit 7: Documentation and examples
echo "Creating commit 7: Documentation and examples..."
git add Readme.md
git add examples/basic_usage.py
git commit -m "docs: Update documentation for v2.0.0

- Rewrite README with security-first approach
- Add comprehensive usage examples
- Document all features and configuration options
- Include security best practices
- Add performance tips
- Update badges and project description

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

# Commit 8: Package setup and requirements
echo "Creating commit 8: Package configuration..."
git add setup.py
git add requirements.txt
git commit -m "build: Update package configuration for v2.0.0

- Update requirements with all dependencies
- Configure setup.py with optional extras
- Add proper classifiers and metadata
- Include console script entry point
- Separate core and optional dependencies

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

# Commit 9: Remove old insecure files
echo "Creating commit 9: Clean up old implementation..."
git add -A
git commit -m "refactor: Remove old insecure implementation

- Remove vulnerable SQL string interpolation code
- Delete unused modules (clarification_handler, user_input_processor)
- Remove redundant wrappers (db_connection, schema_fetcher)
- Clean up old database implementations
- Remove insecure query validator
- Delete analysis report

BREAKING CHANGE: Complete API redesign for v2.0.0

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

echo "All commits created successfully!"
echo ""
echo "Repository status:"
git status
echo ""
echo "Commit history:"
git log --oneline -n 9