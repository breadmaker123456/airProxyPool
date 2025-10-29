#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# argparse removed — using top-of-file variables for configuration
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List
from concurrent.futures import ThreadPoolExecutor

from proxychain.subscriptions import fetch_and_parse, read_subscriptions_file

try:
    import requests
except ImportError:
    requests = None

# ==========================
# Configurable variables
# Edit these to control behavior without CLI args
# ==========================
SUBSCRIPTIONS_FILE = 'subscriptions.txt'  # path to txt file listing subscription URLs
CONFIG_OUTPUT = str(Path('glider') / 'glider.subscription.conf')  # output glider config path
LISTEN = 'mixed://:10710'  # listen address for glider (e.g., 'mixed://:10707' or 'socks5://127.0.0.1:10809')
INTERVAL_SECONDS = 6000  # refresh interval seconds
GLIDER_BINARY = str(Path('glider') / ('glider.exe' if os.name == 'nt' else 'glider'))  # path to glider binary
RUN_ONCE = False  # set True to run once and exit
DRY_RUN = False   # set True to fetch/parse only (no write/start)

# Per-forwarder testing configuration
TEST_EACH_FORWARD = True  # test each imported node for usability
TEST_URL = 'http://www.msftconnecttest.com/connecttest.txt#expect=200'  # use Google to test
TEST_EXPECT_STATUSES = (204, 200)  # acceptable HTTP statuses
TEST_TIMEOUT = 8  # seconds
TEST_LISTEN_HOST = '127.0.0.1'
TEST_START_PORT = 18081  # starting port for temporary glider listeners during tests
TEST_MAX_WORKERS = 20  # number of threads to test forwarders concurrently

# Health check URL used inside generated glider config
HEALTHCHECK_URL = 'http://www.msftconnecttest.com/connecttest.txt#expect=200'


def _ensure_requests():
    if requests is None:
        print("Error: requests is required. Please 'pip install -r requirements.txt'", file=sys.stderr)
        sys.exit(1)


def build_base_config(listen: str) -> str:
    return f"""# Verbose mode, print logs
verbose=true

# listen address
listen={listen}

# strategy: rr (round-robin) or ha (high-availability)
strategy=rr

# forwarder health check
check={HEALTHCHECK_URL}

# check interval(seconds)
checkinterval=300

"""


def write_config(config_path: Path, forward_content: str, listen: str):
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(build_base_config(listen))
        f.write(forward_content)


def read_subscriptions_file(path: Path) -> List[str]:
    if not path.exists():
        return []
    urls = []
    with open(path, 'r', encoding='utf-8') as f:
        for raw in f.readlines():
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            urls.append(line)
    return urls


def run_glider(glider_path: Path, config_path: Path):
    try:
        proc = subprocess.Popen([str(glider_path), '-config', str(config_path)], stdout=None, stderr=None, universal_newlines=True)
        return proc
    except Exception as e:
        print(f"Error starting glider: {e}")
        return None


def kill_glider(proc):
    if not proc:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    except Exception as e:
        print(f"Error killing glider: {e}")


def _choose_test_port(idx: int) -> int:
    return TEST_START_PORT + idx


def _write_temp_test_config(base_dir: Path, port: int, forward_line: str) -> Path:
    cfg_path = base_dir / f'glider.test.{port}.conf'
    content = build_base_config(f'http://{TEST_LISTEN_HOST}:{port}') + (forward_line if forward_line.endswith('\n') else forward_line + '\n')
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cfg_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return cfg_path


def _test_forwarder(glider_path: Path, forward_line: str, idx: int) -> bool:
    """Start a temporary glider with a single forward, then GET Google via HTTP proxy through it."""
    import time as _t
    tmp_cfg = _write_temp_test_config(Path('glider'), _choose_test_port(idx), forward_line)
    port = _choose_test_port(idx)
    proc = None
    try:
        proc = subprocess.Popen([str(glider_path), '-config', str(tmp_cfg)], stdout=None, stderr=None, universal_newlines=True)
        _t.sleep(0.8)  # give glider a moment to start
        proxies = {
            'http': f'http://{TEST_LISTEN_HOST}:{port}',
            'https': f'http://{TEST_LISTEN_HOST}:{port}',
        }
        r = requests.get(TEST_URL, proxies=proxies, timeout=TEST_TIMEOUT)
        return r.status_code in TEST_EXPECT_STATUSES
    except Exception:
        return False
    finally:
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        try:
            tmp_cfg.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            pass


def _filter_forwards_with_tests(glider_path: Path, forward_lines: List[str]) -> List[str]:
    if not TEST_EACH_FORWARD:
        return forward_lines
    ok = []
    futures = []
    with ThreadPoolExecutor(max_workers=TEST_MAX_WORKERS) as executor:
        for idx, line in enumerate(forward_lines):
            if not line.startswith('forward='):
                continue
            futures.append((line, executor.submit(_test_forwarder, glider_path, line, idx)))
        for line, fut in futures:
            try:
                if fut.result():
                    ok.append(line)
            except Exception:
                # treat as failed
                pass
    return ok


def main():
    # Use top-of-file variables instead of CLI args
    subs_path = Path(SUBSCRIPTIONS_FILE)
    config_path = Path(CONFIG_OUTPUT)
    glider_path = Path(GLIDER_BINARY)

    # Validate glider path exists
    if not glider_path.exists():
        print(f"Error: glider executable not found at {glider_path}")
        sys.exit(1)

    # Try to make executable (no-op on Windows)
    try:
        glider_path.chmod(0o755)
    except Exception:
        pass

    urls = read_subscriptions_file(subs_path)
    if not urls:
        print(f"No subscriptions found in {subs_path}. Add URLs (one per line).")
        sys.exit(1)

    _ensure_requests()

    # Initial fetch and write config
    forwards, stats = fetch_and_parse(urls)

    # Optional: per-forwarder testing with Google
    forward_lines = [ln.strip() for ln in forwards.splitlines() if ln.strip()]
    tested_lines = _filter_forwards_with_tests(glider_path, forward_lines)
    if tested_lines:
        forwards = "\n".join(tested_lines) + "\n"
    else:
        print("Warning: All tested forwards failed; falling back to untested set.")
    now = datetime.now()
    print(f"[{now}] Fetched subscriptions: ok={stats['ok_urls']}, failed={stats['failed_urls']}, entries={stats['entries']}")

    if DRY_RUN:
        return

    if stats['entries'] > 0:
        write_config(config_path, forwards, LISTEN)
    else:
        if config_path.exists():
            print(f"No usable entries; keeping existing config at {config_path}")
        else:
            print("No usable entries and no existing config. Exiting.")
            sys.exit(1)

    # Start glider
    proc = run_glider(glider_path, config_path)
    if not proc:
        print("Failed to start glider")
        sys.exit(1)

    if RUN_ONCE:
        print("Started glider once; exiting without loop as requested.")
        return

    last_content_hash = hash(forwards)

    def _cleanup(signum, frame):
        print("\nReceived termination signal. Cleaning up...")
        kill_glider(proc)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _cleanup)
    signal.signal(signal.SIGINT, _cleanup)

    while True:
        print(f"[{datetime.now()}] Waiting {INTERVAL_SECONDS} seconds until next update...")
        time.sleep(INTERVAL_SECONDS)
        urls = read_subscriptions_file(subs_path)
        if not urls:
            print(f"[{datetime.now()}] No subscriptions found; skipping update.")
            continue
        _ensure_requests()
        forwards, stats = fetch_and_parse(urls)
        print(f"[{datetime.now()}] Update: ok={stats['ok_urls']}, failed={stats['failed_urls']}, entries={stats['entries']}")
        if stats['entries'] <= 0:
            print("No usable entries; keeping current glider process and config.")
            continue
        # Test updated forwards
        forward_lines = [ln.strip() for ln in forwards.splitlines() if ln.strip()]
        tested_lines = _filter_forwards_with_tests(glider_path, forward_lines)
        if tested_lines:
            forwards = "\n".join(tested_lines) + "\n"
        else:
            print("Warning: All tested forwards failed; keeping current glider process and config.")
            continue
        new_hash = hash(forwards)
        if new_hash == last_content_hash:
            print("Entries unchanged; no restart needed.")
            continue
        # Write and restart
        write_config(config_path, forwards, LISTEN)
        print("Restarting glider...")
        kill_glider(proc)
        proc = run_glider(glider_path, config_path)
        if not proc:
            print("Failed to restart glider; will keep trying next cycle.")
            continue
        last_content_hash = new_hash
        print("Glider restarted with updated config.")


if __name__ == '__main__':
    main()
