"""
serialization.py
================
Single canonical asyncpg-row → JSON-safe dict converter.

asyncpg returns ``Decimal`` for NUMERIC columns, ``UUID`` objects, and
``datetime``/``date`` objects — none of which are JSON serializable as-is
(and ``Decimal`` breaks the frontend with "toFixed is not a function").
Every router previously carried its own copy of this loop; this module
replaces all of them.
"""
from __future__ import annotations

import json

EMPTY_FROZENSET: frozenset[str] = frozenset()


def serialize_row(row, jsonb_cols: frozenset[str] = EMPTY_FROZENSET) -> dict:
    """
    Convert an asyncpg Record (or dict) to a JSON-safe dict.

    - datetime/date  → ISO-8601 string
    - UUID           → str
    - Decimal        → float
    - columns named in *jsonb_cols* that arrive as JSON strings → parsed objects
    """
    d = dict(row)
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
        elif type(v).__name__ == "UUID":
            d[k] = str(v)
        elif type(v).__name__ == "Decimal":
            d[k] = float(v)
        elif k in jsonb_cols and isinstance(v, str):
            try:
                d[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                pass
    return d


def serialize_rows(rows, jsonb_cols: frozenset[str] = EMPTY_FROZENSET) -> list[dict]:
    """Convenience wrapper for lists of records."""
    return [serialize_row(r, jsonb_cols) for r in rows]
