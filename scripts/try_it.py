"""Developer smoke script.

Runs a minimal end-to-end check against a running local API:
- GET /health
- GET /version
- POST /query ("Say hello in one short sentence.")

Exit codes:
- 0 on success
- 1 on any non-200 response or unexpected exception

No heavy dependencies: only `requests`. Colorized output via ANSI codes.
"""

from __future__ import annotations
import os
import sys
import json

try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover
    print("requests package not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

# Minimal ANSI helpers


class Color:
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    RESET = "\033[0m"


def load_env(path: str = ".env") -> None:
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k not in os.environ:
                os.environ[k] = v


def pretty(obj) -> str:
    try:
        return json.dumps(obj, indent=2, ensure_ascii=False)
    except Exception:
        return str(obj)


def request_json(method: str, url: str, **kwargs):
    try:
        r = requests.request(method, url, timeout=10, **kwargs)
    except requests.RequestException as e:  # connection errors, timeouts, etc.
        return -1, f"Request failed: {e}"
    try:
        data = r.json()
    except Exception:
        data = r.text
    return r.status_code, data


def main() -> int:
    load_env()
    base = os.getenv("SMOKE_BASE_URL", "http://localhost:8088")
    api_key = os.getenv("CKA_API_KEY")

    headers = {}
    if api_key:
        headers["X-CKA-API-Key"] = api_key

    steps = [
        ("health", "GET", f"{base}/health", {}),
        ("version", "GET", f"{base}/version", {}),
        (
            "query",
            "POST",
            f"{base}/query",
            {"json": {"query": "Say hello in one short sentence."}, "headers": headers},
        ),
    ]

    failed = False
    for name, method, url, extra in steps:
        print(f"{Color.CYAN}==> {name.upper()} {Color.RESET}{url}")
        status, data = request_json(method, url, **extra)
        color = Color.GREEN if status == 200 else Color.RED
        print(f"Status: {color}{status}{Color.RESET}")
        print(pretty(data))
        if status != 200:
            failed = True
        print()

    if failed:
        print(f"{Color.RED}Smoke check FAILED{Color.RESET}")
        return 1
    print(f"{Color.GREEN}Smoke check PASSED{Color.RESET}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
