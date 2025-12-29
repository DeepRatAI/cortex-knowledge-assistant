"""Structured logging configuration.

Uses structlog for JSON-formatted logs usable in ELK/Grafana pipelines.
"""

from __future__ import annotations

import logging
import sys

import structlog

try:  # Optional: enrich logs with OpenTelemetry trace context
    from opentelemetry import trace as _otel_trace  # type: ignore
except Exception:  # pragma: no cover
    _otel_trace = None


def configure_logging() -> None:
    """Configure structured logging with trace & scrub processors."""

    timestamper = structlog.processors.TimeStamper(fmt="iso")

    def _inject_trace(logger, method_name, event_dict):  # pragma: no cover
        if _otel_trace is None:
            return event_dict
        span = _otel_trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.is_valid:
            event_dict["trace_id"] = format(ctx.trace_id, "032x")
            event_dict["span_id"] = format(ctx.span_id, "016x")
        return event_dict

    def _scrub(logger, method_name, event_dict):  # pragma: no cover
        import re

        patterns = [
            re.compile(r"(api[_-]?key|token|authorization)\s*[:=]\s*[^\s]+", re.I),
            re.compile(r"bearer\s+[a-z0-9\-_.=]+", re.I),
        ]
        for k, v in event_dict.items():
            if isinstance(v, str):
                for pat in patterns:
                    v = pat.sub("<redacted>", v)
                event_dict[k] = v
        return event_dict

    structlog.configure(
        processors=[
            timestamper,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            _scrub,
            _inject_trace,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


configure_logging()

logger = structlog.get_logger()
