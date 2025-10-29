from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, Optional

from .utils import utcnow


@dataclass
class ProxyNode:
    uid: str
    backend_uri: str
    schema: str
    server: str
    port: int
    country: Optional[str] = None
    country_code: Optional[str] = None
    name: Optional[str] = None
    source: str = "unknown"
    raw: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ProxyNode":
        kwargs = dict(data)
        for key in ("created_at", "updated_at"):
            value = kwargs.get(key)
            if isinstance(value, str):
                kwargs[key] = datetime.fromisoformat(value)
        return cls(**kwargs)  # type: ignore[arg-type]


@dataclass
class ProxyEndpoint:
    id: str
    node_uid: str
    protocol: str
    host: str
    port: int
    public_host: str
    country: Optional[str] = None
    country_code: Optional[str] = None
    name: Optional[str] = None
    available: bool = False
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
    last_checked: Optional[datetime] = None

    def public_endpoint(self) -> str:
        scheme = self.protocol.lower()
        return f"{scheme}://{self.public_host}:{self.port}"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        data["last_checked"] = self.last_checked.isoformat() if self.last_checked else None
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ProxyEndpoint":
        kwargs = dict(data)
        for key in ("created_at", "updated_at", "last_checked"):
            value = kwargs.get(key)
            if isinstance(value, str):
                kwargs[key] = datetime.fromisoformat(value)
        return cls(**kwargs)  # type: ignore[arg-type]


@dataclass
class CacheEntry:
    endpoint_ids: list[str]
    expires_at: datetime

    def to_dict(self) -> dict:
        return {
            "endpoint_ids": list(self.endpoint_ids),
            "expires_at": self.expires_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CacheEntry":
        return cls(endpoint_ids=list(data.get("endpoint_ids", [])), expires_at=datetime.fromisoformat(data["expires_at"]))
