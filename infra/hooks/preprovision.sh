#!/usr/bin/env sh
set -e

ENV_NAME="${AZD_ENV_NAME:-dev}"
RAND_SUFFIX=$(date +%s | tail -c 6)

azd env set AZURE_LOCATION "eastus2"
azd env set AZURE_RESOURCE_GROUP "rg-${RAND_SUFFIX}-${ENV_NAME}"

echo "Set AZURE_LOCATION=eastus2"
echo "Set AZURE_RESOURCE_GROUP=rg-${RAND_SUFFIX}-${ENV_NAME}"
