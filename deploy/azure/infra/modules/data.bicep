// State that must outlive the VM: secrets (Key Vault) and backups (geo-redundant storage).
// The resource group gets a delete lock. Soft delete and purge protection keep secrets recoverable;
// SECRETS-KEY in particular decrypts API keys stored in the database.
param location string
param env string
param suffix string
param tags object
param alertEmail string
param operatorPrincipalId string

var keyVaultName = 'kv-fb-${env}-${suffix}'
var storageAccountName = 'stfb${env}bk${suffix}'

// Built-in role IDs.
var roles = {
  keyVaultSecretsOfficer: 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'
  storageBlobDataReader: '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
}

// Blobs older than this are deleted by the storage account itself (on top of 14 days of soft delete).
var retention = [
  {
    name: 'dumps'
    days: 35
  }
  {
    name: 'base'
    days: 15
  }
  {
    name: 'wal'
    days: 15
  }
]

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: true
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

// Not really a secret, but private: the watchdog reads it from here, so it stays out of git.
resource alertEmailSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'ALERT-EMAIL'
  properties: {
    value: alertEmail
    contentType: 'text/plain'
  }
}

resource st 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: 'Standard_GRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    // Microsoft Entra sign-in only: there are no storage keys to leak.
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    publicNetworkAccess: 'Enabled'
  }
}

resource blob 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: st
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 14
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: 14
    }
  }
}

resource backups 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blob
  name: 'backups'
  properties: {
    publicAccess: 'None'
  }
}

resource lifecycle 'Microsoft.Storage/storageAccounts/managementPolicies@2023-05-01' = {
  parent: st
  name: 'default'
  properties: {
    policy: {
      rules: [
        for r in retention: {
          enabled: true
          name: 'expire-${r.name}'
          type: 'Lifecycle'
          definition: {
            filters: {
              blobTypes: [
                'blockBlob'
              ]
              prefixMatch: [
                'backups/${r.name}/'
              ]
            }
            actions: {
              baseBlob: {
                delete: {
                  daysAfterModificationGreaterThan: r.days
                }
              }
            }
          }
        }
      ]
    }
  }
  dependsOn: [
    backups
  ]
}

// The operator sets the secrets they own in the portal, and can browse backups.
resource operatorSecrets 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(kv.id, operatorPrincipalId, roles.keyVaultSecretsOfficer)
  scope: kv
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.keyVaultSecretsOfficer)
    principalId: operatorPrincipalId
    principalType: 'User'
  }
}

resource operatorBackups 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(st.id, operatorPrincipalId, roles.storageBlobDataReader)
  scope: st
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.storageBlobDataReader)
    principalId: operatorPrincipalId
    principalType: 'User'
  }
}

resource noDelete 'Microsoft.Authorization/locks@2020-05-01' = {
  name: 'fb-${env}-data-no-delete'
  properties: {
    level: 'CanNotDelete'
    notes: 'Secrets and backups for FluidBuddha ${env}. Remove the lock only to retire the environment.'
  }
  dependsOn: [
    kv
    st
    lifecycle
  ]
}

output keyVaultName string = kv.name
output storageAccountName string = st.name
