from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass
class Settings:
    """Runtime configuration for the proxy chain service."""

    data_dir: Path = field(default_factory=lambda: Path(os.getenv("APP_DATA_DIR", "data")))
    glider_binary: Path = field(
        default_factory=lambda: Path(
            os.getenv(
                "GLIDER_BINARY",
                "glider\\glider.exe" if os.name == "nt" else "glider/glider",
            )
        )
    )
    subscriptions_file: Path = field(
        default_factory=lambda: Path(os.getenv("SUBSCRIPTIONS_FILE", "subscriptions.txt"))
    )
    clash_file: Path = field(
        default_factory=lambda: Path(os.getenv("CLASH_FILE", "aggregator/data/clash.yaml"))
    )
    subscription_config_file: Path = field(
        default_factory=lambda: Path(os.getenv("GLIDER_SUBSCRIPTION_CONFIG", "glider/glider.subscription.conf"))
    )
    listen_host: str = field(default_factory=lambda: os.getenv("PROXY_LISTEN_HOST", "0.0.0.0"))
    public_host: str = field(
        default_factory=lambda: os.getenv(
            "PUBLIC_HOST",
            os.getenv("PROXY_PUBLIC_HOST", os.getenv("PROXY_LISTEN_HOST", "127.0.0.1")),
        )
    )
    enabled_protocols: List[str] = field(default_factory=list)
    cache_ttl_seconds: int = field(default_factory=lambda: _int_env("PROXY_CACHE_TTL", 300))
    base_socks_port: int = field(default_factory=lambda: _int_env("BASE_SOCKS_PORT", 25000))
    base_http_port: int = field(default_factory=lambda: _int_env("BASE_HTTP_PORT", 26000))
    max_endpoints: int = field(default_factory=lambda: _int_env("MAX_PROXY_ENDPOINTS", 500))
    enable_glider: bool = field(default_factory=lambda: _to_bool(os.getenv("ENABLE_GLIDER"), True))
    refresh_interval_seconds: int = field(
        default_factory=lambda: _int_env("REFRESH_INTERVAL_SECONDS", 0)
    )
    health_check_url: str = field(
        default_factory=lambda: os.getenv(
            "PROXY_HEALTH_CHECK",
            "http://www.msftconnecttest.com/connecttest.txt#expect=200",
        )
    )
    glider_strategy: str = field(default_factory=lambda: os.getenv("GLIDER_STRATEGY", "rr"))
    glider_check_interval: int = field(
        default_factory=lambda: _int_env("GLIDER_CHECK_INTERVAL", 60)
    )
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    glider_config_dir: Path = field(init=False)
    port_registry_file: Path = field(init=False)
    nodes_store_file: Path = field(init=False)
    endpoints_store_file: Path = field(init=False)

    def __post_init__(self) -> None:
        # Normalise list of enabled protocols
        protocols_env = os.getenv("ENABLED_PROTOCOLS")
        if protocols_env:
            parsed = [item.strip().lower() for item in protocols_env.split(",") if item.strip()]
            self.enabled_protocols = parsed or ["socks5", "http"]
        else:
            self.enabled_protocols = ["socks5", "http"]

        strategy = (self.glider_strategy or "").strip().lower()
        self.glider_strategy = strategy or "rr"

        self.health_check_url = self.health_check_url.strip() if self.health_check_url else ""
        if self.glider_check_interval <= 0:
            self.glider_check_interval = 60

        self.data_dir = self.data_dir.expanduser().resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.glider_config_dir = Path(
            os.getenv("GLIDER_GENERATED_DIR", str(self.data_dir / "glider_configs"))
        ).expanduser().resolve()
        self.glider_config_dir.mkdir(parents=True, exist_ok=True)

        self.port_registry_file = self.data_dir / "port_registry.json"
        self.nodes_store_file = self.data_dir / "proxy_nodes.json"
        self.endpoints_store_file = self.data_dir / "proxy_endpoints.json"

    @property
    def supports_protocol(self) -> set[str]:
        return {proto.lower() for proto in self.enabled_protocols}
