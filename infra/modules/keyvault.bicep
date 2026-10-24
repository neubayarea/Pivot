// Key Vault with RBAC. Empty for now: it is only for third-party secrets we may add later.
// Short soft-delete and no purge protection, so `azd down --purge` can remove it.
param location string
param tags object
param name string
param principalId string

var secretsUser = '4633458b-17de-408a-b874-0445c86b69e6'

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
  }
}

resource read 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, principalId, secretsUser)
  scope: vault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', secretsUser)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

output uri string = vault.properties.vaultUri
