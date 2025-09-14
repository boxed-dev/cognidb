"""Setup configuration for CogniDB."""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "Readme.md").read_text()

# Read requirements
requirements = (this_directory / "requirements.txt").read_text().splitlines()

# Separate optional requirements
core_requirements = []
optional_requirements = {
    'llama': ['llama-cpp-python>=0.2.0'],
    'azure': ['azure-identity>=1.14.0', 'azure-keyvault-secrets>=4.7.0'],
    'vault': ['hvac>=1.2.0'],
    'redis': ['redis>=5.0.0'],
    'api': ['fastapi>=0.104.0', 'uvicorn>=0.24.0'],
    'dev': [
        'pytest>=7.4.0',
        'pytest-cov>=4.1.0',
        'pytest-asyncio>=0.21.0',
        'pytest-mock>=3.11.0',
        'black>=23.0.0',
        'flake8>=6.0.0',
        'mypy>=1.5.0',
        'pre-commit>=3.3.0'
    ],
    'docs': [
        'sphinx>=7.0.0',
        'sphinx-rtd-theme>=1.3.0'
    ]
}

# Filter core requirements (exclude optional ones)
for line in requirements:
    if line and not line.startswith('#'):
        # Skip optional dependencies
        if not any(opt in line.lower() for opt in ['llama', 'azure', 'hvac', 'redis', 'fastapi', 'pytest', 'sphinx']):
            core_requirements.append(line)

setup(
    name="cognidb",
    version="2.0.0",
    author="CogniDB Team",
    author_email="team@cognidb.io",
    description="Secure Natural Language Database Interface",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/adrienckr/cognidb",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Database",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=core_requirements,
    extras_require={
        **optional_requirements,
        'all': sum(optional_requirements.values(), [])
    },
    entry_points={
        'console_scripts': [
            'cognidb=cognidb.cli:main',
        ],
    },
    include_package_data=True,
    package_data={
        'cognidb': [
            'cognidb.example.yaml',
            'examples/*.py',
        ],
    },
    keywords='database sql natural-language nlp ai llm security',
    project_urls={
        'Bug Reports': 'https://github.com/adrienckr/cognidb/issues',
        'Source': 'https://github.com/adrienckr/cognidb',
        'Documentation': 'https://cognidb.readthedocs.io',
    },
)