type ModelDeployment = {
  @description('Deployment name')
  name: string

  @description('Model name')
  modelName: string

  @description('Model version (leave empty to use default)')
  modelVersion: string

  @description('Model provider format')
  modelPublisherFormat: string

  @description('SKU name for the deployment')
  skuName: string

  @description('Capacity for the deployment')
  capacity: int
}

@description('Azure AI Foundry account name')
param foundryName string

@description('Model deployments')
param deployments ModelDeployment[]

resource foundry 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: foundryName
}

@batchSize(1)
resource modelDeployments 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = [for deployment in deployments: {
  name: deployment.name
  parent: foundry
  sku: {
    name: deployment.skuName
    capacity: deployment.capacity
  }
  properties: {
    model: deployment.modelVersion != '' ? {
      format: deployment.modelPublisherFormat
      name: deployment.modelName
      version: deployment.modelVersion
    } : {
      format: deployment.modelPublisherFormat
      name: deployment.modelName
    }
  }
}]

output deploymentNames string[] = [for deployment in deployments: deployment.name]
