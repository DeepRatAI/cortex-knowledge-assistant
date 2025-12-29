import os
import sys
import json
import requests

MODELS = [
    # Primary small/medium candidates (router-based inference)
    "HuggingFaceTB/SmolLM3-3B",
    "HuggingFaceTB/SmolLM2-360M-Instruct",
    "HuggingFaceTB/SmolLM2-135M",
    "google/flan-t5-small",
    "google/flan-t5-base",
    "google/flan-t5-large",
    "CohereForAI/aya-23-1B",
    # Additional instruct / fallback
    "Qwen/Qwen2.5-0.5B-Instruct",
    "Qwen/Qwen2.5-1.5B-Instruct",
    "HuggingFaceH4/zephyr-7b-beta",
    "mistralai/Mistral-7B-Instruct-v0.2",
    "meta-llama/Llama-3.2-3B-Instruct",
]


ROUTER = "https://router.huggingface.co/hf-inference/models"


def probe(model: str, token: str) -> tuple[int, str]:
    url = f"{ROUTER}/{model}"
    try:
        r = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Wait-For-Model": "true",
            },
            json={"inputs": "ping", "parameters": {"max_new_tokens": 1}},
            timeout=25,
        )
        try:
            data = r.json()
        except Exception:
            data = r.text
        # Return status and a concise message if any
        msg = ""
        if isinstance(data, dict) and "error" in data:
            msg = str(data.get("error"))
        elif isinstance(data, str):
            msg = data[:120]
        return r.status_code, msg
    except Exception as e:
        return -1, f"exception:{type(e).__name__}"


def main():
    token = os.getenv("HF_API_KEY") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
    if not token:
        print("HF_API_KEY missing in env", file=sys.stderr)
        return 1
    results = []
    for m in MODELS:
        code, msg = probe(m, token)
        results.append((m, code, msg))
        print(f"{m:40s} -> {code} {msg}")
    # Save JSON for inspection
    with open("hf_scan_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    # Exit 0 if any 200/503 found
    if any(code in (200, 503) for _, code, _ in results):
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
