import os

import httpx
import pytest

TOPICS = ["AI safety", "Battery tech", "Quantum computing"]


def _auth_headers() -> dict[str, str]:
    token = os.getenv("SMOKE_BEARER_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


@pytest.mark.skipif(not os.getenv("SMOKE_BASE_URL"), reason="SMOKE_BASE_URL not set")
def test_live_health() -> None:
    base_url = os.environ["SMOKE_BASE_URL"].rstrip("/")
    response = httpx.get(f"{base_url}/health", timeout=10)
    assert response.status_code == 200


@pytest.mark.skipif(not os.getenv("SMOKE_BASE_URL"), reason="SMOKE_BASE_URL not set")
@pytest.mark.parametrize("topic", TOPICS)
def test_live_research(topic: str) -> None:
    base_url = os.environ["SMOKE_BASE_URL"].rstrip("/")
    response = httpx.post(
        f"{base_url}/v1/research",
        json={"topic": topic},
        headers=_auth_headers(),
        timeout=90,
    )
    assert response.status_code == 200
    body = response.json()
    assert "summary" in body


@pytest.mark.skipif(not os.getenv("SMOKE_BASE_URL"), reason="SMOKE_BASE_URL not set")
@pytest.mark.parametrize("topic", TOPICS)
def test_live_research_stream(topic: str) -> None:
    base_url = os.environ["SMOKE_BASE_URL"].rstrip("/")
    with httpx.stream(
        "POST",
        f"{base_url}/v1/research/stream",
        json={"topic": topic},
        headers=_auth_headers(),
        timeout=90,
    ) as response:
        assert response.status_code == 200
        saw_event = False
        for chunk in response.iter_text():
            if "data:" in chunk:
                saw_event = True
                break
        assert saw_event
