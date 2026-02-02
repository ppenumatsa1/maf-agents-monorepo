from agent_framework import tool

from app.core.observability.telemetry import start_span


@tool(approval_mode="never_require")
def extract_key_points(text: str) -> str:
    """Extract key points from a text input."""
    with start_span("app.tool.extract_key_points", {"text.length": len(text or "")}):
        if not text:
            return "No content provided."
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        bullets = lines[:5]
        return "\n".join(f"- {line}" for line in bullets) or "No key points found."


@tool(approval_mode="never_require")
def build_outline(topic: str) -> str:
    """Generate a lightweight outline for the topic."""
    with start_span("app.tool.build_outline", {"topic.length": len(topic or "")}):
        return (
            f"Outline for {topic}:\n"
            "1. Background\n"
            "2. Key Findings\n"
            "3. Implications\n"
            "4. Recommendations"
        )


@tool(approval_mode="never_require")
def review_draft(draft: str) -> str:
    """Provide quick review notes for a draft."""
    with start_span("app.tool.review_draft", {"draft.length": len(draft or "")}):
        if not draft:
            return "No draft provided for review."
        return "Review: check clarity, evidence, and missing caveats."
