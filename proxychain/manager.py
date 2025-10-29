from __future__ import annotations

import logging
import random
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from .cache import SelectionCache
from .config import Settings
from .glider_manager import GliderManager
from .models import ProxyEndpoint, ProxyNode
from .port_registry import PortRegistry
from .proxy_loader import load_nodes
from .storage import JsonStorage
from .utils import matches_country, normalise_protocols, utcnow

logger = logging.getLogger(__name__)

EPOCH = datetime.fromtimestamp(0, tz=timezone.utc)


@dataclass
class SelectionResult:
    endpoints: List[ProxyEndpoint]
    cached: bool
    cache_expires_at: Optional[datetime]


class ProxyManager:
    """Coordinates proxy nodes, endpoint allocation, caching and glider processes."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = threading.RLock()
        self._nodes: Dict[str, ProxyNode] = {}
        self._endpoints: Dict[str, ProxyEndpoint] = {}
        self._usage: Dict[str, datetime] = {}
        self._last_refresh: Optional[datetime] = None

        self._node_storage = JsonStorage(settings.nodes_store_file)
        self._endpoint_storage = JsonStorage(settings.endpoints_store_file)
        self._port_registry = PortRegistry(
            JsonStorage(settings.port_registry_file),
            start_socks_port=settings.base_socks_port,
            start_http_port=settings.base_http_port,
        )
        self._glider = GliderManager(settings)
        self._cache = SelectionCache(settings.cache_ttl_seconds)

        self._load_state()

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------
    def _load_state(self) -> None:
        stored_nodes = self._node_storage.load([])
        for payload in stored_nodes:
            try:
                node = ProxyNode.from_dict(payload)
                self._nodes[node.uid] = node
            except Exception:  # pragma: no cover - defensive
                continue

        stored_endpoints = self._endpoint_storage.load([])
        for payload in stored_endpoints:
            try:
                endpoint = ProxyEndpoint.from_dict(payload)
                self._endpoints[endpoint.id] = endpoint
                self._usage.setdefault(endpoint.id, endpoint.updated_at)
            except Exception:  # pragma: no cover - defensive
                continue

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def refresh(self) -> dict:
        """Refresh available nodes from upstream sources and rebuild endpoints."""

        logger.info("Refreshing proxy nodes")
        new_nodes_list = load_nodes(self.settings)
        if self.settings.max_endpoints and len(new_nodes_list) > self.settings.max_endpoints:
            logger.warning(
                "Limiting nodes to max_endpoints=%s (received %s)",
                self.settings.max_endpoints,
                len(new_nodes_list),
            )
            new_nodes_list = new_nodes_list[: self.settings.max_endpoints]

        new_nodes: Dict[str, ProxyNode] = {}
        now = utcnow()
        for node in new_nodes_list:
            existing = self._nodes.get(node.uid)
            node.created_at = existing.created_at if existing else now
            node.updated_at = now
            new_nodes[node.uid] = node

        # Build new endpoints map
        new_endpoints: Dict[str, ProxyEndpoint] = {}

        with self._lock:
            removed_nodes = set(self._nodes.keys()) - set(new_nodes.keys())
            for node_id in removed_nodes:
                self._port_registry.release(node_id)

            for node in new_nodes.values():
                socks_port, http_port = self._port_registry.assign(node.uid)
                if "socks5" in self.settings.supports_protocol:
                    endpoint_id = f"{node.uid}:socks5"
                    endpoint = ProxyEndpoint(
                        id=endpoint_id,
                        node_uid=node.uid,
                        protocol="socks5",
                        host=self.settings.listen_host,
                        port=socks_port,
                        public_host=self.settings.public_host,
                        country=node.country,
                        country_code=node.country_code,
                        name=node.name,
                    )
                    existing_endpoint = self._endpoints.get(endpoint_id)
                    if existing_endpoint:
                        endpoint.created_at = existing_endpoint.created_at
                        endpoint.available = existing_endpoint.available
                        endpoint.last_checked = existing_endpoint.last_checked
                    new_endpoints[endpoint_id] = endpoint

                if "http" in self.settings.supports_protocol:
                    endpoint_id = f"{node.uid}:http"
                    endpoint = ProxyEndpoint(
                        id=endpoint_id,
                        node_uid=node.uid,
                        protocol="http",
                        host=self.settings.listen_host,
                        port=http_port,
                        public_host=self.settings.public_host,
                        country=node.country,
                        country_code=node.country_code,
                        name=node.name,
                    )
                    existing_endpoint = self._endpoints.get(endpoint_id)
                    if existing_endpoint:
                        endpoint.created_at = existing_endpoint.created_at
                        endpoint.available = existing_endpoint.available
                        endpoint.last_checked = existing_endpoint.last_checked
                    new_endpoints[endpoint_id] = endpoint

            active_ids: set[str] = set()
            if self.settings.enable_glider:
                for endpoint in new_endpoints.values():
                    node = new_nodes.get(endpoint.node_uid)
                    if not node:
                        continue
                    alive = self._glider.ensure(endpoint, node.backend_uri)
                    endpoint.available = alive
                    endpoint.updated_at = now
                    if alive:
                        endpoint.last_checked = now
                    active_ids.add(endpoint.id)
                self._glider.cleanup(active_ids)
            else:
                self._glider.stop_all()
                for endpoint in new_endpoints.values():
                    endpoint.available = False
                    endpoint.updated_at = now

            removed_endpoint_ids = set(self._endpoints.keys()) - set(new_endpoints.keys())
            for endpoint_id in removed_endpoint_ids:
                self._usage.pop(endpoint_id, None)

            self._nodes = new_nodes
            self._endpoints = new_endpoints
            self._last_refresh = now
            for endpoint in self._endpoints.values():
                self._usage.setdefault(endpoint.id, endpoint.updated_at)

            self._node_storage.save([node.to_dict() for node in self._nodes.values()])
            self._endpoint_storage.save([endpoint.to_dict() for endpoint in self._endpoints.values()])
            self._port_registry.save()
            self._cache.clear()

        logger.info(
            "Refresh completed: nodes=%s, endpoints=%s",
            len(self._nodes),
            len(self._endpoints),
        )
        return {
            "nodes": len(self._nodes),
            "endpoints": len(self._endpoints),
            "refreshed_at": now.isoformat(),
        }

    def select(
        self,
        protocols: Sequence[str],
        country: Optional[str],
        count: int,
        randomize: bool,
    ) -> SelectionResult:
        protocols = normalise_protocols(protocols) or list(self.settings.supports_protocol)
        key = (tuple(sorted(protocols)), (country or "").lower(), int(count))
        if not randomize:
            cached = self._cache.get(key)
            if cached:
                endpoints = [self._endpoints[endpoint_id] for endpoint_id in cached.endpoint_ids if endpoint_id in self._endpoints]
                if endpoints:
                    return SelectionResult(endpoints=endpoints, cached=True, cache_expires_at=cached.expires_at)

        with self._lock:
            available = [endpoint for endpoint in self._endpoints.values() if endpoint.protocol in protocols]
            if country:
                available = [endpoint for endpoint in available if matches_country(country, endpoint.country, endpoint.country_code)]

            if not available:
                if not randomize:
                    self._cache.invalidate(key)
                return SelectionResult(endpoints=[], cached=False, cache_expires_at=None)

            if randomize:
                random.shuffle(available)
            else:
                available.sort(key=lambda endpoint: (self._usage.get(endpoint.id, EPOCH), endpoint.id))

            selected = available[:count] if count > 0 else available
            now = utcnow()
            for endpoint in selected:
                self._usage[endpoint.id] = now

            cache_entry = None
            if not randomize:
                cache_entry = self._cache.set(key, [endpoint.id for endpoint in selected])

            return SelectionResult(
                endpoints=selected,
                cached=False,
                cache_expires_at=cache_entry.expires_at if cache_entry else None,
            )

    def get_node(self, node_uid: str) -> Optional[ProxyNode]:
        with self._lock:
            return self._nodes.get(node_uid)

    def status(self) -> dict:
        with self._lock:
            return {
                "nodes": len(self._nodes),
                "endpoints": len(self._endpoints),
                "last_refresh": self._last_refresh.isoformat() if self._last_refresh else None,
                "glider": self._glider.status() if self.settings.enable_glider else {},
            }

    def last_refresh_at(self) -> Optional[datetime]:
        return self._last_refresh

    def shutdown(self) -> None:
        logger.info("Shutting down proxy manager")
        self._glider.stop_all()
