// Web PubSub (ADR-0007): Free_F1 for development, Standard_S1 for the judging period.
param location string
param tags object
param name string
@allowed(['Free_F1', 'Standard_S1'])
param sku string
@description('Who gets Web PubSub Service Owner: [{ id, type }].')
param principals array

var serviceOwner = '12cf5a90-567b-43ae-8102-96cf46c7d9b4'

resource pubsub 'Microsoft.SignalRService/webPubSub@2024-03-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: sku
    tier: sku == 'Free_F1' ? 'Free' : 'Standard'
    capacity: 1
  }
  properties: {
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource roles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for p in principals: {
  name: guid(pubsub.id, p.id, serviceOwner)
  scope: pubsub
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', serviceOwner)
    principalId: p.id
    principalType: p.type
  }
}]

output endpoint string = 'https://${pubsub.properties.hostName}'
