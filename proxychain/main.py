from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from fastapi import FastAPI

from .api import create_router
from .config import Settings
from .manager import ProxyManager

logger = logging.getLogger(__name__)


class RefreshWorker(threading.Thread):
    def __init__(self, manager: ProxyManager, interval: int) -> None:
        super().__init__(daemon=True)
        self.manager = manager
        self.interval = max(interval, 1)
        self._stop = threading.Event()

    def run(self) -> None:
        logger.info("Starting background refresh worker (interval=%ss)", self.interval)
        while not self._stop.wait(self.interval):
            try:
                self.manager.refresh()
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("Background refresh failed: %s", exc)

    def stop(self) -> None:
        self._stop.set()
        logger.info("Stopping background refresh worker")


settings = Settings()
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
manager = ProxyManager(settings)
refresh_worker: Optional[RefreshWorker] = None

app = FastAPI(title="ProxyChain API", version="1.0.0")
app.include_router(create_router(manager))


@app.on_event("startup")
async def on_startup() -> None:
    global refresh_worker
    try:
        manager.refresh()
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Initial refresh failed: %s", exc)
    if settings.refresh_interval_seconds > 0:
        refresh_worker = RefreshWorker(manager, settings.refresh_interval_seconds)
        refresh_worker.start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    if refresh_worker:
        refresh_worker.stop()
        refresh_worker.join(timeout=5)
    manager.shutdown()


@app.get("/healthz")
async def healthz() -> dict:
    status = manager.status()
    status["settings"] = {
        "protocols": list(settings.supports_protocol),
        "glider_enabled": settings.enable_glider,
    }
    return status
