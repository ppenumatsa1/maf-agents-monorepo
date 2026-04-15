import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Iterator

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.trace import Status, StatusCode

from app.core.middleware.correlation import get_correlation_id

logger = logging.getLogger(__name__)
_tracer = trace.get_tracer("researcher-agent")
_meter = metrics.get_meter("researcher-agent")
_telemetry_configured = False

_research_requests_total = _meter.create_counter(
    "research_requests_total",
    unit="{request}",
    description="Count of research API requests.",
)
_research_failures_total = _meter.create_counter(
    "research_failures_total",
    unit="{request}",
    description="Count of research API requests that failed.",
)
_research_duration_ms = _meter.create_histogram(
    "research_duration_ms",
    unit="ms",
    description="Research request duration in milliseconds.",
)
_stream_chunks_total = _meter.create_counter(
    "research_stream_chunks_total",
    unit="{chunk}",
    description="Count of streamed chunks emitted by the research endpoint.",
)
_auth_attempts_total = _meter.create_counter(
    "auth_attempts_total",
    unit="{attempt}",
    description="Count of authentication attempts at integration boundaries.",
)
_auth_failures_total = _meter.create_counter(
    "auth_failures_total",
    unit="{attempt}",
    description="Count of failed authentication attempts at integration boundaries.",
)


def configure_telemetry(app: FastAPI) -> None:
    """Configure Azure Monitor + Agent Framework telemetry."""
    global _telemetry_configured
    if _telemetry_configured:
        logger.debug("Telemetry already configured; skipping duplicate setup.")
        return

    telemetry_enabled = os.getenv("ENABLE_TELEMETRY", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not telemetry_enabled:
        logger.info("Telemetry disabled by ENABLE_TELEMETRY flag.")
        return

    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection_string:
        logger.warning("APPLICATIONINSIGHTS_CONNECTION_STRING is not set; telemetry is disabled.")
        return

    create_resource = None
    enable_instrumentation = None
    try:
        from agent_framework.observability import create_resource, enable_instrumentation
    except Exception as exc:
        logger.warning(
            "Agent Framework observability unavailable; continuing without AF hooks: %s", exc
        )

    azure_monitor_args: dict[str, Any] = {
        "connection_string": connection_string,
        "enable_live_metrics": True,
    }
    if create_resource:
        azure_monitor_args["resource"] = create_resource()

    try:
        # Import lazily so telemetry dependency issues do not prevent app startup.
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(**azure_monitor_args)
    except Exception as exc:
        logger.exception("Failed to configure Azure Monitor telemetry: %s", exc)
        return

    _telemetry_configured = True

    # Azure Monitor distro enables supported instrumentations (including FastAPI/requests)
    # by default. Do not re-instrument manually.

    if enable_instrumentation:
        # Dev mode requirement: always capture sensitive payload content for richer trace analysis.
        enable_instrumentation(enable_sensitive_data=True)


@contextmanager
def start_span(
    name: str, attributes: dict[str, str | bool | int | float] | None = None
) -> Iterator[object]:
    with _tracer.start_as_current_span(name) as span:
        if span and span.is_recording():
            correlation_id = get_correlation_id()
            if correlation_id:
                span.set_attribute("app.correlation_id", correlation_id)
            if attributes:
                for key, value in attributes.items():
                    if value is not None:
                        span.set_attribute(key, value)
        try:
            yield span
        except Exception as exc:
            if span and span.is_recording():
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
            raise


def emit_business_event(
    name: str, attributes: dict[str, str | bool | int | float] | None = None
) -> None:
    attrs = _build_attributes(attributes)
    span = trace.get_current_span()
    if span and span.is_recording():
        span.add_event(name=name, attributes=attrs)
    logger.info("business_event=%s attributes=%s", name, attrs)


def record_research_started(attributes: dict[str, str | bool | int | float] | None = None) -> None:
    attrs = _build_attributes(attributes)
    _research_requests_total.add(1, attrs)
    emit_business_event("research.request.started", attrs)


def record_research_completed(
    duration_ms: float, attributes: dict[str, str | bool | int | float] | None = None
) -> None:
    attrs = _build_attributes(attributes)
    _research_duration_ms.record(duration_ms, attrs)
    emit_business_event(
        "research.request.completed", {**attrs, "duration_ms": round(duration_ms, 2)}
    )


def record_research_failed(
    reason: str, attributes: dict[str, str | bool | int | float] | None = None
) -> None:
    attrs = _build_attributes({**(attributes or {}), "reason": reason})
    _research_failures_total.add(1, attrs)
    emit_business_event("research.request.failed", attrs)


def record_stream_chunk(
    chunk_index: int, attributes: dict[str, str | bool | int | float] | None = None
) -> None:
    attrs = _build_attributes({**(attributes or {}), "chunk_index": chunk_index})
    _stream_chunks_total.add(1, attrs)
    if chunk_index == 1 or chunk_index % 50 == 0:
        emit_business_event("research.stream.chunk_emitted", attrs)


def record_auth_outcome(
    integration: str,
    success: bool,
    reason: str | None = None,
    attributes: dict[str, str | bool | int | float] | None = None,
) -> None:
    merged_attrs: dict[str, str | bool | int | float] = {
        "integration": integration,
        "success": success,
    }
    if reason:
        merged_attrs["reason"] = reason
    if attributes:
        merged_attrs.update(attributes)

    attrs = _build_attributes(merged_attrs)
    _auth_attempts_total.add(1, attrs)
    if not success:
        _auth_failures_total.add(1, attrs)
        emit_business_event("auth.integration.failed", attrs)
    else:
        emit_business_event("auth.integration.succeeded", attrs)


def now_ms() -> float:
    return time.perf_counter() * 1000


def _build_attributes(
    attributes: dict[str, str | bool | int | float] | None = None,
) -> dict[str, str | bool | int | float]:
    attrs = dict(attributes or {})
    correlation_id = get_correlation_id()
    if correlation_id and "app.correlation_id" not in attrs:
        attrs["app.correlation_id"] = correlation_id
    return attrs
