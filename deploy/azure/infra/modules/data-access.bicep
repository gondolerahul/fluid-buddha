// The VM's managed identity on the data resource group: it reads secrets and generates the internal
// ones on the first deploy (Key Vault Secrets Officer), and writes backups (Blob Data Contributor,
// on the backups container only).
param keyVaultName string
param storageAccountName string
param vmPrincipalId string

var roles = {
  keyVaultSecretsOfficer: 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'
  storageBlobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
}

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource st 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource blob 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' existing = {
  parent: st
  name: 'default'
}

resource backups 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' existing = {
  parent: blob
  name: 'backups'
}

resource vmSecrets 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(kv.id, vmPrincipalId, roles.keyVaultSecretsOfficer)
  scope: kv
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.keyVaultSecretsOfficer)
    principalId: vmPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource vmBackups 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(backups.id, vmPrincipalId, roles.storageBlobDataContributor)
  scope: backups
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.storageBlobDataContributor)
    principalId: vmPrincipalId
    principalType: 'ServicePrincipal'
  }
}
