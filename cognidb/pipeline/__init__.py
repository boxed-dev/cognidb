"""Query pipeline — deep module for NL→SQL→execute with security locality."""

from .secure_query import QueryResult, SecureQueryPipeline

__all__ = ["SecureQueryPipeline", "QueryResult"]
