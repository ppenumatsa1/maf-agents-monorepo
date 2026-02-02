from fastapi import FastAPI

from app.core.logging.logger import configure_logging
from app.core.middleware.correlation import CorrelationIdMiddleware
from app.core.observability.telemetry import configure_telemetry
from app.domain.routes.health import router as health_router
from app.domain.routes.research import router as research_router


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(title="01-researcher-agent", version="0.1.0")

    app.add_middleware(CorrelationIdMiddleware)
    configure_telemetry(app)

    app.include_router(health_router)
    app.include_router(research_router)

    return app
