import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MAFConfig:
    provider: str
    model: str
    foundry_projects_endpoint: str | None
    foundry_model_deployment_name: str | None

    @staticmethod
    def from_env() -> "MAFConfig":
        provider = os.getenv("MAF_PROVIDER", "foundry").lower()
        if provider not in {"azure", "azure_openai", "foundry", "azure_ai"}:
            provider = "foundry"
        model = os.getenv("MAF_MODEL", "gpt-4o-mini")

        return MAFConfig(
            provider=provider,
            model=model,
            foundry_projects_endpoint=os.getenv("FOUNDRY_PROJECTS_ENDPOINT"),
            foundry_model_deployment_name=os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME"),
        )
