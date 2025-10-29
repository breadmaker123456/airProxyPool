from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Dict, Iterable, List
from urllib.parse import unquote, urlsplit

import yaml

from .config import Settings
from .models import ProxyNode
from .subscriptions import fetch_and_parse, read_subscriptions_file
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

    subscription_nodes = _load_from_subscriptions(settings)
    if subscription_nodes:
        return subscription_nodes

    logger.warning(
        "No proxy nodes found; please run collector or ensure subscriptions are configured"
    )
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


def _nodes_from_forward_lines(lines: Iterable[str], source: str) -> List[ProxyNode]:
    nodes: Dict[str, ProxyNode] = {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or not line.startswith("forward="):
            continue
        uri = line[len("forward=") :]
        parsed = urlsplit(uri)
        schema = (parsed.scheme or "").lower()
        if schema not in SUPPORTED_SCHEMAS:
            continue
        server = parsed.hostname or ""
        port = parsed.port or 0
        if not server or port <= 0:
            continue
        name = unquote(parsed.fragment) if parsed.fragment else None
        country_name, country_code = derive_country(name)
        uid = hashlib.sha1(uri.encode("utf-8")).hexdigest()
        if uid in nodes:
            continue
        nodes[uid] = ProxyNode(
            uid=uid,
            backend_uri=uri,
            schema=schema,
            server=server,
            port=port,
            country=country_name,
            country_code=country_code,
            name=name,
            source=source,
            raw={"uri": uri, "source": source},
        )
    return list(nodes.values())


def _load_from_forward_config(path: Path) -> Iterable[ProxyNode]:
    with path.open("r", encoding="utf-8") as handle:
        return _nodes_from_forward_lines(handle, source="forward_config")


def _load_from_subscriptions(settings: Settings) -> List[ProxyNode]:
    urls = read_subscriptions_file(settings.subscriptions_file)
    if not urls:
        logger.debug("No subscription URLs found in %s", settings.subscriptions_file)
        return []

    try:
        content, stats = fetch_and_parse(urls)
    except Exception as exc:  # pragma: no cover - network heavy
        logger.error(
            "Failed to load subscriptions from %s: %s",
            settings.subscriptions_file,
            exc,
        )
        return []

    if not isinstance(stats, dict):
        stats = {}

    entries = int(stats.get("entries", 0) or 0)
    if entries <= 0:
        logger.warning(
            "No usable subscription entries found (ok=%s, failed=%s)",
            stats.get("ok_urls", 0),
            stats.get("failed_urls", 0),
        )
        return []

    nodes = _nodes_from_forward_lines(content.splitlines(), source="subscription")
    if not nodes:
        logger.warning(
            "Subscription fetch reported %s entries but none could be parsed", entries
        )
        return []

    failed_urls = []
    by_url = stats.get("by_url", {})
    if isinstance(by_url, dict):
        for url, info in by_url.items():
            if isinstance(info, dict) and info.get("error"):
                failed_urls.append(f"{url}: {info.get('error')}")

    if failed_urls:
        logger.warning("Some subscription URLs failed: %s", "; ".join(failed_urls))

    logger.info(
        "Loaded %s nodes from subscriptions (ok=%s, failed=%s)",
        len(nodes),
        stats.get("ok_urls", 0),
        stats.get("failed_urls", 0),
    )
    return nodes
