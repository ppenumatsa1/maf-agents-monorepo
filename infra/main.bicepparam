using './main.bicep'

param location = 'eastus2'

param envName = 'maf-agents'

param tags = {
  environment: envName
  managedBy: 'azd'
  region: location
  SecurityControl: 'Ignore'
}

param containerAppName = 'researcher-agent'
param containerImage = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
param containerTargetPort = 8000

param foundryAccountSkuName = 'S0'
param foundryProjectDisplayName = 'MAF Agents'
param foundryProjectDescription = 'AI Foundry project for MAF agents.'

param modelDeployments = [
  {
    name: 'gpt-4.1-mini'
    modelName: 'gpt-4.1-mini'
    modelVersion: ''
    modelPublisherFormat: 'OpenAI'
    skuName: 'GlobalStandard'
    capacity: 200
  }
  {
    name: 'gpt-5'
    modelName: 'gpt-5'
    modelVersion: '2025-08-07'
    modelPublisherFormat: 'OpenAI'
    skuName: 'GlobalStandard'
    capacity: 100
  }
  {
    name: 'text-embed-3-large'
    modelName: 'text-embedding-3-large'
    modelVersion: ''
    modelPublisherFormat: 'OpenAI'
    skuName: 'GlobalStandard'
    capacity: 100
  }
]
