// Who may do what on the core resource group. Principal IDs arrive as parameters, so the role
// assignment names (which must be known when a deployment starts) can include them.
param acrName string
param vmName string
param vmPrincipalId string
param buildPrincipalId string
param deployPrincipalId string

// Built-in role IDs.
var roles = {
  reader: 'acdd72a7-3385-48ef-bd42-f606fba81ae7'
  acrPull: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
  acrPush: '8311e382-0749-4cb8-b61a-304f252e45ec'
  acrDelete: 'c2f4ef07-c644-48eb-af81-4b1b4947fb11'
  virtualMachineContributor: '9980e02c-c2be-4d73-94e8-173b1dc7cf3c'
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: acrName
}

resource vm 'Microsoft.Compute/virtualMachines@2024-07-01' existing = {
  name: vmName
}

// The VM pulls release images; the build identity pushes them and prunes old ones.
var registryGrants = [
  {
    principal: vmPrincipalId
    role: roles.acrPull
  }
  {
    principal: vmPrincipalId
    role: roles.reader
  }
  {
    principal: buildPrincipalId
    role: roles.acrPush
  }
  {
    principal: buildPrincipalId
    role: roles.acrDelete
  }
]

resource registryRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for g in registryGrants: {
    name: guid(acr.id, g.principal, g.role)
    scope: acr
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', g.role)
      principalId: g.principal
      principalType: 'ServicePrincipal'
    }
  }
]

// Both GitHub identities can read this resource group, so azure/login finds the subscription and az
// can look resources up by name.
resource groupReaders 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for p in [
    buildPrincipalId
    deployPrincipalId
  ]: {
    name: guid(resourceGroup().id, p, roles.reader)
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.reader)
      principalId: p
      principalType: 'ServicePrincipal'
    }
  }
]

// The deploy identity runs the release on this VM (Run Command), and nothing else.
resource deployOnVm 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vm.id, deployPrincipalId, roles.virtualMachineContributor)
  scope: vm
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.virtualMachineContributor)
    principalId: deployPrincipalId
    principalType: 'ServicePrincipal'
  }
}
