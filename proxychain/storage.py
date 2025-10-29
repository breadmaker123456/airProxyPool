from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


class JsonStorage:
    """A thin wrapper around a JSON file with basic locking and atomic writes."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def load(self, default: Any) -> Any:
        with self._lock:
            if not self.path.exists():
                return default
            try:
                with self.path.open("r", encoding="utf-8") as handle:
                    return json.load(handle)
            except json.JSONDecodeError:
                # Keep corrupted file as backup for inspection
                backup = self.path.with_suffix(self.path.suffix + ".invalid")
                try:
                    self.path.rename(backup)
                except OSError:
                    pass
                return default

    def save(self, data: Any) -> None:
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        with self._lock:
            with temp_path.open("w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
            temp_path.replace(self.path)
