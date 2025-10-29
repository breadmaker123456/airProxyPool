from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Query, Request, status

from .api_models import CountryInfo, ProxyItem, ProxyListMeta, ProxyListResponse, RefreshResponse
from .manager import ProxyManager
from .utils import parse_protocols_param


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
            items.append(
                ProxyItem(
                    id=endpoint.id,
                    protocol=endpoint.protocol,
                    host=endpoint.host,
                    port=endpoint.port,
                    public_host=endpoint.public_host,
                    endpoint=endpoint.public_endpoint(),
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
