from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from fastapi.testclient import TestClient

from app.core.security.models import Principal
from app.main import create_app


class _FakeResearchService:
    async def run(self, _request):
        return {"summary": "ok", "draft": "d", "review": "r"}

    async def stream(self, _request) -> AsyncGenerator[str, None]:
        for chunk in ["phase-1", "phase-2"]:
            yield chunk


class _FailingResearchService:
    async def run(self, _request):
        raise RuntimeError("boom")

    async def stream(self, _request) -> AsyncGenerator[str, None]:
        if False:
            yield ""


class _StructuredStreamResearchService:
    async def run(self, _request):
        return {"summary": "ok", "draft": "d", "review": "r"}

    async def stream(self, _request) -> AsyncGenerator[dict[str, str], None]:
        yield {"event": "executor_invoked", "executor": "ResearcherAgent"}
        yield {"event": "output", "executor": "ResearcherAgent", "text": "hello"}
        yield {"event": "executor_completed", "executor": "ResearcherAgent"}


def _client_with_overrides(monkeypatch: pytest.MonkeyPatch, service_class):
    import app.api.v1.routers.research as research_router

    monkeypatch.setattr(research_router, "ResearchService", service_class)
    return TestClient(create_app())


def test_routes_are_open_when_auth_disabled(set_auth_env, monkeypatch: pytest.MonkeyPatch) -> None:
    set_auth_env(False)
    client = _client_with_overrides(monkeypatch, _FakeResearchService)

    run_response = client.post("/v1/research", json={"topic": "test"})
    assert run_response.status_code == 200
    assert run_response.json() == {"summary": "ok", "draft": "d", "review": "r"}

    with client.stream("POST", "/v1/research/stream", json={"topic": "test"}) as stream_response:
        assert stream_response.status_code == 200
        chunks = "".join(stream_response.iter_text())

    assert "data: phase-1" in chunks
    assert "data: phase-2" in chunks


def test_routes_require_bearer_token_when_auth_enabled(
    set_auth_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_auth_env(True)
    client = _client_with_overrides(monkeypatch, _FakeResearchService)

    run_response = client.post("/v1/research", json={"topic": "test"})
    stream_response = client.post("/v1/research/stream", json={"topic": "test"})

    assert run_response.status_code == 401
    assert stream_response.status_code == 401


def test_research_route_requires_research_read_role(
    set_auth_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_auth_env(True)
    from app.core.security.dependencies import get_current_principal

    app = create_app()
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        authenticated=True,
        client_id="client-id",
        roles={"Research.Write"},
    )

    import app.api.v1.routers.research as research_router

    monkeypatch.setattr(research_router, "ResearchService", _FakeResearchService)
    client = TestClient(app)

    response = client.post("/v1/research", json={"topic": "test"})

    assert response.status_code == 403
    assert "Research.Read" in response.json()["detail"]


def test_research_stream_route_requires_research_write_role(
    set_auth_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_auth_env(True)
    from app.core.security.dependencies import get_current_principal

    app = create_app()
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        authenticated=True,
        client_id="client-id",
        roles={"Research.Read"},
    )

    import app.api.v1.routers.research as research_router

    monkeypatch.setattr(research_router, "ResearchService", _FakeResearchService)
    client = TestClient(app)

    response = client.post("/v1/research/stream", json={"topic": "test"})

    assert response.status_code == 403
    assert "Research.Write" in response.json()["detail"]


def test_research_route_returns_500_on_service_failure(
    set_auth_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_auth_env(False)

    import app.api.v1.routers.research as research_router

    monkeypatch.setattr(research_router, "ResearchService", _FailingResearchService)

    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.post("/v1/research", json={"topic": "test"})

    assert response.status_code == 500


def test_research_routes_validate_payload(set_auth_env, monkeypatch: pytest.MonkeyPatch) -> None:
    set_auth_env(False)
    client = _client_with_overrides(monkeypatch, _FakeResearchService)

    response = client.post("/v1/research", json={"constraints": "missing topic"})

    assert response.status_code == 422


def test_stream_route_formats_structured_sse_events(
    set_auth_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_auth_env(False)
    client = _client_with_overrides(monkeypatch, _StructuredStreamResearchService)

    with client.stream("POST", "/v1/research/stream", json={"topic": "test"}) as stream_response:
        assert stream_response.status_code == 200
        chunks = "".join(stream_response.iter_text())

    assert "event: executor_invoked" in chunks
    assert 'data: {"executor": "ResearcherAgent"}' in chunks
    assert "event: output" in chunks
    assert 'data: {"executor": "ResearcherAgent", "text": "hello"}' in chunks
