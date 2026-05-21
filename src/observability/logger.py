"""Structured logging + append-only audit log for every agent/tool/trade event."""
import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

_configured = False
_audit_lock = threading.Lock()


def configure_logging(log_level: str = "INFO", audit_log_path: str = "./data/audit.jsonl", otlp_endpoint: str = "") -> None:
    global _configured
    if _configured:
        return

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}.get(log_level.upper(), 20)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )

    resource = Resource.create({"service.name": "ai-investment-firm"})
    provider = TracerProvider(resource=resource)

    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint)))
        except Exception:
            pass  # OTLP is optional
    else:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    Path(audit_log_path).parent.mkdir(parents=True, exist_ok=True)
    _configured = True


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)


def audit(event: str, audit_log_path: str = "./data/audit.jsonl", **kwargs: Any) -> None:
    """Append a single structured event to the immutable audit log."""
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "event": event,
        **kwargs,
    }
    with _audit_lock:
        with open(audit_log_path, "a") as f:
            f.write(json.dumps(record) + "\n")


def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)
