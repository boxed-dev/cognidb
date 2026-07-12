"""Query pipeline — deep module for NL→SQL→execute with security locality."""

from .secure_query import SecureQueryPipeline, QueryResult

__all__ = ["SecureQueryPipeline", "QueryResult"]
