from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    topic: str = Field(..., description="Research topic")
    context: str | None = Field(None, description="Optional context")
    constraints: str | None = Field(None, description="Optional constraints")


class ResearchResponse(BaseModel):
    summary: str
    draft: str
    review: str
