from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Dict, Iterable, List
from urllib.parse import unquote, urlsplit

import yaml

from .config import Settings
from .models import ProxyNode
from .utils import derive_country

logger = logging.getLogger(__name__)

SUPPORTED_SCHEMAS = {"ss", "vmess"}
SUPPORTED_SS_CIPHERS = {
    "aes-128-gcm",
    "aes-256-gcm",
    "chacha20-ietf-poly1305",
    "aes-128-ctr",
    "aes-192-ctr",
    "aes-256-ctr",
    "aes-128-cfb",
    "aes-192-cfb",
    "aes-256-cfb",
    "chacha20-ietf",
    "xchacha20-ietf-poly1305",
}


def load_nodes(settings: Settings) -> List[ProxyNode]:
    """Load proxy nodes from the preferred source."""

    if settings.clash_file.exists():
        try:
            nodes = list(_load_from_clash(settings.clash_file))
            if nodes:
                logger.info("Loaded %s nodes from %s", len(nodes), settings.clash_file)
                return nodes
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to parse %s: %s", settings.clash_file, exc)

    if settings.subscription_config_file.exists():
        nodes = list(_load_from_forward_config(settings.subscription_config_file))
        if nodes:
            logger.info(
                "Loaded %s nodes from forward config %s",
                len(nodes),
                settings.subscription_config_file,
            )
            return nodes

    logger.warning("No proxy nodes found; please run collector or provide subscription config")
    return []


def _load_from_clash(path: Path) -> Iterable[ProxyNode]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    proxies = payload.get("proxies", [])
    seen: Dict[str, ProxyNode] = {}

    for proxy in proxies:
        if not isinstance(proxy, dict):
            continue
        schema = proxy.get("type")
        if schema not in SUPPORTED_SCHEMAS:
            continue
        if schema == "ss" and proxy.get("cipher") not in SUPPORTED_SS_CIPHERS:
            continue

        backend_uri = _build_backend_uri_from_clash(proxy)
        if not backend_uri:
            continue
        uid = hashlib.sha1(backend_uri.encode("utf-8")).hexdigest()
        if uid in seen:
            continue
        name = proxy.get("name")
        country_name, country_code = derive_country(name, proxy)
        server = str(proxy.get("server"))
        port = int(proxy.get("port", 0) or 0)
        node = ProxyNode(
            uid=uid,
            backend_uri=backend_uri,
            schema=schema,
            server=server,
            port=port,
            country=country_name,
            country_code=country_code,
            name=name,
            source="clash",
            raw=proxy,
        )
        seen[uid] = node

    return seen.values()


def _build_backend_uri_from_clash(proxy: dict) -> str | None:
    schema = proxy.get("type")
    if schema == "ss":
        try:
            cipher = proxy["cipher"]
            password = proxy["password"]
            server = proxy["server"]
            port = proxy["port"]
        except KeyError:
            return None
        name = proxy.get("name", "")
        suffix = f"#{name}" if name else ""
        return f"ss://{cipher}:{password}@{server}:{port}{suffix}"
    if schema == "vmess":
        try:
            server = proxy["server"]
            port = proxy["port"]
            uuid = proxy["uuid"]
        except KeyError:
            return None
        alter_id = proxy.get("alterId", proxy.get("alterID", 0))
        suffix = f"#{proxy.get('name')}" if proxy.get("name") else ""
        return f"vmess://none:{uuid}@{server}:{port}?alterID={alter_id}{suffix}"
    return None


def _load_from_forward_config(path: Path) -> Iterable[ProxyNode]:
    nodes: Dict[str, ProxyNode] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or not line.startswith("forward="):
                continue
            uri = line[len("forward=") :]
            parsed = urlsplit(uri)
            schema = parsed.scheme
            if schema not in SUPPORTED_SCHEMAS:
                continue
            server = parsed.hostname or ""
            port = parsed.port or 0
            name = unquote(parsed.fragment) if parsed.fragment else None
            country_name, country_code = derive_country(name)
            uid = hashlib.sha1(uri.encode("utf-8")).hexdigest()
            if uid in nodes:
                continue
            node = ProxyNode(
                uid=uid,
                backend_uri=uri,
                schema=schema,
                server=server,
                port=port,
                country=country_name,
                country_code=country_code,
                name=name,
                source="forward_config",
                raw={"uri": uri},
            )
            nodes[uid] = node
    return nodes.values()
