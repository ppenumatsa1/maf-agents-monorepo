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
