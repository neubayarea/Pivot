// One Container App, running as the shared managed identity and pulling from ACR with it.
// azd finds it by the azd-service-name tag and swaps in the real image on `azd deploy`.
param location string
param tags object
param name string
@description('Service name in azure.yaml.')
param serviceName string
param environmentId string
param identityId string
param registryServer string
@description('True once azd has deployed this service; keeps the current image on re-provision.')
param exists bool
@description('Port the container listens on; 0 means no ingress.')
param targetPort int = 0
param external bool = false
@description('Plain environment variables: [{ name, value }]. No secrets here.')
param env array = []
param minReplicas int = 1
param maxReplicas int = 1
param cpu string = '0.5'
param memory string = '1Gi'

resource current 'Microsoft.App/containerApps@2024-03-01' existing = if (exists) {
  name: name
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: union(tags, { 'azd-service-name': serviceName })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identityId}': {} }
  }
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: targetPort == 0 ? null : {
        external: external
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: false
      }
      registries: [{ server: registryServer, identity: identityId }]
    }
    template: {
      containers: [{
        name: serviceName
        image: exists ? current.properties.template.containers[0].image : 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
        env: env
        resources: { cpu: json(cpu), memory: memory }
      }]
      scale: { minReplicas: minReplicas, maxReplicas: maxReplicas }
    }
  }
}

output name string = app.name
output fqdn string = targetPort == 0 ? '' : app.properties.configuration.ingress.fqdn
