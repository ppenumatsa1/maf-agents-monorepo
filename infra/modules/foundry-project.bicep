@description('Location for all resources')
param location string

@description('Tags applied to all resources')
param tags object

@description('Azure AI Foundry account name')
param accountName string

@description('Azure AI Foundry project name')
param projectName string

@description('Project display name')
param displayName string

@description('Project description')
param projectDescription string

resource account 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: accountName
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  name: projectName
  parent: account
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  tags: tags
  properties: {
    displayName: displayName
    description: projectDescription
  }
}

output projectId string = project.id
output projectName string = project.name
output projectPrincipalId string = project.identity.principalId
