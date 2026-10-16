"""Shared utilities for Agent Praxis."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime and date objects."""

    def default(self, o: Any) -> Any:
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return super().default(o)
