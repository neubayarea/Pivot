// Service Bus (Standard) with the Judge's work queue. Local (key) auth is off.
param location string
param tags object
param name string
param queueName string
@description('Who gets Azure Service Bus Data Owner: [{ id, type }].')
param principals array

var dataOwner = '090c5cfd-751d-490a-894a-3ce6f1109419'

resource namespace 'Microsoft.ServiceBus/namespaces@2021-11-01' = {
  name: name
  location: location
  tags: tags
  sku: { name: 'Standard', tier: 'Standard' }
  properties: {
    disableLocalAuth: true
    minimumTlsVersion: '1.2'
  }
}

// Message ids are "{match_id}:{minute}" (pivot_core.ports), so duplicate detection drops repeats.
resource queue 'Microsoft.ServiceBus/namespaces/queues@2021-11-01' = {
  parent: namespace
  name: queueName
  properties: {
    lockDuration: 'PT1M'
    maxDeliveryCount: 5
    deadLetteringOnMessageExpiration: true
    requiresDuplicateDetection: true
    duplicateDetectionHistoryTimeWindow: 'PT10M'
  }
}

resource roles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for p in principals: {
  name: guid(namespace.id, p.id, dataOwner)
  scope: namespace
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', dataOwner)
    principalId: p.id
    principalType: p.type
  }
}]

output fullyQualifiedNamespace string = '${namespace.name}.servicebus.windows.net'
