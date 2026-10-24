// Pivot C1 deployment (docs/architecture.md §3.1, §11; ADR-0013): one resource group with
// api, worker and web Container Apps, Service Bus, Cosmos DB serverless, Web PubSub, Key Vault,
// monitoring, a cost budget and one user-assigned managed identity. No connection strings or keys:
// every app reaches every service through the identity and data-plane RBAC.
targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('azd environment name: pivot-dev or pivot-demo.')
param environmentName string

@minLength(1)
@description('Region for every resource; pick one where the Foundry models have quota.')
param location string

@description('Object id of whoever runs azd (azd sets AZURE_PRINCIPAL_ID). Gets the same data roles, for local runs against the cloud. Empty to skip.')
param principalId string = ''

@allowed(['User', 'ServicePrincipal'])
param principalType string = 'User'

@description('Owner tag on every resource.')
param owner string = 'pivot'

@description('Where the budget alert emails go; comma separated.')
param budgetEmails string

param budgetAmount int = 50

@description('First day of the month the budget starts counting from.')
param budgetStartDate string = '2026-10-01'

@allowed(['Free_F1', 'Standard_S1'])
param webPubSubSku string = 'Free_F1'

@description('Foundry endpoint and model deployment names, set by D01. Empty until then.')
param foundryEndpoint string = ''
param foundryDeployment string = ''
param foundryDeploymentMini string = ''

@description('Set by azd once each service has been deployed (SERVICE_<NAME>_RESOURCE_EXISTS).')
param apiExists bool = false
param workerExists bool = false
param webExists bool = false

var token = toLower(uniqueString(subscription().id, environmentName, location))
var tags = { 'azd-env-name': environmentName, env: environmentName, owner: owner }
// Work queue the worker consumes; must equal pivot_core.ports.PIVOT_CANDIDATES.
var candidatesQueue = 'pivot-candidates'
var databaseName = 'pivot'
var pubsubHub = 'pivot'

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module identity 'modules/identity.bicep' = {
  name: 'identity'
  scope: rg
  params: { location: location, tags: tags, name: 'id-${token}' }
}

// The apps' identity, plus the developer (or CI principal) running azd when there is one.
var principals = concat(
  [{ id: identity.outputs.principalId, type: 'ServicePrincipal' }],
  empty(principalId) ? [] : [{ id: principalId, type: principalType }]
)

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  scope: rg
  params: { location: location, tags: tags, logAnalyticsName: 'log-${token}', appInsightsName: 'appi-${token}' }
}

module registry 'modules/registry.bicep' = {
  name: 'registry'
  scope: rg
  params: { location: location, tags: tags, name: 'cr${token}', principalId: identity.outputs.principalId }
}

module serviceBus 'modules/servicebus.bicep' = {
  name: 'servicebus'
  scope: rg
  params: { location: location, tags: tags, name: 'sb-${token}', queueName: candidatesQueue, principals: principals }
}

module cosmos 'modules/cosmos.bicep' = {
  name: 'cosmos'
  scope: rg
  params: {
    location: location
    tags: tags
    name: 'cosmos-${token}'
    databaseName: databaseName
    partitionKeyPath: '/match_id'
    principals: principals
  }
}

module webPubSub 'modules/webpubsub.bicep' = {
  name: 'webpubsub'
  scope: rg
  params: { location: location, tags: tags, name: 'wps-${token}', sku: webPubSubSku, principals: principals }
}

module keyVault 'modules/keyvault.bicep' = {
  name: 'keyvault'
  scope: rg
  params: { location: location, tags: tags, name: 'kv-${token}', principalId: identity.outputs.principalId }
}

module budget 'modules/budget.bicep' = {
  name: 'budget'
  scope: rg
  params: {
    name: 'budget-${environmentName}'
    amount: budgetAmount
    startDate: budgetStartDate
    contactEmails: map(split(budgetEmails, ','), e => trim(e))
  }
}

module containerEnv 'modules/container-apps-env.bicep' = {
  name: 'container-apps-env'
  scope: rg
  params: { location: location, tags: tags, name: 'cae-${token}', logAnalyticsName: monitoring.outputs.logAnalyticsName }
}

var apiName = 'ca-api-${token}'
var webName = 'ca-web-${token}'

// What the Python apps read. A08's Azure adapters pick these up; AZURE_CLIENT_ID tells
// DefaultAzureCredential which managed identity to use.
var appEnv = [
  { name: 'PIVOT_PROFILE', value: 'c1' }
  { name: 'AZURE_CLIENT_ID', value: identity.outputs.clientId }
  { name: 'PIVOT_COSMOS_ENDPOINT', value: cosmos.outputs.endpoint }
  { name: 'PIVOT_COSMOS_DATABASE', value: cosmos.outputs.databaseName }
  { name: 'PIVOT_SERVICEBUS_NAMESPACE', value: serviceBus.outputs.fullyQualifiedNamespace }
  { name: 'PIVOT_WEBPUBSUB_ENDPOINT', value: webPubSub.outputs.endpoint }
  { name: 'PIVOT_WEBPUBSUB_HUB', value: pubsubHub }
  { name: 'PIVOT_KEYVAULT_URI', value: keyVault.outputs.uri }
  { name: 'PIVOT_FOUNDRY_ENDPOINT', value: foundryEndpoint }
  { name: 'PIVOT_FOUNDRY_DEPLOYMENT', value: foundryDeployment }
  { name: 'PIVOT_FOUNDRY_DEPLOYMENT_MINI', value: foundryDeploymentMini }
  { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: monitoring.outputs.appInsightsConnectionString }
]

module api 'modules/container-app.bicep' = {
  name: 'api'
  scope: rg
  params: {
    location: location
    tags: tags
    name: apiName
    serviceName: 'api'
    environmentId: containerEnv.outputs.id
    identityId: identity.outputs.id
    registryServer: registry.outputs.loginServer
    exists: apiExists
    targetPort: 8000
    external: true
    minReplicas: 1
    maxReplicas: 3
    env: concat(appEnv, [
      { name: 'OTEL_SERVICE_NAME', value: 'pivot-api' }
      { name: 'PIVOT_CORS_ORIGINS', value: 'https://${webName}.${containerEnv.outputs.defaultDomain}' }
    ])
  }
}

// One replica until envelope seq is shared across workers (see A05 hand-over).
module worker 'modules/container-app.bicep' = {
  name: 'worker'
  scope: rg
  params: {
    location: location
    tags: tags
    name: 'ca-worker-${token}'
    serviceName: 'worker'
    environmentId: containerEnv.outputs.id
    identityId: identity.outputs.id
    registryServer: registry.outputs.loginServer
    exists: workerExists
    minReplicas: 1
    maxReplicas: 1
    env: concat(appEnv, [{ name: 'OTEL_SERVICE_NAME', value: 'pivot-worker' }])
  }
}

// nginx serving the Vite build and proxying /api to the API, so the browser sees one origin.
module web 'modules/container-app.bicep' = {
  name: 'web'
  scope: rg
  params: {
    location: location
    tags: tags
    name: webName
    serviceName: 'web'
    environmentId: containerEnv.outputs.id
    identityId: identity.outputs.id
    registryServer: registry.outputs.loginServer
    exists: webExists
    targetPort: 80
    external: true
    minReplicas: 1
    maxReplicas: 2
    cpu: '0.25'
    memory: '0.5Gi'
    env: [{ name: 'API_UPSTREAM', value: 'https://${api.outputs.fqdn}' }]
  }
}

// azd writes these into .azure/<env>/.env.
output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = registry.outputs.loginServer
output AZURE_CONTAINER_REGISTRY_NAME string = registry.outputs.name
output AZURE_CONTAINER_ENVIRONMENT_NAME string = containerEnv.outputs.name
output PIVOT_WEB_URL string = 'https://${web.outputs.fqdn}'
output PIVOT_API_URL string = 'https://${api.outputs.fqdn}'
output PIVOT_COSMOS_ENDPOINT string = cosmos.outputs.endpoint
output PIVOT_COSMOS_DATABASE string = cosmos.outputs.databaseName
output PIVOT_SERVICEBUS_NAMESPACE string = serviceBus.outputs.fullyQualifiedNamespace
output PIVOT_WEBPUBSUB_ENDPOINT string = webPubSub.outputs.endpoint
output PIVOT_WEBPUBSUB_HUB string = pubsubHub
output PIVOT_KEYVAULT_URI string = keyVault.outputs.uri
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.appInsightsConnectionString
// D01 grants this principal access to the Foundry resource.
output PIVOT_IDENTITY_PRINCIPAL_ID string = identity.outputs.principalId
output PIVOT_IDENTITY_CLIENT_ID string = identity.outputs.clientId
