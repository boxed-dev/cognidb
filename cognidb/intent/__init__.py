"""Intent generation path — deterministic QueryIntent → SQL (ADR 0006)."""

from .renderer import IntentRenderError, render_sql

__all__ = ["render_sql", "IntentRenderError"]
