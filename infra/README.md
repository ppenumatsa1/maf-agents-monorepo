# Infra

Bicep templates and azd hooks for provisioning Azure Container Apps, Azure AI Foundry, ACR,
Log Analytics, and Application Insights. Key Vault is intentionally excluded for Phase 2.

## Files

- main.bicep: Primary infrastructure template
- main.bicepparam: Default parameters for local azd environments
- modules/: Reusable Bicep modules
- hooks/: azd lifecycle hooks (preprovision, postprovision, predeploy)

## Notes

- preprovision.sh sets the location and a unique resource group name.
- postprovision.sh writes FOUNDRY\_\* values into the agent .env file.
- predeploy.sh builds and pushes the container image, then updates azd env vars.
