from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Query, Request, status

from .api_models import CountryInfo, ProxyItem, ProxyListMeta, ProxyListResponse, RefreshResponse
from .manager import ProxyManager
from .utils import parse_protocols_param


_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "::", "0.0.0.0"}
_LOOPBACK_BRACKETED = {"[::]", "[::1]"}
_LOOPBACK_PREFIXES = ("127.", "::ffff:127.")


def _strip_port(host: str) -> str:
    value = host.strip()
    if not value:
        return value
    if value.startswith("[") and "]" in value:
        end = value.find("]")
        return value[1:end]
    if value.count(":") == 1:
        name, maybe_port = value.rsplit(":", 1)
        if maybe_port.isdigit():
            return name
    return value


def _is_loopback(host: Optional[str]) -> bool:
    if not host:
        return False
    normalised = host.strip().lower()
    if not normalised:
        return False
    if normalised in _LOOPBACK_BRACKETED:
        return True
    stripped = normalised[1:-1] if normalised.startswith("[") and normalised.endswith("]") else normalised
    if stripped in _LOOPBACK_HOSTS:
        return True
    return any(stripped.startswith(prefix) for prefix in _LOOPBACK_PREFIXES)


def _resolve_public_host(request: Request, fallback: str) -> str:
    if fallback and not _is_loopback(fallback):
        return fallback

    headers = request.headers
    for header_name in ("x-forwarded-host", "host"):
        raw = headers.get(header_name)
        if not raw:
            continue
        candidate = raw.split(",")[0].strip()
        if not candidate:
            continue
        candidate = _strip_port(candidate)
        if candidate and not _is_loopback(candidate):
            return candidate

    hostname = request.url.hostname
    if hostname and not _is_loopback(hostname):
        return hostname

    server = request.scope.get("server")
    if server:
        server_host = server[0]
        if server_host and not _is_loopback(server_host):
            return server_host

    return fallback


def create_router(manager: ProxyManager) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["proxy"])

    @router.get("/proxies", response_model=ProxyListResponse)
    def get_proxies(
        request: Request,
        protocols: Optional[str] = Query(
            default=None,
            description="Comma separated list of protocols to return (socks5,http)",
        ),
        country: Optional[str] = Query(
            default=None,
            description="Filter proxies by country name or ISO code",
        ),
        count: int = Query(
            default=1,
            ge=1,
            le=100,
            description="Number of proxies to return",
        ),
        random: bool = Query(
            default=False,
            description="Return a randomised selection (disables caching)",
        ),
    ) -> ProxyListResponse:
        raw_values = request.query_params.getlist("protocols")
        if raw_values:
            protocol_list = parse_protocols_param(raw_values if len(raw_values) > 1 else raw_values[0])
        else:
            protocol_list = parse_protocols_param(protocols)

        selection = manager.select(protocol_list, country, count, random)
        endpoints = selection.endpoints

        items: List[ProxyItem] = []
        for endpoint in endpoints:
            node = manager.get_node(endpoint.node_uid)
            resolved_public_host = _resolve_public_host(request, endpoint.public_host)
            items.append(
                ProxyItem(
                    id=endpoint.id,
                    protocol=endpoint.protocol,
                    host=endpoint.host,
                    port=endpoint.port,
                    public_host=resolved_public_host,
                    endpoint=endpoint.public_endpoint(resolved_public_host),
                    country=CountryInfo(name=endpoint.country, code=endpoint.country_code)
                    if endpoint.country or endpoint.country_code
                    else None,
                    name=endpoint.name,
                    available=endpoint.available,
                    node_id=endpoint.node_uid,
                    backend_schema=node.schema if node else None,
                    backend_server=node.server if node else None,
                    backend_port=node.port if node else None,
                    updated_at=endpoint.updated_at,
                    last_checked=endpoint.last_checked,
                )
            )

        meta = ProxyListMeta(
            requested_count=count,
            returned_count=len(items),
            cached=selection.cached,
            cache_expires_at=selection.cache_expires_at,
            random=random,
            refreshed_at=manager.last_refresh_at(),
        )

        return ProxyListResponse(data=items, meta=meta)

    @router.post("/proxies/refresh", response_model=RefreshResponse, status_code=status.HTTP_202_ACCEPTED)
    def trigger_refresh() -> RefreshResponse:
        result = manager.refresh()
        return RefreshResponse(
            nodes=result["nodes"],
            endpoints=result["endpoints"],
            refreshed_at=datetime.fromisoformat(result["refreshed_at"]),
        )

    return router
