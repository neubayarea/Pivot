// Cosmos DB for NoSQL, serverless (ADR-0006). Keys are disabled; access is Cosmos native RBAC only,
// so the database and containers are created here and never from app code.
param location string
param tags object
param name string
param databaseName string
@description('Partition key path for both containers; must match the field the adapter writes.')
param partitionKeyPath string
@description('Who gets Cosmos DB Built-in Data Contributor: [{ id, type }].')
param principals array

var dataContributor = '00000000-0000-0000-0000-000000000002'

resource account 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: name
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [{ locationName: location, failoverPriority: 0, isZoneRedundant: false }]
    capabilities: [{ name: 'EnableServerless' }]
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    disableLocalAuth: true
    disableKeyBasedMetadataWriteAccess: true
    publicNetworkAccess: 'Enabled'
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: account
  name: databaseName
  properties: {
    resource: { id: databaseName }
  }
}

// match_data holds match, minute, pivot and scenario documents (told apart by `type`);
// agent_traces expires after 7 days.
var containers = [
  { name: 'match_data', ttl: null }
  { name: 'agent_traces', ttl: 604800 }
]

resource container 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = [for c in containers: {
  parent: database
  name: c.name
  properties: {
    resource: union({
      id: c.name
      partitionKey: { paths: [partitionKeyPath], kind: 'Hash' }
    }, c.ttl == null ? {} : { defaultTtl: c.ttl })
  }
}]

resource roles 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = [for p in principals: {
  parent: account
  name: guid(account.id, p.id, dataContributor)
  properties: {
    roleDefinitionId: '${account.id}/sqlRoleDefinitions/${dataContributor}'
    principalId: p.id
    scope: account.id
  }
}]

output endpoint string = account.properties.documentEndpoint
output databaseName string = database.name
