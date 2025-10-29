from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from .storage import JsonStorage


@dataclass
class _Entry:
    socks_port: int
    http_port: int

    def to_dict(self) -> dict:
        return {"socks": self.socks_port, "http": self.http_port}

    @classmethod
    def from_dict(cls, data: dict) -> "_Entry":
        return cls(socks_port=int(data.get("socks")), http_port=int(data.get("http")))


class PortRegistry:
    """Keeps track of allocated local ports for proxy endpoints."""

    def __init__(
        self,
        storage: JsonStorage,
        start_socks_port: int,
        start_http_port: int,
    ) -> None:
        self._storage = storage
        self._start_socks = start_socks_port
        self._start_http = start_http_port
        self._entries: Dict[str, _Entry] = {}
        self._next_socks = start_socks_port
        self._next_http = start_http_port
        self._dirty = False
        self._load()

    def _load(self) -> None:
        payload = self._storage.load(
            {
                "next_socks": self._start_socks,
                "next_http": self._start_http,
                "entries": {},
            }
        )
        self._next_socks = int(payload.get("next_socks", self._start_socks))
        self._next_http = int(payload.get("next_http", self._start_http))
        entries = payload.get("entries", {})
        for key, value in entries.items():
            try:
                entry = _Entry.from_dict(value)
            except (TypeError, ValueError):
                continue
            self._entries[key] = entry

    def assign(self, node_id: str) -> Tuple[int, int]:
        entry = self._entries.get(node_id)
        if entry:
            return entry.socks_port, entry.http_port
        socks_port = self._next_available_socks()
        http_port = self._next_available_http()
        entry = _Entry(socks_port=socks_port, http_port=http_port)
        self._entries[node_id] = entry
        self._dirty = True
        return socks_port, http_port

    def release(self, node_id: str) -> None:
        if node_id in self._entries:
            del self._entries[node_id]
            self._dirty = True

    def _used_socks_ports(self) -> set[int]:
        return {entry.socks_port for entry in self._entries.values()}

    def _used_http_ports(self) -> set[int]:
        return {entry.http_port for entry in self._entries.values()}

    def _next_available_socks(self) -> int:
        candidate = self._next_socks
        used = self._used_socks_ports()
        while candidate in used:
            candidate += 1
        self._next_socks = candidate + 1
        self._dirty = True
        return candidate

    def _next_available_http(self) -> int:
        candidate = self._next_http
        used = self._used_http_ports()
        while candidate in used:
            candidate += 1
        self._next_http = candidate + 1
        self._dirty = True
        return candidate

    def save(self) -> None:
        if not self._dirty:
            return
        payload = {
            "next_socks": self._next_socks,
            "next_http": self._next_http,
            "entries": {key: entry.to_dict() for key, entry in self._entries.items()},
        }
        self._storage.save(payload)
        self._dirty = False

    def snapshot(self) -> dict:
        return {
            "next_socks": self._next_socks,
            "next_http": self._next_http,
            "entries": {key: entry.to_dict() for key, entry in self._entries.items()},
        }
