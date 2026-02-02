import json
import logging
import os
from datetime import datetime, timezone

from app.core.middleware.correlation import get_correlation_id


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "correlation_id": getattr(record, "correlation_id", None),
        }
        return json.dumps(payload)


def configure_logging() -> None:
    root = logging.getLogger()
    log_level = os.getenv("RA_LOG_LEVEL", "INFO").upper()
    root.setLevel(getattr(logging, log_level, logging.INFO))

    handler = logging.StreamHandler()
    handler.setLevel(root.level)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(CorrelationIdFilter())

    root.handlers.clear()
    root.addHandler(handler)

    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
    logging.getLogger("agent_framework").setLevel(logging.INFO)
