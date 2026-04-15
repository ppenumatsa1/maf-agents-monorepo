import json

import httpx
from agent_framework import tool

from app.core.observability.telemetry import emit_business_event, start_span


@tool(approval_mode="never_require")
def web_search(topic: str, max_results: int = 5) -> str:
    """Search DuckDuckGo Instant Answer API and return compact JSON payload."""
    with start_span(
        "app.tool.web_search",
        {"topic.length": len(topic or ""), "max_results": max_results},
    ):
        status_code = 0
        parse_success = False
        results: list[dict[str, str]] = []
        params = {
            "q": topic,
            "format": "json",
            "no_redirect": "1",
            "no_html": "1",
        }
        try:
            response = httpx.get("https://api.duckduckgo.com/", params=params, timeout=15.0)
            status_code = response.status_code
            response.raise_for_status()
            payload = response.json()
            parse_success = True

            for item in payload.get("RelatedTopics", []):
                if len(results) >= max_results:
                    break
                text = item.get("Text")
                first_url = item.get("FirstURL")
                if not text or not first_url:
                    continue
                results.append(
                    {
                        "title": text.split(" - ")[0][:120],
                        "url": first_url,
                        "source": "DuckDuckGo",
                        "snippet": text,
                    }
                )

            return json.dumps({"topic": topic, "results": results}, indent=2)
        finally:
            emit_business_event(
                "research.tool.web_search",
                {
                    "topic.length": len(topic or ""),
                    "topic": topic or "",
                    "max_results": max_results,
                    "results.count": len(results),
                    "results.payload": json.dumps(results),
                    "http.status_code": status_code,
                    "http.status_class": f"{status_code // 100}xx" if status_code else "unknown",
                    "parse.success": parse_success,
                },
            )
