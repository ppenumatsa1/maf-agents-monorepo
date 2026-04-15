#!/usr/bin/env bash
set -euo pipefail

echo "Pre-Provision Hook: Environment Setup"

ENV_NAME="${AZURE_ENV_NAME:-${AZD_ENV_NAME:-dev}}"
RAND_SUFFIX=$(date +%s | tail -c 6)
RESOURCE_GROUP="rg-${RAND_SUFFIX}-${ENV_NAME}"
APP_DISPLAY_NAME="01-researcher-agent-${ENV_NAME}-app"
ROLE_READ_ID="f97ba8de-72df-4f27-b78d-6f90e461ee8f"
ROLE_WRITE_ID="f367957b-fcc3-42dc-8494-1058e5f5c23e"

if ! command -v az >/dev/null 2>&1; then
	echo "Error: Azure CLI (az) is required." >&2
	exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
	echo "Error: jq is required." >&2
	exit 1
fi

azd env set AZURE_LOCATION "eastus2" --no-prompt
azd env set AZURE_RESOURCE_GROUP "$RESOURCE_GROUP" --no-prompt

TENANT_ID=$(az account show --query tenantId -o tsv)
if [[ -z "$TENANT_ID" ]]; then
	echo "Error: unable to resolve tenant id from current Azure context." >&2
	exit 1
fi

APP_OBJECT_ID=$(az ad app list --display-name "$APP_DISPLAY_NAME" --query "[0].id" -o tsv)
APP_ID=$(az ad app list --display-name "$APP_DISPLAY_NAME" --query "[0].appId" -o tsv)

if [[ -z "$APP_OBJECT_ID" || -z "$APP_ID" ]]; then
	APP_ID=$(az ad app create \
		--display-name "$APP_DISPLAY_NAME" \
		--sign-in-audience AzureADMyOrg \
		--query appId -o tsv)
	APP_OBJECT_ID=$(az ad app show --id "$APP_ID" --query id -o tsv)
	echo "Created Entra app registration: $APP_DISPLAY_NAME ($APP_ID)"
else
	echo "Reusing Entra app registration: $APP_DISPLAY_NAME ($APP_ID)"
fi

az ad app update --id "$APP_OBJECT_ID" --identifier-uris "api://$APP_ID"

APP_ROLES_FILE=$(mktemp)
cat > "$APP_ROLES_FILE" <<EOF
[
	{
		"allowedMemberTypes": ["Application"],
		"description": "Read access to researcher endpoints",
		"displayName": "Research.Read",
		"id": "$ROLE_READ_ID",
		"isEnabled": true,
		"origin": "Application",
		"value": "Research.Read"
	},
	{
		"allowedMemberTypes": ["Application"],
		"description": "Write access to researcher endpoints",
		"displayName": "Research.Write",
		"id": "$ROLE_WRITE_ID",
		"isEnabled": true,
		"origin": "Application",
		"value": "Research.Write"
	}
]
EOF
az ad app update --id "$APP_OBJECT_ID" --app-roles "@$APP_ROLES_FILE"
rm -f "$APP_ROLES_FILE"

SP_OBJECT_ID=$(az ad sp show --id "$APP_ID" --query id -o tsv 2>/dev/null || true)
if [[ -z "$SP_OBJECT_ID" ]]; then
	az ad sp create --id "$APP_ID" >/dev/null
	SP_OBJECT_ID=$(az ad sp show --id "$APP_ID" --query id -o tsv)
	echo "Created service principal for app: $APP_ID"
fi

for ROLE_ID in "$ROLE_READ_ID" "$ROLE_WRITE_ID"; do
	HAS_ASSIGNMENT=$(az rest \
		--method GET \
		--url "https://graph.microsoft.com/v1.0/servicePrincipals/${SP_OBJECT_ID}/appRoleAssignments?\$filter=resourceId eq ${SP_OBJECT_ID}" \
		--query "value[?appRoleId=='$ROLE_ID'] | length(@)" \
		-o tsv)

	if [[ "$HAS_ASSIGNMENT" == "0" ]]; then
		az rest \
			--method POST \
			--url "https://graph.microsoft.com/v1.0/servicePrincipals/${SP_OBJECT_ID}/appRoleAssignments" \
			--headers "Content-Type=application/json" \
			--body "{\"principalId\":\"${SP_OBJECT_ID}\",\"resourceId\":\"${SP_OBJECT_ID}\",\"appRoleId\":\"${ROLE_ID}\"}" \
			>/dev/null
		if [[ "$ROLE_ID" == "$ROLE_READ_ID" ]]; then
			echo "Assigned Research.Read role to service principal."
		else
			echo "Assigned Research.Write role to service principal."
		fi
	fi
done

SECRET_JSON=$(az ad app credential reset --id "$APP_ID" --display-name "azd-${ENV_NAME}" --append -o json)
CLIENT_SECRET=$(echo "$SECRET_JSON" | jq -r '.password')
if [[ -z "$CLIENT_SECRET" || "$CLIENT_SECRET" == "null" ]]; then
	echo "Error: failed to create client secret for app registration." >&2
	exit 1
fi

ENTRA_AUDIENCE="api://$APP_ID"
ENTRA_AUTHORITY="https://login.microsoftonline.com/${TENANT_ID}"
ENTRA_ISSUER="https://sts.windows.net/${TENANT_ID}/"
ENTRA_JWKS_URL="${ENTRA_AUTHORITY}/discovery/v2.0/keys"

azd env set ENTRA_AUTHORITY "$ENTRA_AUTHORITY" --no-prompt
azd env set ENTRA_TENANT_ID "$TENANT_ID" --no-prompt
azd env set ENTRA_CLIENT_ID "$APP_ID" --no-prompt
azd env set ENTRA_CLIENT_SECRET "$CLIENT_SECRET" --no-prompt
azd env set ENTRA_AUDIENCE "$ENTRA_AUDIENCE" --no-prompt
azd env set ENTRA_API_AUDIENCE "$ENTRA_AUDIENCE" --no-prompt
azd env set ENTRA_SCOPE "${ENTRA_AUDIENCE}/.default" --no-prompt
azd env set ENTRA_ISSUER "$ENTRA_ISSUER" --no-prompt
azd env set ENTRA_JWKS_URL "$ENTRA_JWKS_URL" --no-prompt
azd env set ENTRA_JWKS_CACHE_TTL_SECONDS "${ENTRA_JWKS_CACHE_TTL_SECONDS:-300}" --no-prompt
azd env set REQUIRE_AUTH "${REQUIRE_AUTH:-true}" --no-prompt

echo "Set AZURE_LOCATION=eastus2"
echo "Set AZURE_RESOURCE_GROUP=${RESOURCE_GROUP}"
echo "Set ENTRA_* auth environment values for ${APP_DISPLAY_NAME}"
