"""Input sanitization utilities."""

from __future__ import annotations

import html
import re


class InputSanitizer:
    """Sanitizes the two untrusted inputs CogniDB actually handles:

    1. the natural-language question sent to the LLM, and
    2. database identifiers used when building schema-introspection helpers.

    Values are never sanitized for SQL here — they are bound as parameters by the
    renderer/driver (see the intent renderer). String escaping is a driver concern.
    """

    # Characters allowed in natural language queries
    ALLOWED_NL_CHARS = re.compile(r'[^a-zA-Z0-9\s\-_.,!?\'"\(\)%$#@]')

    MAX_NATURAL_LANGUAGE_LENGTH = 500
    MAX_IDENTIFIER_LENGTH = 64

    @staticmethod
    def sanitize_natural_language(query: str) -> str:
        """Sanitize a natural-language query before it is sent to the LLM."""
        if not query:
            return ""

        query = query[: InputSanitizer.MAX_NATURAL_LANGUAGE_LENGTH]
        query = InputSanitizer.ALLOWED_NL_CHARS.sub(" ", query)
        query = " ".join(query.split())
        query = html.escape(query, quote=False)
        return query.strip()

    @staticmethod
    def sanitize_identifier(identifier: str) -> str:
        """Sanitize a database identifier (table/column name).

        Raises:
            ValueError: if the identifier is empty or has no valid characters.
        """
        if not identifier:
            raise ValueError("Identifier cannot be empty")

        identifier = re.sub(r"[^a-zA-Z0-9_]", "", identifier)
        if not re.match(r"^[a-zA-Z_]", identifier):
            identifier = f"_{identifier}"
        identifier = identifier[: InputSanitizer.MAX_IDENTIFIER_LENGTH]

        if not identifier:
            raise ValueError("Identifier contains no valid characters")

        return identifier
