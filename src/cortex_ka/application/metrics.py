"""Prometheus metrics instrumentation for Cortex KA.

This module defines and exposes counters/histograms used by the API layer.
Separated to avoid import side-effects and keep FastAPI startup clean.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# Request counter labelled by endpoint and status class
http_requests_total = Counter(
    "cka_http_requests_total",
    "Total HTTP requests",
    labelnames=("endpoint", "status_class"),
)

# Query latency histogram (seconds)
query_latency_seconds = Histogram(
    "cka_query_latency_seconds",
    "Latency for /query endpoint",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)

# Retrieved chunks count distribution
retrieved_chunks = Histogram(
    "cka_retrieved_chunks_count",
    "Number of chunks retrieved per query",
    buckets=(0, 1, 2, 3, 5, 8, 13, 21),
)

# General HTTP request latency by endpoint (seconds)
http_request_latency_seconds = Histogram(
    "cka_http_request_latency_seconds",
    "HTTP request latency by endpoint",
    labelnames=("endpoint",),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

# Active model gauge (HF or other) - label holds provider and model id
active_model_info = Gauge(
    "cka_active_model_info",
    "Gauge set to 1 with labels provider/model to expose current LLM selection",
    labelnames=("provider", "model"),
)
