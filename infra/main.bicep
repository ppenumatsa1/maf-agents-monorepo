@description('Location for all resources')
param location string = resourceGroup().location

@description('Environment name prefix')
param envName string

@description('Tags applied to all resources')
param tags object

@description('Container app name')
param containerAppName string

@description('Container image for the agent (used during provision)')
param containerImage string

@description('Container ingress target port')
param containerTargetPort int

@description('Azure AI Foundry account SKU name')
param foundryAccountSkuName string

@description('Azure AI Foundry project display name')
param foundryProjectDisplayName string

@description('Azure AI Foundry project description')
param foundryProjectDescription string

type ModelDeployment = {
  @description('Deployment name')
  name: string

  @description('Model name')
  modelName: string

  @description('Model version (leave empty to use default)')
  modelVersion: string

  @description('Model publisher format')
  modelPublisherFormat: string

  @description('SKU name for the deployment')
  skuName: string

  @description('Capacity for the deployment')
  capacity: int
}

@description('Azure AI Foundry model deployments')
param modelDeployments ModelDeployment[]

var resourceToken = toLower(uniqueString(resourceGroup().id, envName))
var namePrefix = 'maf${resourceToken}'
var logAnalyticsName = '${namePrefix}-law'
var appInsightsName = '${namePrefix}-appi'
var acaEnvName = '${namePrefix}-aca'
var acrName = '${namePrefix}acr'
var foundryAccountName = '${namePrefix}-foundry'
var foundryProjectName = '${namePrefix}-project'

var primaryDeployment = length(modelDeployments) > 0 ? modelDeployments[0] : {
  name: ''
  modelName: ''
  modelVersion: ''
  modelPublisherFormat: ''
  skuName: ''
  capacity: 0
}

module logAnalytics 'modules/log-analytics.bicep' = {
  params: {
    name: logAnalyticsName
    location: location
    tags: tags
  }
}

module appInsights 'modules/app-insights.bicep' = {
  params: {
    name: appInsightsName
    location: location
    workspaceId: logAnalytics.outputs.workspaceId
    tags: tags
  }
}

module acr 'modules/acr.bicep' = {
  params: {
    name: acrName
    location: location
  }
}

module identity 'modules/managed-identity.bicep' = {
  params: {
    name: '${envName}-mi'
    location: location
  }
}

module foundryResource 'modules/foundry-resource.bicep' = {
  params: {
    name: foundryAccountName
    location: location
    skuName: foundryAccountSkuName
    tags: tags
  }
}

module foundryProject 'modules/foundry-project.bicep' = {
  params: {
    accountName: foundryAccountName
    projectName: foundryProjectName
    location: location
    displayName: foundryProjectDisplayName
    projectDescription: foundryProjectDescription
    tags: tags
  }
  dependsOn: [
    foundryResource
  ]
}

module foundryModels 'modules/foundry-models.bicep' = {
  params: {
    foundryName: foundryResource.outputs.accountName
    deployments: modelDeployments
  }
  dependsOn: [
    foundryProject
  ]
}

module acrRbac 'modules/rbac.bicep' = {
  params: {
    acrId: acr.outputs.acrId
    foundryId: foundryResource.outputs.accountId
    principalId: identity.outputs.principalId
  }
}

module acaEnv 'modules/aca-env.bicep' = {
  params: {
    name: acaEnvName
    location: location
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
  }
}

module containerApp 'modules/container-app.bicep' = {
  params: {
    name: containerAppName
    location: location
    environmentId: acaEnv.outputs.environmentId
    targetPort: containerTargetPort
    image: containerImage
    registryServer: acr.outputs.loginServer
    managedIdentityId: identity.outputs.resourceId
    managedIdentityClientId: identity.outputs.clientId
    appInsightsConnectionString: appInsights.outputs.connectionString
    foundryProjectsEndpoint: 'https://${foundryResource.outputs.accountName}.services.ai.azure.com/api/projects/${foundryProject.outputs.projectName}'
    foundryModelDeploymentName: primaryDeployment.name
  }
  dependsOn: [
    acrRbac
  ]
}

output acrLoginServer string = acr.outputs.loginServer
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = acr.outputs.loginServer
output containerAppFqdn string = containerApp.outputs.fqdn
@secure()
output appInsightsConnectionString string = appInsights.outputs.connectionString
output foundryAccountId string = foundryResource.outputs.accountId
output foundryProjectId string = foundryProject.outputs.projectId
output foundryModelDeploymentNames string[] = foundryModels.outputs.deploymentNames
output FOUNDRY_PROJECTS_ENDPOINT string = 'https://${foundryResource.outputs.accountName}.services.ai.azure.com/api/projects/${foundryProject.outputs.projectName}'
output FOUNDRY_PROJECT_RESOURCE_ID string = foundryProject.outputs.projectId
output FOUNDRY_MODEL_DEPLOYMENT_NAME string = primaryDeployment.name
