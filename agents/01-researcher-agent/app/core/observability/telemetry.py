import logging
import os
from contextlib import contextmanager
from typing import Iterator

from agent_framework.observability import create_resource, enable_instrumentation
from azure.monitor.opentelemetry import configure_azure_monitor
from fastapi import FastAPI
from opentelemetry import trace

from app.core.middleware.correlation import get_correlation_id

logger = logging.getLogger(__name__)


def configure_telemetry(app: FastAPI) -> None:
    """Configure Azure Monitor + Agent Framework telemetry."""
    _ = app

    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection_string:
        logger.warning("APPLICATIONINSIGHTS_CONNECTION_STRING is not set; telemetry is disabled.")
        return

    configure_azure_monitor(
        connection_string=connection_string,
        resource=create_resource(),
        enable_live_metrics=True,
    )

    enable_instrumentation_flag = os.getenv("ENABLE_INSTRUMENTATION", "true").lower()
    if enable_instrumentation_flag == "true":
        enable_sensitive_data = os.getenv("ENABLE_SENSITIVE_DATA", "false").lower()
        enable_instrumentation(enable_sensitive_data=enable_sensitive_data == "true")


@contextmanager
def start_span(
    name: str, attributes: dict[str, str | bool | int | float] | None = None
) -> Iterator[object]:
    tracer = trace.get_tracer("researcher-agent")
    with tracer.start_as_current_span(name) as span:
        if span and span.is_recording():
            correlation_id = get_correlation_id()
            if correlation_id:
                span.set_attribute("app.correlation_id", correlation_id)
            if attributes:
                for key, value in attributes.items():
                    if value is not None:
                        span.set_attribute(key, value)
        yield span
