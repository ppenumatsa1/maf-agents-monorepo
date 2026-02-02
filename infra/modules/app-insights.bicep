@description('App Insights name')
param name string

@description('Location')
param location string

@description('Log Analytics workspace id')
param workspaceId string

@description('Tags applied to Application Insights')
param tags object

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: name
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspaceId
  }
}

@secure()
output connectionString string = appInsights.properties.ConnectionString
