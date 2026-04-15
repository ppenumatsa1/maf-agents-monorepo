#!/usr/bin/env bash
set -euo pipefail

echo "Pre-Provision Hook: Environment Setup"

ENV_NAME="${AZURE_ENV_NAME:-${AZD_ENV_NAME:-dev}}"
RAND_SUFFIX=$(date +%s | tail -c 6)
RESOURCE_GROUP="rg-${RAND_SUFFIX}-${ENV_NAME}"
API_APP_DISPLAY_NAME="01-researcher-agent-${ENV_NAME}-api"
CLIENT_APP_DISPLAY_NAME="01-researcher-agent-${ENV_NAME}-client"
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

ensure_sp() {
	local app_id="$1"
	local sp_object_id

	sp_object_id=$(az ad sp show --id "$app_id" --query id -o tsv 2>/dev/null || true)
	if [[ -z "$sp_object_id" ]]; then
		az ad sp create --id "$app_id" >/dev/null
		sp_object_id=$(az ad sp show --id "$app_id" --query id -o tsv)
	fi

	echo "$sp_object_id"
}

assign_app_role_if_missing() {
	local client_sp_object_id="$1"
	local api_sp_object_id="$2"
	local role_id="$3"

	local existing
	existing=$(az rest \
		--method GET \
		--url "https://graph.microsoft.com/v1.0/servicePrincipals/${client_sp_object_id}/appRoleAssignments" \
		--query "value[?resourceId=='${api_sp_object_id}' && appRoleId=='${role_id}'] | length(@)" \
		-o tsv)

	if [[ "$existing" == "0" ]]; then
		az rest \
			--method POST \
			--url "https://graph.microsoft.com/v1.0/servicePrincipals/${client_sp_object_id}/appRoleAssignments" \
			--headers "Content-Type=application/json" \
			--body "{\"principalId\":\"${client_sp_object_id}\",\"resourceId\":\"${api_sp_object_id}\",\"appRoleId\":\"${role_id}\"}" \
			>/dev/null
	fi
}

API_APP_RAW=$(az ad app list --display-name "$API_APP_DISPLAY_NAME" --query "[0]" -o json)
API_APP_ID=$(echo "$API_APP_RAW" | jq -r '.appId // empty')
API_APP_OBJECT_ID=$(echo "$API_APP_RAW" | jq -r '.id // empty')

if [[ -z "$API_APP_OBJECT_ID" || -z "$API_APP_ID" ]]; then
	API_APP_ID=$(az ad app create \
		--display-name "$API_APP_DISPLAY_NAME" \
		--sign-in-audience AzureADMyOrg \
		--query appId -o tsv)
	API_APP_OBJECT_ID=$(az ad app show --id "$API_APP_ID" --query id -o tsv)
	echo "Created API app registration: $API_APP_DISPLAY_NAME ($API_APP_ID)"
else
	echo "Reusing API app registration: $API_APP_ID"
fi

CLIENT_APP_RAW=$(az ad app list --display-name "$CLIENT_APP_DISPLAY_NAME" --query "[0]" -o json)
CLIENT_APP_ID=$(echo "$CLIENT_APP_RAW" | jq -r '.appId // empty')

if [[ -z "$CLIENT_APP_ID" ]]; then
	CLIENT_APP_ID=$(az ad app create \
		--display-name "$CLIENT_APP_DISPLAY_NAME" \
		--sign-in-audience AzureADMyOrg \
		--query appId -o tsv)
	echo "Created client app registration: $CLIENT_APP_DISPLAY_NAME ($CLIENT_APP_ID)"
else
	echo "Reusing client app registration: $CLIENT_APP_ID"
fi

API_AUDIENCE="api://${API_APP_ID}"
az ad app update --id "$API_APP_OBJECT_ID" --identifier-uris "$API_AUDIENCE"

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
az ad app update --id "$API_APP_OBJECT_ID" --app-roles "@$APP_ROLES_FILE"
rm -f "$APP_ROLES_FILE"

API_SP_OBJECT_ID=$(ensure_sp "$API_APP_ID")
CLIENT_SP_OBJECT_ID=$(ensure_sp "$CLIENT_APP_ID")

assign_app_role_if_missing "$CLIENT_SP_OBJECT_ID" "$API_SP_OBJECT_ID" "$ROLE_READ_ID"
assign_app_role_if_missing "$CLIENT_SP_OBJECT_ID" "$API_SP_OBJECT_ID" "$ROLE_WRITE_ID"

echo "Assigned Research.Read/Research.Write app roles from API app to client service principal."

# Rotate to a single active secret for client app per provision run.
SECRET_JSON=$(az ad app credential reset --id "$CLIENT_APP_ID" --display-name "azd-${ENV_NAME}" -o json)
CLIENT_SECRET=$(echo "$SECRET_JSON" | jq -r '.password')
if [[ -z "$CLIENT_SECRET" || "$CLIENT_SECRET" == "null" ]]; then
	echo "Error: failed to create client secret for app registration." >&2
	exit 1
fi
echo "Replaced client secret for Entra client app: $CLIENT_APP_DISPLAY_NAME"

ENTRA_AUTHORITY="https://login.microsoftonline.com/${TENANT_ID}"
ENTRA_ISSUER="https://sts.windows.net/${TENANT_ID}/"
ENTRA_JWKS_URL="${ENTRA_AUTHORITY}/discovery/v2.0/keys"

azd env set ENTRA_AUTHORITY "$ENTRA_AUTHORITY" --no-prompt
azd env set ENTRA_TENANT_ID "$TENANT_ID" --no-prompt
azd env set ENTRA_CLIENT_ID "$CLIENT_APP_ID" --no-prompt
azd env set ENTRA_CLIENT_SECRET "$CLIENT_SECRET" --no-prompt
azd env set ENTRA_AUDIENCE "$API_AUDIENCE" --no-prompt
azd env set ENTRA_API_AUDIENCE "$API_AUDIENCE" --no-prompt
azd env set ENTRA_SCOPE "${API_AUDIENCE}/.default" --no-prompt
azd env set ENTRA_API_APP_ID "$API_APP_ID" --no-prompt
azd env set ENTRA_CLIENT_APP_ID "$CLIENT_APP_ID" --no-prompt
azd env set ENTRA_ISSUER "$ENTRA_ISSUER" --no-prompt
azd env set ENTRA_JWKS_URL "$ENTRA_JWKS_URL" --no-prompt
azd env set ENTRA_JWKS_CACHE_TTL_SECONDS "${ENTRA_JWKS_CACHE_TTL_SECONDS:-300}" --no-prompt
azd env set REQUIRE_AUTH "${REQUIRE_AUTH:-true}" --no-prompt

echo "Set AZURE_LOCATION=eastus2"
echo "Set AZURE_RESOURCE_GROUP=${RESOURCE_GROUP}"
echo "Set ENTRA_* auth environment values for API app ${API_APP_ID} and client app ${CLIENT_APP_ID}"
