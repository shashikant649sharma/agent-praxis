"""Shared utilities for Agent Praxis."""

from __future__ import annotations

import json
from datetime import date, datetime


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime and date objects."""

    def default(self, o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return super().default(o)
