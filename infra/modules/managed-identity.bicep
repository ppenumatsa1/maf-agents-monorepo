@description('User-assigned managed identity name')
param name string

@description('Location')
param location string

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: name
  location: location
}

output principalId string = identity.properties.principalId
output resourceId string = identity.id
output clientId string = identity.properties.clientId
