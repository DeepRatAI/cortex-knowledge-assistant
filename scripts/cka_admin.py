"""Cortex KA admin/diagnostic CLI.

This CLI is intentionally minimal and read-only. It provides commands to:
- Check basic health of the API and its dependencies.
- Validate critical configuration values.
- Exercise the PII redaction/DLP pipeline on sample text.

It is meant to be a starting point for operational tooling in regulated
environments (e.g. banking), not a full management console.
"""

from __future__ import annotations

import os
import sys
import json
import argparse
from typing import Any

import httpx

from cortex_ka.api.main import redact_pii


def cmd_health(args: argparse.Namespace) -> int:
    base_url = args.base_url.rstrip("/")
    try:
        r = httpx.get(f"{base_url}/health", timeout=5)
        r.raise_for_status()
    except Exception as exc:  # pragma: no cover - operational path
        print(f"health check failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(r.json(), indent=2, sort_keys=True))
    return 0


def cmd_check_config(_: argparse.Namespace) -> int:
    """Print a summary of critical configuration knobs.

    This does not print secret values, only whether they are present.
    """

    keys = [
        "CKA_API_KEY",
        "HF_API_KEY",
        "CKA_QDRANT_URL",
        "CKA_QDRANT_API_KEY",
        "CKA_USE_QDRANT",
        "CKA_USE_REDIS",
        "CKA_LLM_PROVIDER",
    ]
    summary: dict[str, Any] = {}
    for k in keys:
        val = os.getenv(k)
        if k.endswith("API_KEY") or k.endswith("_TOKEN"):
            summary[k] = "<set>" if val else "<unset>"
        else:
            summary[k] = val or "<unset>"
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def cmd_test_dlp(args: argparse.Namespace) -> int:
    text = args.text
    redacted = redact_pii(text)
    out = {"input": text, "redacted": redacted}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cka-admin", description="Cortex KA admin CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_health = sub.add_parser("health", help="Check API /health endpoint")
    p_health.add_argument(
        "--base-url",
        default=os.getenv("CKA_ADMIN_BASE_URL", "http://localhost:8088"),
        help="Base URL of the Cortex KA API",
    )
    p_health.set_defaults(func=cmd_health)

    p_cfg = sub.add_parser("check-config", help="Print critical configuration summary")
    p_cfg.set_defaults(func=cmd_check_config)

    p_dlp = sub.add_parser("test-dlp", help="Run PII redaction on given text")
    p_dlp.add_argument("text", help="Text to run through the redaction pipeline")
    p_dlp.set_defaults(func=cmd_test_dlp)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if not func:
        parser.print_help()
        return 1
    return func(args)


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    raise SystemExit(main())
