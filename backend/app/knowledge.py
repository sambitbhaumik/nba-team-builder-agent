from __future__ import annotations

from typing import List

from .db import add_preference, query_preferences


def store_preference(key: str, value: str) -> None:
    add_preference(key=key, value=value)


def load_preferences() -> List[str]:
    items = query_preferences()
    return [f"{item['key']}: {item['value']}" for item in items]
