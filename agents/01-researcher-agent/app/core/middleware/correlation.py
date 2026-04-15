import contextvars
import uuid
from typing import Callable

from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_correlation_id_ctx_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)


def get_correlation_id() -> str | None:
    return _correlation_id_ctx_var.get()


def set_correlation_id(value: str | None) -> None:
    _correlation_id_ctx_var.set(value)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        incoming = request.headers.get("x-correlation-id")
        correlation_id = incoming or str(uuid.uuid4())
        set_correlation_id(correlation_id)

        span = trace.get_current_span()
        if span and span.is_recording():
            span.set_attribute("app.correlation_id", correlation_id)

        response = await call_next(request)
        response.headers["x-correlation-id"] = correlation_id
        return response
