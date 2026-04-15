@description('Container App name')
param name string

@description('Location')
param location string

@description('Container Apps environment id')
param environmentId string

@description('Ingress target port')
param targetPort int

@description('Container image')
param image string

@description('ACR login server')
param registryServer string

@description('Managed identity resource id')
param managedIdentityId string

@description('Managed identity client id')
param managedIdentityClientId string

@description('Application Insights connection string')
@secure()
param appInsightsConnectionString string

@description('Azure AI Foundry projects endpoint')
param foundryProjectsEndpoint string

@description('Azure AI Foundry model deployment name')
param foundryModelDeploymentName string

@description('Enable auth middleware in the app')
param requireAuth string

@description('Microsoft Entra tenant ID')
param entraTenantId string

@description('Microsoft Entra client/application ID')
param entraClientId string

@description('Expected audience claim')
param entraAudience string

@description('Token authority URL')
param entraAuthority string

@description('Token issuer URL')
param entraIssuer string

@description('JWKS endpoint URL')
param entraJwksUrl string

@description('JWKS cache TTL in seconds')
param entraJwksCacheTtlSeconds int

resource app 'Microsoft.App/containerApps@2023-05-01' = {
  name: name
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    environmentId: environmentId
    configuration: {
      ingress: {
        external: true
        targetPort: targetPort
        transport: 'auto'
      }
      registries: [
        {
          server: registryServer
          identity: managedIdentityId
        }
      ]
      activeRevisionsMode: 'Single'
    }
    template: {
      containers: [
        {
          name: name
          image: image
          env: [
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsightsConnectionString
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: managedIdentityClientId
            }
            {
              name: 'FOUNDRY_PROJECTS_ENDPOINT'
              value: foundryProjectsEndpoint
            }
            {
              name: 'FOUNDRY_MODEL_DEPLOYMENT_NAME'
              value: foundryModelDeploymentName
            }
            {
              name: 'REQUIRE_AUTH'
              value: requireAuth
            }
            {
              name: 'ENTRA_TENANT_ID'
              value: entraTenantId
            }
            {
              name: 'ENTRA_CLIENT_ID'
              value: entraClientId
            }
            {
              name: 'ENTRA_AUDIENCE'
              value: entraAudience
            }
            {
              name: 'ENTRA_AUTHORITY'
              value: entraAuthority
            }
            {
              name: 'ENTRA_ISSUER'
              value: entraIssuer
            }
            {
              name: 'ENTRA_JWKS_URL'
              value: entraJwksUrl
            }
            {
              name: 'ENTRA_JWKS_CACHE_TTL_SECONDS'
              value: '${entraJwksCacheTtlSeconds}'
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
}

output fqdn string = app.properties.configuration.ingress.fqdn
