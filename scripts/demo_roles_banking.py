"""Role-based E2E demo for Cortex Knowledge Assistant.

This script is intended to be run in CI (e.g. GitHub Actions) to
showcase typical banking use cases for two roles backed by the same
backend:

- Standard customer service agent (DLP enforced).
- Privileged backoffice / risk manager (reduced DLP, can see PII
  in tightly controlled environments).

It assumes the API is already running and reachable via
`CKA_DEMO_BASE_URL`.

The script does *not* modify any server state; it is a pure client of
the public HTTP API.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict

import requests


@dataclass
class RoleConfig:
    name: str
    api_key: str
    expects_pii_redacted: bool


DEMO_BASE_URL = os.getenv("CKA_DEMO_BASE_URL", "http://localhost:8000")
STANDARD_API_KEY = os.getenv("CKA_STANDARD_API_KEY", "demo-key-cli-81093")
PRIVILEGED_API_KEY = os.getenv("CKA_PRIVILEGED_API_KEY", "demo-key-cli-81093-ops")
TIMEOUT = float(os.getenv("CKA_DEMO_TIMEOUT", "30"))


def _print_header(title: str) -> None:
    bar = "=" * len(title)
    print(f"\n{bar}\n{title}\n{bar}")


def _get(url: str) -> Dict[str, Any]:
    resp = requests.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _post_query(api_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{DEMO_BASE_URL.rstrip('/')}/query"
    headers = {"X-CKA-API-Key": api_key}
    resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _assert_health() -> None:
    _print_header("Checking /health")
    url = f"{DEMO_BASE_URL.rstrip('/')}/health"
    data = _get(url)
    print("/health response:", data)

    provider = data.get("provider")
    provider_ok = data.get("provider_ok")

    if provider != "hf":
        raise SystemExit(f"Expected provider 'hf', got {provider!r}")
    if provider_ok is not True:
        raise SystemExit("Expected provider_ok == true")


def _contains_known_pii(answer: str) -> bool:
    """Very small PII heuristic matching what the main demo uses.

    We only look for a couple of known synthetic fragments; this is not
    a generic PII detector.
    """

    if not answer:
        return False

    candidates = [
        "49014052F",  # DNI used in the synthetic examples
        "4111 1111 1111 1111",  # classic test card pattern
        "4111111111111111",
    ]
    lowered = answer
    return any(fragment in lowered for fragment in candidates)


def _assert_response_shape(resp: Dict[str, Any]) -> None:
    if "answer" not in resp:
        raise SystemExit("Missing 'answer' field in response")
    if "used_chunks" not in resp:
        raise SystemExit("Missing 'used_chunks' in response")
    if "citations" not in resp:
        raise SystemExit("Missing 'citations' in response")


def _run_role_scenario(role: RoleConfig) -> None:
    _print_header(f"Role scenario: {role.name}")

    banking_question = {
        "query": "What is the minimum documentation required to approve a standard personal loan for an existing customer?",
        "conversation_id": "demo-roles-banking-1",
    }

    policy_question = {
        "query": "Summarize the confidentiality and data-protection rules that agents must follow when handling DNI and card numbers.",
        "conversation_id": "demo-roles-banking-2",
    }

    pii_question = {
        "query": "Customer DNI 49014052F and card 4111 1111 1111 1111 were used in a suspicious transaction. Summarize the risk signals and next steps.",
        "conversation_id": "demo-roles-banking-3",
    }

    scenarios = [
        ("normal_banking", banking_question),
        ("confidentiality_policy", policy_question),
        ("transaction_with_pii", pii_question),
    ]

    for label, payload in scenarios:
        print(f"\n--- {role.name} – {label} ---")
        resp = _post_query(role.api_key, payload)
        _assert_response_shape(resp)
        answer = resp.get("answer", "")

        print("Answer:\n", answer)
        print("used_chunks (count):", len(resp.get("used_chunks", [])))
        print("citations (count):", len(resp.get("citations", [])))

        if label == "transaction_with_pii":
            has_pii = _contains_known_pii(answer)
            if role.expects_pii_redacted and has_pii:
                raise SystemExit(
                    f"Role {role.name} expected PII to be redacted but answer contains known PII fragments."
                )
            if not role.expects_pii_redacted and not has_pii:
                # We only warn here instead of failing hard, because
                # actual model behaviour may choose to paraphrase PII.
                print(
                    "[WARN] Privileged role did not surface known PII fragments; "
                    "this may be acceptable depending on policy."
                )


def main() -> int:
    _assert_health()

    standard_role = RoleConfig(
        name="standard_customer_service_agent",
        api_key=STANDARD_API_KEY,
        expects_pii_redacted=True,
    )

    privileged_role = RoleConfig(
        name="privileged_backoffice_manager",
        api_key=PRIVILEGED_API_KEY,
        expects_pii_redacted=False,
    )

    _run_role_scenario(standard_role)
    _run_role_scenario(privileged_role)

    print("\nAll role scenarios completed.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
