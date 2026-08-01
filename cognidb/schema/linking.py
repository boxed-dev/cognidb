"""Schema linking — select relevant tables for generation (ADR 0007)."""

from __future__ import annotations

import re
from typing import Any


def link_schema(
    natural_language: str,
    full_schema: dict[str, Any],
    *,
    top_k: int = 8,
    max_tables: int = 40,
    enable: bool = True,
) -> tuple[dict[str, Any], str]:
    """
    Return (schema_context, strategy) where strategy is
    'linked' | 'full' | 'full_truncated' | 'empty'.
    """
    if not full_schema:
        return {}, "empty"

    table_names = list(full_schema.keys())
    if not enable:
        return _bounded(full_schema, max_tables)

    tokens = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", natural_language.lower()))
    scored: list[tuple[int, str]] = []
    for name in table_names:
        n = name.lower()
        score = 0
        if n in tokens:
            score += 10
        for t in tokens:
            if len(t) > 2 and (t in n or n in t):
                score += 3
        # column name hits
        cols = full_schema.get(name) or {}
        if isinstance(cols, dict):
            if _is_nested_columns(cols):
                col_keys = (cols.get("columns") or {}).keys()
            else:
                col_keys = cols.keys()
            for c in col_keys:
                cl = str(c).lower()
                if cl in tokens:
                    score += 2
        if score:
            scored.append((score, name))

    scored.sort(key=lambda x: (-x[0], x[1]))
    if not scored:
        return _bounded(full_schema, max_tables)

    chosen = [name for _, name in scored[:top_k]]
    linked = {n: full_schema[n] for n in chosen if n in full_schema}
    return linked, "linked"


def _is_nested_columns(cols: dict) -> bool:
    return "columns" in cols and isinstance(cols.get("columns"), dict)


def _bounded(schema: dict[str, Any], max_tables: int) -> tuple[dict[str, Any], str]:
    keys = list(schema.keys())
    if len(keys) <= max_tables:
        return dict(schema), "full"
    truncated = {k: schema[k] for k in keys[:max_tables]}
    return truncated, "full_truncated"
