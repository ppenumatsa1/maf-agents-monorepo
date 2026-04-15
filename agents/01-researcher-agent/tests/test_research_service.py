from __future__ import annotations

import asyncio
import sys
import types

import pytest

from app.api.v1.schemas.research import ResearchRequest, ResearchResponse
from app.modules.research.service import ResearchService


class _WorkflowStub:
    def __init__(self) -> None:
        self.last_request = None

    async def run(self, request: ResearchRequest) -> dict[str, str]:
        self.last_request = request
        return {"summary": "sum", "draft": "draft", "review": "review"}

    async def stream(self, request: ResearchRequest):
        self.last_request = request
        for chunk in ["a", "b"]:
            yield chunk


class _FailingWorkflowStub(_WorkflowStub):
    async def run(self, _request: ResearchRequest) -> dict[str, str]:
        raise RuntimeError("run failed")


def test_research_service_run_uses_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    workflow = _WorkflowStub()
    monkeypatch.setitem(
        sys.modules,
        "app.maf",
        types.SimpleNamespace(ResearchWorkflow=lambda: workflow),
    )

    service = ResearchService()
    request = ResearchRequest(topic="AI")

    result = asyncio.run(service.run(request))

    assert isinstance(result, ResearchResponse)
    assert result.summary == "sum"
    assert workflow.last_request == request


def test_research_service_stream_uses_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    workflow = _WorkflowStub()
    monkeypatch.setitem(
        sys.modules,
        "app.maf",
        types.SimpleNamespace(ResearchWorkflow=lambda: workflow),
    )

    async def scenario() -> list[str]:
        service = ResearchService()
        request = ResearchRequest(topic="AI")
        output = []
        async for chunk in service.stream(request):
            output.append(chunk)
        assert workflow.last_request == request
        return output

    chunks = asyncio.run(scenario())

    assert chunks == ["a", "b"]


def test_research_service_run_propagates_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        sys.modules,
        "app.maf",
        types.SimpleNamespace(ResearchWorkflow=_FailingWorkflowStub),
    )

    async def scenario() -> None:
        service = ResearchService()
        await service.run(ResearchRequest(topic="AI"))

    with pytest.raises(RuntimeError, match="run failed"):
        asyncio.run(scenario())
