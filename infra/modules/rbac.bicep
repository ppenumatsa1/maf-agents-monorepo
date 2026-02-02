@description('ACR resource id')
param acrId string

@description('Foundry account resource id')
param foundryId string

@description('Principal id to grant access')
param principalId string

var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var azureAiUserRoleId = '53ca6127-db72-4b80-b1b0-d745d6d5456d'

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: last(split(acrId, '/'))
  scope: resourceGroup()
}

resource foundry 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: last(split(foundryId, '/'))
  scope: resourceGroup()
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acrId, principalId, acrPullRoleId)
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

resource foundryAiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundryId, principalId, azureAiUserRoleId)
  scope: foundry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', azureAiUserRoleId)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}
