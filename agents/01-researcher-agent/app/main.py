from fastapi import FastAPI

from app.api.v1.routers.health import router as health_router
from app.api.v1.routers.research import router as research_router
from app.core.logging.logger import configure_logging
from app.core.middleware.correlation import CorrelationIdMiddleware
from app.core.observability.telemetry import configure_telemetry


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(title="01-researcher-agent", version="0.1.0")

    app.add_middleware(CorrelationIdMiddleware)
    configure_telemetry(app)

    app.include_router(health_router)
    app.include_router(research_router)

    return app
