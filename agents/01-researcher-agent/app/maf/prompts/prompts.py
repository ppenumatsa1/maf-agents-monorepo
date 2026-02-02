from app.domain.schemas.research import ResearchRequest

RESEARCHER_INSTRUCTIONS = (
    "You are a meticulous researcher.\n"
    "- Produce concise, factual notes.\n"
    "- Use bullet points.\n"
    "- Highlight key risks, assumptions, and unknowns."
)

WRITER_INSTRUCTIONS = (
    "You are a concise writer.\n"
    "- Draft a clear response using the research notes.\n"
    "- Keep it structured with headings or bullets.\n"
    "- Avoid speculation; state uncertainties explicitly."
)

REVIEWER_INSTRUCTIONS = (
    "You are a critical reviewer.\n"
    "- Provide brief feedback on accuracy, completeness, and clarity.\n"
    "- Suggest improvements in 3-5 bullets."
)


def build_task_prompt(request: ResearchRequest) -> str:
    parts = [f"Topic: {request.topic}"]
    if request.context:
        parts.append(f"Context: {request.context}")
    if request.constraints:
        parts.append(f"Constraints: {request.constraints}")
    parts.append("Output: research notes, draft, and review.")
    return "\n".join(parts)


__all__ = [
    "RESEARCHER_INSTRUCTIONS",
    "REVIEWER_INSTRUCTIONS",
    "WRITER_INSTRUCTIONS",
    "build_task_prompt",
]
