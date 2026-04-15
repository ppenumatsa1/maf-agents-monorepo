import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.v1.schemas.research import ResearchRequest, ResearchResponse
from app.core.observability.telemetry import (
    now_ms,
    record_research_completed,
    record_research_failed,
    record_research_started,
    start_span,
)
from app.core.security.dependencies import require_roles
from app.modules.research import ResearchService

router = APIRouter(prefix="/v1")


@router.post(
    "/research",
    response_model=ResearchResponse,
    dependencies=[Depends(require_roles("Research.Read"))],
)
async def research(request: ResearchRequest) -> ResearchResponse:
    attributes = {
        "topic.length": len(request.topic or ""),
        "has_constraints": bool(request.constraints),
        "stream": False,
    }
    started_ms = now_ms()
    record_research_started(attributes)
    with start_span(
        "app.http.research",
        attributes,
    ):
        service = ResearchService()
        try:
            result = await service.run(request)
            summary = (
                result.get("summary", "")
                if isinstance(result, dict)
                else getattr(result, "summary", "")
            )
            record_research_completed(
                duration_ms=now_ms() - started_ms,
                attributes={**attributes, "summary.length": len(summary)},
            )
            return result
        except Exception as exc:
            record_research_failed(reason=type(exc).__name__, attributes=attributes)
            raise


@router.post("/research/stream", dependencies=[Depends(require_roles("Research.Write"))])
async def research_stream(request: ResearchRequest) -> StreamingResponse:
    service = ResearchService()
    attributes = {
        "topic.length": len(request.topic or ""),
        "has_constraints": bool(request.constraints),
        "stream": True,
    }
    started_ms = now_ms()
    record_research_started(attributes)

    async def event_stream() -> AsyncGenerator[str, None]:
        with start_span(
            "app.http.research_stream",
            attributes,
        ):
            completed = False
            try:
                async for chunk in service.stream(request):
                    if isinstance(chunk, dict):
                        event_name = chunk.get("event", "update")
                        payload = {k: v for k, v in chunk.items() if k != "event"}
                        yield f"event: {event_name}\\ndata: {json.dumps(payload)}\\n\\n"
                    else:
                        yield f"data: {chunk}\\n\\n"
                completed = True
            except Exception as exc:
                record_research_failed(reason=type(exc).__name__, attributes=attributes)
                raise
            finally:
                if completed:
                    record_research_completed(
                        duration_ms=now_ms() - started_ms,
                        attributes=attributes,
                    )

    return StreamingResponse(event_stream(), media_type="text/event-stream")
