from __future__ import annotations

import threading
from datetime import datetime, timedelta
from typing import Dict, Hashable, Optional

from .models import CacheEntry
from .utils import utcnow


class SelectionCache:
    """Simple in-memory TTL cache keyed by hashable values."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        self._ttl = max(ttl_seconds, 1)
        self._entries: Dict[Hashable, CacheEntry] = {}
        self._lock = threading.RLock()

    def get(self, key: Hashable) -> Optional[CacheEntry]:
        with self._lock:
            entry = self._entries.get(key)
            if not entry:
                return None
            if entry.expires_at <= utcnow():
                del self._entries[key]
                return None
            return entry

    def set(self, key: Hashable, endpoint_ids: list[str]) -> CacheEntry:
        with self._lock:
            entry = CacheEntry(endpoint_ids=endpoint_ids, expires_at=utcnow() + timedelta(seconds=self._ttl))
            self._entries[key] = entry
            return entry

    def invalidate(self, key: Hashable) -> None:
        with self._lock:
            self._entries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
