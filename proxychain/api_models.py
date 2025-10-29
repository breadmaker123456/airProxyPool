from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class CountryInfo(BaseModel):
    name: Optional[str] = Field(default=None, description="Human readable country name")
    code: Optional[str] = Field(default=None, description="ISO alpha-2 country code")


class ProxyItem(BaseModel):
    id: str
    protocol: str
    host: str
    port: int
    public_host: str = Field(description="Public host clients should connect to")
    endpoint: str = Field(description="Full URI for the proxy endpoint")
    country: Optional[CountryInfo] = None
    name: Optional[str] = Field(default=None, description="Display name of the upstream node")
    available: bool = Field(default=False, description="Whether the backing glider process is alive")
    node_id: str = Field(description="Identifier of the upstream node")
    backend_schema: Optional[str] = Field(default=None, description="Protocol of the upstream node (ss/vmess)")
    backend_server: Optional[str] = Field(default=None, description="Hostname of the upstream node")
    backend_port: Optional[int] = Field(default=None, description="Port of the upstream node")
    updated_at: datetime
    last_checked: Optional[datetime] = None


class ProxyListMeta(BaseModel):
    requested_count: int
    returned_count: int
    cached: bool
    cache_expires_at: Optional[datetime] = None
    random: bool
    refreshed_at: Optional[datetime] = None


class ProxyListResponse(BaseModel):
    data: List[ProxyItem]
    meta: ProxyListMeta


class RefreshResponse(BaseModel):
    nodes: int
    endpoints: int
    refreshed_at: datetime
