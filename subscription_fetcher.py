#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
subscription_fetcher.py

Standalone subscription tool that does NOT modify existing project files unless explicitly requested.

Features:
- Fetch subscription content from a URL (yaml or txt)
- Parse into glider-compatible "forward=" lines
  - YAML: expects Clash-style { proxies: [...] }, reuses parse.py:parse_config
  - TXT: accepts lines beginning with ss:// or vmess://
    - Supports vmess://<base64-json> by decoding into glider URL form
- Output a standalone config file by default (glider/glider.subscription.conf)
- Optional: install the generated forward lines into glider/glider.conf (replace existing forward lines only)

Usage examples (PowerShell):
  python subscription_fetcher.py --url "https://example.com/sub.yaml" --format yaml
  python subscription_fetcher.py --url "https://example.com/sub.txt" --format txt --output-config glider/custom.conf
  python subscription_fetcher.py --url "https://example.com/sub.yaml" --install-to-main-config
"""

import argparse
import base64
import re
import sys
from pathlib import Path
from typing import Tuple, List

import yaml  # from requirements.txt

try:
    import requests
except ImportError:
    requests = None


BASE_CONFIG = """# Verbose mode, print logs
verbose=true

# listen address
listen=:10707

# strategy: rr (round-robin) or ha (high-availability)
strategy=rr

# forwarder health check
check=http://www.msftconnecttest.com/connecttest.txt#expect=200

# check interval(seconds)
checkinterval=30

"""


def _ensure_requests():
    if requests is None:
        print("Error: requests is required. Please 'pip install -r requirements.txt'", file=sys.stderr)
        sys.exit(1)


def _b64_decode(s: str) -> bytes:
    # Add padding for base64-url or base64 strings if needed
    s = s.strip()
    # URL-safe replace
    s = s.replace('-', '+').replace('_', '/')
    padding = (-len(s)) % 4
    s_padded = s + ('=' * padding)
    return base64.b64decode(s_padded)


def _vmess_from_base64(uri: str) -> str:
    """Convert vmess://<base64-json> to glider-friendly vmess URL.

    Expected JSON fields: add, port, id (uuid), aid (alterId).
    Output: vmess://none:{uuid}@{add}:{port}?alterID={aid}
    """
    payload = uri[len('vmess://'):]  # strip scheme
    try:
        raw = _b64_decode(payload).decode('utf-8', errors='ignore')
        data = yaml.safe_load(raw)  # yaml.safe_load can parse JSON too
        if not isinstance(data, dict):
            raise ValueError("Invalid vmess JSON payload")
        server = str(data.get('add', '')).strip()
        port = str(data.get('port', '')).strip()
        uuid = str(data.get('id', '')).strip()
        alter_id = str(data.get('aid', '0')).strip() or '0'
        if not (server and port and uuid):
            raise ValueError("Missing required vmess fields (add/port/id)")
        return f"vmess://none:{uuid}@{server}:{port}?alterID={alter_id}"
    except Exception as e:
        # If decode fails, return original to allow downstream filtering/inspection
        return uri


def parse_subscription_txt(text: str) -> Tuple[str, int]:
    """Parse plain-text subscription content into glider forward= lines.

    - Accepts lines beginning with ss:// or vmess://
    - Supports vmess://<base64-json> by converting to glider URL
    - Ignores empty lines and comments (# ...)
    """
    forwards: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('ss://'):
            forwards.append(f"forward={line}")
        elif line.startswith('vmess://'):
            # If not already glider form (with '@'), try to decode base64-JSON
            candidate = line if '@' in line else _vmess_from_base64(line)
            forwards.append(f"forward={candidate}")
        # silently ignore unsupported schemes
    out = "\n".join(f for f in forwards)
    if out and not out.endswith('\n'):
        out += '\n'
    return out, len(forwards)


def parse_subscription_yaml(text: str) -> Tuple[str, int]:
    """Parse YAML (Clash-like) content into glider forward= lines using parse.py logic.
    Returns (forward_content, count).
    """
    import importlib.util
    current_dir = Path(__file__).parent.absolute()
    parse_path = current_dir / "parse.py"
    if not parse_path.exists():
        raise FileNotFoundError(f"Parser script not found at {parse_path}")

    data = yaml.safe_load(text) or {}
    proxies = data.get('proxies', [])

    spec = importlib.util.spec_from_file_location("parse_module", str(parse_path))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    forward_content = mod.parse_config(proxies)
    return forward_content, len(proxies)


def write_standalone_config(output_path: Path, forward_content: str, include_base: bool = True):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = (BASE_CONFIG if include_base else "") + forward_content
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)


def install_into_main_glider_conf(forward_content: str):
    """Replace forward= lines inside glider/glider.conf only; preserve other settings."""
    current_dir = Path(__file__).parent.absolute()
    glider_conf_path = current_dir / "glider" / "glider.conf"
    glider_conf_path.parent.mkdir(parents=True, exist_ok=True)

    if not glider_conf_path.exists():
        # If main conf doesn't exist, create a minimal one with base + forwards
        write_standalone_config(glider_conf_path, forward_content, include_base=True)
        return

    with open(glider_conf_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if re.search(r'^(?:forward=.*\n)+', content, flags=re.MULTILINE):
        new_content = re.sub(r'^(?:forward=.*\n)+', forward_content, content, flags=re.MULTILINE)
    else:
        new_content = content.rstrip() + '\n' + forward_content

    with open(glider_conf_path, 'w', encoding='utf-8') as f:
        f.write(new_content)


def main():
    ap = argparse.ArgumentParser(description='Fetch a subscription and produce glider forwards/config (standalone).')
    ap.add_argument('--url', required=True, help='Subscription URL')
    ap.add_argument('--format', choices=['auto', 'yaml', 'txt'], default='auto', help='Subscription content format')
    ap.add_argument('--timeout', type=int, default=30, help='HTTP timeout seconds')

    # Output options
    ap.add_argument('--output-config', default=str(Path('glider') / 'glider.subscription.conf'), help='Path to write a standalone config')
    ap.add_argument('--output-forwards-only', action='store_true', help='Write only forward= lines (no base config)')
    ap.add_argument('--install-to-main-config', action='store_true', help='Replace forward= lines in glider/glider.conf')

    # Diagnostics
    ap.add_argument('--dry-run', action='store_true', help='Do not write files; just parse and report counts')

    args = ap.parse_args()

    _ensure_requests()

    try:
        resp = requests.get(args.url, timeout=args.timeout)
        resp.raise_for_status()
    except Exception as e:
        print(f"Error fetching subscription: {e}", file=sys.stderr)
        sys.exit(1)

    fmt = args.format
    if fmt == 'auto':
        # naive auto-detection by content type and/or first non-empty char
        ctype = resp.headers.get('Content-Type', '').lower()
        if 'yaml' in ctype or 'yml' in ctype:
            fmt = 'yaml'
        elif 'text/plain' in ctype:
            fmt = 'txt'
        else:
            # peek first non-empty line
            head = next((ln.strip() for ln in resp.text.splitlines() if ln.strip()), '')
            fmt = 'yaml' if head.startswith('proxies:') else 'txt'

    if fmt == 'yaml':
        try:
            forward_content, count = parse_subscription_yaml(resp.text)
        except Exception as e:
            print(f"Error parsing YAML subscription: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        forward_content, count = parse_subscription_txt(resp.text)

    if not forward_content:
        print('No usable entries parsed from subscription.', file=sys.stderr)
        sys.exit(2)

    print(f"Parsed {count} entries. Format={fmt}.")

    if args.dry_run:
        return

    # Write standalone config by default
    output_path = Path(args.output_config)
    write_standalone_config(output_path, forward_content, include_base=not args.output_forwards_only)
    print(f"Wrote {'forwards' if args.output_forwards_only else 'config'} to: {output_path}")

    if args.install_to_main_config:
        install_into_main_glider_conf(forward_content)
        print("Installed forwards into glider/glider.conf")


if __name__ == '__main__':
    main()
