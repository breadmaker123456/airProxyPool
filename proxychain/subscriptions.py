from __future__ import annotations

import base64
import importlib.util
import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple

try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover - dependency should be present
    requests = None  # type: ignore[assignment]

import yaml

logger = logging.getLogger(__name__)


def _b64_decode(value: str) -> bytes:
    cleaned = value.strip().replace("-", "+").replace("_", "/")
    padding = (-len(cleaned)) % 4
    return base64.b64decode(cleaned + ("=" * padding))


def _vmess_from_base64(uri: str) -> str:
    payload = uri[len("vmess://") :]
    try:
        raw = _b64_decode(payload).decode("utf-8", errors="ignore")
        data = yaml.safe_load(raw)
        if not isinstance(data, dict):
            raise ValueError("Invalid vmess JSON payload")
        server = str(data.get("add", "")).strip()
        port = str(data.get("port", "")).strip()
        uuid = str(data.get("id", "")).strip()
        alter_id = str(data.get("aid", "0")).strip() or "0"
        if not (server and port and uuid):
            raise ValueError("Missing required vmess fields (add/port/id)")
        return f"vmess://none:{uuid}@{server}:{port}?alterID={alter_id}"
    except Exception:  # pragma: no cover - defensive fallback
        return uri


def _maybe_decode_base64_blob(payload: str) -> str:
    compact = "".join(payload.split())
    if not compact:
        return payload
    if not re.fullmatch(r"[A-Za-z0-9+/=_-]+", compact):
        return payload
    try:
        decoded = _b64_decode(compact).decode("utf-8", errors="ignore")
        if "ss://" in decoded or "vmess://" in decoded:
            return decoded
    except Exception:
        pass
    return payload


def _normalize_ss_uri(uri: str) -> str:
    try:
        rest = uri[len("ss://") :]
        if "@" in rest:
            userinfo, tail = rest.split("@", 1)
            if re.fullmatch(r"[A-Za-z0-9+/=_-]+", userinfo) and ":" not in userinfo:
                try:
                    decoded = _b64_decode(userinfo).decode("utf-8", errors="ignore")
                    if ":" in decoded and "@" not in decoded:
                        return f"ss://{decoded}@{tail}"
                except Exception:
                    pass
            return uri
        base_part = rest.split("#", 1)[0]
        suffix = rest[len(base_part) :]
        if re.fullmatch(r"[A-Za-z0-9+/=_-]+", base_part):
            try:
                decoded_full = _b64_decode(base_part).decode("utf-8", errors="ignore")
                if ":" in decoded_full and "@" in decoded_full:
                    return f"ss://{decoded_full}{suffix}"
            except Exception:
                pass
        return uri
    except Exception:
        return uri


def _parse_lines(text: str) -> List[str]:
    forwards: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("ss://"):
            forwards.append(f"forward={_normalize_ss_uri(line)}")
        elif line.startswith("vmess://"):
            candidate = line if "@" in line else _vmess_from_base64(line)
            forwards.append(f"forward={candidate}")
    return forwards


def parse_txt_content(text: str) -> Tuple[str, int]:
    text_to_parse = _maybe_decode_base64_blob(text)
    forwards = _parse_lines(text_to_parse)
    if not forwards:
        compact = "".join(text.split())
        try:
            decoded = _b64_decode(compact).decode("utf-8", errors="ignore")
            forwards = _parse_lines(decoded)
        except Exception:
            forwards = []
    output = "\n".join(forwards)
    if output and not output.endswith("\n"):
        output += "\n"
    return output, len(forwards)


def parse_yaml_content(text: str) -> Tuple[str, int]:
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent
    parse_path = project_root / "parse.py"
    if not parse_path.exists():
        raise FileNotFoundError(f"Parser script not found at {parse_path}")
    data = yaml.safe_load(text) or {}
    proxies = data.get("proxies", [])
    spec = importlib.util.spec_from_file_location("parse_module", str(parse_path))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    forward_content = module.parse_config(proxies)
    return forward_content, len(proxies)


def detect_format_from_response(resp_text: str, content_type: str) -> str:
    ct = (content_type or "").lower()
    first_line = next((ln.strip() for ln in resp_text.splitlines() if ln.strip()), "")
    if first_line.startswith("proxies:"):
        return "yaml"
    if "yaml" in ct or "yml" in ct:
        return "yaml"
    if "text/plain" in ct:
        return "txt"
    return "txt"


def fetch_and_parse(urls: List[str], *, timeout: float = 30.0, verify: bool = False) -> Tuple[str, dict]:
    logger.debug("Fetching %s subscription URLs", len(urls))
    if requests is None:  # pragma: no cover - depends on environment
        raise RuntimeError("requests library is required to fetch subscriptions")
    forwards: List[str] = []
    by_url: Dict[str, dict[str, object]] = {}
    stats = {
        "total_urls": len(urls),
        "ok_urls": 0,
        "failed_urls": 0,
        "entries": 0,
        "by_url": by_url,
    }

    with requests.Session() as session:
        for url in urls:
            url_stats: dict[str, object] = {"count": 0, "error": None, "format": None}
            try:
                logger.debug("Requesting subscription URL %s", url)
                response = session.get(url, timeout=timeout, verify=verify)
                response.raise_for_status()
                fmt = detect_format_from_response(response.text, response.headers.get("Content-Type", ""))
                url_stats["format"] = fmt
                if fmt == "yaml":
                    content, count = parse_yaml_content(response.text)
                else:
                    content, count = parse_txt_content(response.text)
                if count > 0:
                    forwards.extend([ln.strip() for ln in content.splitlines() if ln.strip()])
                    url_stats["count"] = count
                    stats["ok_urls"] += 1
                else:
                    url_stats["error"] = "No usable entries"
                    stats["failed_urls"] += 1
            except Exception as exc:  # pragma: no cover - network heavy
                url_stats["error"] = str(exc)
                stats["failed_urls"] += 1
                logger.warning("Failed to fetch subscription URL %s: %s", url, exc)
            by_url[url] = url_stats

    deduped: List[str] = []
    seen = set()
    for line in forwards:
        if not line.startswith("forward="):
            continue
        if line in seen:
            continue
        deduped.append(line)
        seen.add(line)

    combined = "\n".join(deduped)
    if combined:
        combined += "\n"
    stats["entries"] = len(deduped)
    return combined, stats


def read_subscriptions_file(path: Path) -> List[str]:
    if not path.exists():
        return []
    urls: List[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            urls.append(line)
    return urls
