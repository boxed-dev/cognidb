"""Setup configuration for CogniDB."""

from pathlib import Path
from setuptools import setup, find_packages

this_directory = Path(__file__).parent
long_description = (this_directory / "Readme.md").read_text(encoding="utf-8")

setup(
    name="cognidb",
    version="3.0.0",
    author="Rishabh Kumar",
    author_email="rishabh.vaaiv@gmail.com",
    description="Secure Natural Language Database Interface",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/boxed-dev/cognidb",
    packages=find_packages(exclude=["tests", "tests.*", "examples", "examples.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Database",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.9",
    install_requires=[
        "sqlparse>=0.4.4",
        "pyyaml>=6.0.1",
        "python-dotenv>=1.0.0",
        "mysql-connector-python>=8.0.33",
        "psycopg2-binary>=2.9.9",
        "openai>=1.0.0",
        "anthropic>=0.8.0",
        "cryptography>=41.0.0",
    ],
    extras_require={
        "mongo": ["pymongo>=4.6.0"],
        "aws": ["boto3>=1.28.0"],
        "redis": ["redis>=5.0.0"],
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "pytest-asyncio>=0.21.0",
            "pytest-mock>=3.11.0",
        ],
    },
    include_package_data=True,
    keywords="database sql natural-language nlp ai llm security nl2sql",
    project_urls={
        "Bug Reports": "https://github.com/boxed-dev/cognidb/issues",
        "Source": "https://github.com/boxed-dev/cognidb",
    },
    license="MIT",
)
