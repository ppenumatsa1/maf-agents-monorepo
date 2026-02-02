from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.observability.telemetry import start_span
from app.domain.schemas.research import ResearchRequest, ResearchResponse
from app.domain.services.research_service import ResearchService

router = APIRouter(prefix="/v1")


@router.post("/research", response_model=ResearchResponse)
async def research(request: ResearchRequest) -> ResearchResponse:
    with start_span(
        "app.http.research",
        {
            "topic": request.topic,
            "has_constraints": bool(request.constraints),
            "stream": False,
        },
    ):
        service = ResearchService()
        result = await service.run(request)
        return result


@router.post("/research/stream")
async def research_stream(request: ResearchRequest) -> StreamingResponse:
    service = ResearchService()

    async def event_stream() -> AsyncGenerator[str, None]:
        with start_span(
            "app.http.research_stream",
            {
                "topic": request.topic,
                "has_constraints": bool(request.constraints),
                "stream": True,
            },
        ):
            async for chunk in service.stream(request):
                yield f"data: {chunk}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
