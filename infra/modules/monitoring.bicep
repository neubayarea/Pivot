// Log Analytics workspace and a workspace-based Application Insights.
param location string
param tags object
param logAnalyticsName string
param appInsightsName string

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
  }
}

output logAnalyticsName string = logs.name
// Not a credential: it only says where to send telemetry.
output appInsightsConnectionString string = appInsights.properties.ConnectionString
