"""
json_utils.py
=============
CustomEncoder that handles asyncpg-specific types that stdlib json cannot
serialize: Decimal, UUID, datetime, date, and asyncpg.Record.

Usage:
    json.dumps(payload, cls=CustomEncoder)
"""
from __future__ import annotations

import json
import math
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID


class CustomEncoder(json.JSONEncoder):
    """JSON encoder that handles asyncpg types and common Python numerics."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            f = float(obj)
            # Guard against Decimal("NaN") / Decimal("Infinity")
            if math.isfinite(f):
                return f
            return None
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        # asyncpg.Record behaves like a Mapping
        try:
            return dict(obj)
        except (TypeError, AttributeError):
            pass
        return super().default(obj)
