"""Evaluation script: measures latency of synthetic queries against local service.

Usage:
    python -m cortex_ka.scripts.evaluate --url http://localhost:8088 --n 5
"""

from __future__ import annotations

import argparse
import statistics
import time

import httpx


def run(url: str, n: int) -> None:
    latencies = []
    for i in range(n):
        t0 = time.perf_counter()
        resp = httpx.post(f"{url.rstrip('/')}/query", json={"query": f"Describe policy {i}"})
        dt = time.perf_counter() - t0
        latencies.append(dt)
        print({"i": i, "status": resp.status_code, "latency_s": round(dt, 4)})
    print(
        {
            "count": n,
            "p50": round(statistics.median(latencies), 4),
            "avg": round(sum(latencies) / n, 4),
            "max": round(max(latencies), 4),
        }
    )


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8088")
    parser.add_argument("--n", type=int, default=5)
    args = parser.parse_args()
    run(args.url, args.n)
