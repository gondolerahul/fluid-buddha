// FluidBuddha production on Azure: docs/deployment/azure-production-plan.md §3.
// Deployed at subscription scope by provision.ps1, into two resource groups:
//
//   rg-fb-<env>-core  network, firewall, static IP, VM, registry, GitHub identities, alerts
//   rg-fb-<env>-data  Key Vault and backup storage. A delete lock protects it, and it outlives a
//                     rebuild of the core group.
//
// Every name starts with "fb", so nothing meets the other workloads in the same subscription.
targetScope = 'subscription'

@description('Azure region for everything.')
param location string = 'centralindia'

@description('Environment, used in every name.')
@allowed([
  'prod'
  'staging'
  'dev'
])
param env string = 'prod'

@description('VM size. Production runs Standard_B2s_v2 (Central India had no B2as_v2 capacity at launch). Fallbacks: Standard_B2as_v2, Standard_B2ms, Standard_D2as_v5.')
param vmSize string = 'Standard_B2s_v2'

@description('Linux admin user, for emergency SSH only.')
param adminUsername string = 'fbadmin'

@description('SSH public key (the contents of the .pub file).')
param sshPublicKey string

@description('The address allowed to SSH, as CIDR (203.0.113.7/32). Empty: no SSH rule at all.')
param adminIpCidr string = ''

@description('Where Azure alerts, budget emails and the VM watchdog write to.')
param alertEmail string

@description('Object ID of the person running provisioning. Gets Key Vault Secrets Officer and read access to backups.')
param operatorPrincipalId string

@description('Start of the OIDC subject GitHub sends for this repository. With immutable subjects (a repository setting) it carries the owner and repository IDs: gh api repos/OWNER/REPO/actions/oidc/customization/sub shows it.')
param githubSubjectPrefix string = 'repo:gondolerahul@158562688/fluid-buddha@1439640317'

@description('Branch whose workflow runs may push images.')
param githubBuildBranch string = 'main'

@description('GitHub environment whose jobs may deploy (protected by a required reviewer).')
param githubEnvironment string = 'production'

@description('Public names the VM serves.')
param siteDomain string = 'fluidbuddha.com'
param consoleDomain string = 'app.fluidbuddha.com'
param apiDomain string = 'gateway.fluidbuddha.com'

@description('Address space: FluidBuddha takes 10.50 (dev), 10.51 (staging) and 10.52 (prod), clear of the other networks in the subscription.')
param vnetCidr string = '10.52.0.0/24'
param subnetCidr string = '10.52.0.0/26'
param vmPrivateIp string = '10.52.0.4'

@description('False when the VM already exists: it is then left exactly as it is, because its custom data and OS profile cannot change after creation. provision.ps1 sets this.')
param deployVm bool = true

@description('Monthly budget in USD across both resource groups. 0 = no budget.')
param budgetAmount int = 120

@description('First day of the budget\'s first month (yyyy-MM-01). provision.ps1 sets this.')
param budgetStartDate string = ''

var prefix = 'fb'
// Globally unique names (vault, registry, storage) get a short suffix that is stable per subscription.
var suffix = take(uniqueString(subscription().subscriptionId, prefix, env), 6)
var tags = {
  product: 'fluidbuddha'
  env: env
  managedBy: 'bicep'
}
var rgCoreName = 'rg-${prefix}-${env}-core'
var rgDataName = 'rg-${prefix}-${env}-data'

resource rgCore 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: rgCoreName
  location: location
  tags: tags
}

resource rgData 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: rgDataName
  location: location
  tags: tags
}

module data 'modules/data.bicep' = {
  name: '${prefix}-${env}-data'
  scope: rgData
  params: {
    location: location
    env: env
    suffix: suffix
    tags: tags
    alertEmail: alertEmail
    operatorPrincipalId: operatorPrincipalId
  }
}

module core 'modules/core.bicep' = {
  name: '${prefix}-${env}-core'
  scope: rgCore
  params: {
    location: location
    env: env
    suffix: suffix
    tags: tags
    vmSize: vmSize
    adminUsername: adminUsername
    sshPublicKey: sshPublicKey
    adminIpCidr: adminIpCidr
    alertEmail: alertEmail
    githubSubjectPrefix: githubSubjectPrefix
    githubBuildBranch: githubBuildBranch
    githubEnvironment: githubEnvironment
    siteDomain: siteDomain
    consoleDomain: consoleDomain
    apiDomain: apiDomain
    vnetCidr: vnetCidr
    subnetCidr: subnetCidr
    vmPrivateIp: vmPrivateIp
    deployVm: deployVm
    keyVaultName: data.outputs.keyVaultName
    storageAccountName: data.outputs.storageAccountName
  }
}

// The VM's identity reads and writes secrets (it generates the internal ones on the first deploy)
// and writes backups.
module dataAccess 'modules/data-access.bicep' = {
  name: '${prefix}-${env}-data-access'
  scope: rgData
  params: {
    keyVaultName: data.outputs.keyVaultName
    storageAccountName: data.outputs.storageAccountName
    vmPrincipalId: core.outputs.vmPrincipalId
  }
}

resource budget 'Microsoft.Consumption/budgets@2023-05-01' = if (budgetAmount > 0) {
  name: 'budget-${prefix}-${env}'
  properties: {
    category: 'Cost'
    amount: budgetAmount
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: budgetStartDate
    }
    filter: {
      dimensions: {
        name: 'ResourceGroupName'
        operator: 'In'
        values: [
          rgCoreName
          rgDataName
        ]
      }
    }
    notifications: {
      actual80: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 80
        thresholdType: 'Actual'
        contactEmails: [
          alertEmail
        ]
      }
      actual100: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Actual'
        contactEmails: [
          alertEmail
        ]
      }
      forecast100: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Forecasted'
        contactEmails: [
          alertEmail
        ]
      }
    }
  }
  dependsOn: [
    rgCore
    rgData
  ]
}

// Not secret: they go into GitHub repository variables (docs/deployment/azure-operator-guide.md, B5).
output RESOURCE_GROUP string = rgCore.name
output DATA_RESOURCE_GROUP string = rgData.name
output VM_NAME string = core.outputs.vmName
output PUBLIC_IP string = core.outputs.publicIp
output PUBLIC_FQDN string = core.outputs.publicFqdn
output ACR_NAME string = core.outputs.acrName
output KEY_VAULT string = data.outputs.keyVaultName
output STORAGE_ACCOUNT string = data.outputs.storageAccountName
output AZURE_BUILD_CLIENT_ID string = core.outputs.buildClientId
output AZURE_DEPLOY_CLIENT_ID string = core.outputs.deployClientId
output AZURE_TENANT_ID string = subscription().tenantId
output AZURE_SUBSCRIPTION_ID string = subscription().subscriptionId
