@echo off
REM Script to create multiple logical commits for CogniDB v2.0.0
REM Each commit adds related files with appropriate messages

echo Starting CogniDB v2.0.0 commit process...
echo.

REM Commit 1: Core abstractions and interfaces
echo Creating commit 1: Core abstractions...
git add cognidb/core/__init__.py
git add cognidb/core/exceptions.py
git add cognidb/core/interfaces.py
git add cognidb/core/query_intent.py
git commit -m "feat(core): Add core abstractions and interfaces" -m "" -m "- Implement QueryIntent for database-agnostic query representation" -m "- Define abstract interfaces for drivers, translators, and validators" -m "- Add comprehensive exception hierarchy" -m "- Create foundation for modular architecture" -m "" -m "🤖 Generated with Claude Code" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
echo.

REM Commit 2: Security layer
echo Creating commit 2: Security layer...
git add cognidb/security/__init__.py
git add cognidb/security/validator.py
git add cognidb/security/sanitizer.py
git add cognidb/security/query_parser.py
git add cognidb/security/access_control.py
git commit -m "feat(security): Implement comprehensive security layer" -m "" -m "- Add multi-layer query validation to prevent SQL injection" -m "- Implement input sanitization for all user inputs" -m "- Create SQL query parser for security analysis" -m "- Add access control with table/column/row-level permissions" -m "- Enforce parameterized queries throughout" -m "" -m "🤖 Generated with Claude Code" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
echo.

REM Commit 3: Configuration management
echo Creating commit 3: Configuration system...
git add cognidb/config/__init__.py
git add cognidb/config/settings.py
git add cognidb/config/secrets.py
git add cognidb/config/loader.py
git add cognidb.example.yaml
git commit -m "feat(config): Add flexible configuration management" -m "" -m "- Implement settings with dataclasses for type safety" -m "- Add secrets manager supporting multiple providers" -m "- Create config loader with YAML/JSON/env support" -m "- Add example configuration file" -m "- Support for environment variable interpolation" -m "" -m "🤖 Generated with Claude Code" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
echo.

REM Commit 4: AI/LLM integration
echo Creating commit 4: AI/LLM integration...
git add cognidb/ai/__init__.py
git add cognidb/ai/llm_manager.py
git add cognidb/ai/providers.py
git add cognidb/ai/prompt_builder.py
git add cognidb/ai/query_generator.py
git add cognidb/ai/cost_tracker.py
git commit -m "feat(ai): Implement modern LLM integration" -m "" -m "- Add multi-provider support (OpenAI, Anthropic, Azure, etc)" -m "- Implement cost tracking with daily limits" -m "- Create advanced prompt builder with few-shot learning" -m "- Add query generation with optimization suggestions" -m "- Include response caching to reduce costs" -m "- Support streaming and fallback providers" -m "" -m "🤖 Generated with Claude Code" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
echo.

REM Commit 5: Database drivers
echo Creating commit 5: Secure database drivers...
git add cognidb/drivers/__init__.py
git add cognidb/drivers/base_driver.py
git add cognidb/drivers/mysql_driver.py
git add cognidb/drivers/postgres_driver.py
git commit -m "feat(drivers): Add secure database drivers" -m "" -m "- Implement base driver with common functionality" -m "- Add MySQL driver with connection pooling and SSL support" -m "- Add PostgreSQL driver with prepared statements" -m "- Use parameterized queries exclusively" -m "- Include timeout management and result limiting" -m "- Add schema caching for performance" -m "" -m "🤖 Generated with Claude Code" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
echo.

REM Commit 6: Main CogniDB class
echo Creating commit 6: Main CogniDB interface...
git add __init__.py
git commit -m "feat: Implement main CogniDB class with new architecture" -m "" -m "- Create unified interface for natural language queries" -m "- Integrate all components (security, AI, drivers, config)" -m "- Add context manager support" -m "- Include query optimization and suggestions" -m "- Implement audit logging" -m "- Add comprehensive error handling" -m "" -m "🤖 Generated with Claude Code" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
echo.

REM Commit 7: Documentation and examples
echo Creating commit 7: Documentation and examples...
git add Readme.md
git add examples/basic_usage.py
git commit -m "docs: Update documentation for v2.0.0" -m "" -m "- Rewrite README with security-first approach" -m "- Add comprehensive usage examples" -m "- Document all features and configuration options" -m "- Include security best practices" -m "- Add performance tips" -m "- Update badges and project description" -m "" -m "🤖 Generated with Claude Code" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
echo.

REM Commit 8: Package setup and requirements
echo Creating commit 8: Package configuration...
git add setup.py
git add requirements.txt
git commit -m "build: Update package configuration for v2.0.0" -m "" -m "- Update requirements with all dependencies" -m "- Configure setup.py with optional extras" -m "- Add proper classifiers and metadata" -m "- Include console script entry point" -m "- Separate core and optional dependencies" -m "" -m "🤖 Generated with Claude Code" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
echo.

REM Commit 9: Remove old insecure files
echo Creating commit 9: Clean up old implementation...
git add -A
git commit -m "refactor: Remove old insecure implementation" -m "" -m "- Remove vulnerable SQL string interpolation code" -m "- Delete unused modules" -m "- Remove redundant wrappers" -m "- Clean up old database implementations" -m "- Remove insecure query validator" -m "" -m "BREAKING CHANGE: Complete API redesign for v2.0.0" -m "" -m "🤖 Generated with Claude Code" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
echo.

echo All commits created successfully!
echo.
echo Repository status:
git status
echo.
echo Commit history:
git log --oneline -n 9
echo.
pause