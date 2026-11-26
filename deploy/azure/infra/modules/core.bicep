// Compute and network for one environment: the firewall (NSG), network, static IP, the VM, the image
// registry, the GitHub identities that build and deploy, and the alerts.
param location string
param env string
param suffix string
param tags object
param vmSize string
param adminUsername string
param sshPublicKey string
param adminIpCidr string
param alertEmail string
param githubSubjectPrefix string
param githubBuildBranch string
param githubEnvironment string
param siteDomain string
param consoleDomain string
param apiDomain string
param vnetCidr string
param subnetCidr string
param vmPrivateIp string
param deployVm bool
param keyVaultName string
param storageAccountName string

var name = 'fb-${env}'
var vmName = 'vm-${name}-01'
var acrName = 'acrfb${env}${suffix}'
var acrLoginServer = '${acrName}${environment().suffixes.acrLoginServer}'
// B-series v1 sizes (the B2ms fallback) lack accelerated networking; Basv2, Bsv2 and D-series have it.
var burstable = startsWith(toLower(vmSize), 'standard_b')
var acceleratedNetworking = !burstable || contains(toLower(vmSize), '_v2')

var publicRules = [
  {
    name: 'https'
    priority: 100
    protocol: 'Tcp'
    ports: [
      '80'
      '443'
    ]
    source: 'Internet'
    description: 'HTTPS, plus HTTP for certificate issuance and redirects'
  }
  {
    name: 'http3'
    priority: 110
    protocol: 'Udp'
    ports: [
      '443'
    ]
    source: 'Internet'
    description: 'HTTP/3'
  }
  {
    name: 'turn'
    priority: 120
    protocol: '*'
    ports: [
      '3478'
    ]
    source: 'Internet'
    description: 'TURN relay for voice handoff, UDP and TCP'
  }
  {
    name: 'turn-relay'
    priority: 130
    protocol: 'Udp'
    ports: [
      '49160-49200'
    ]
    source: 'Internet'
    description: 'TURN relay ports, about 20 handoffs at once'
  }
]
var sshRule = [
  {
    name: 'ssh-operator'
    priority: 140
    protocol: 'Tcp'
    ports: [
      '22'
    ]
    source: adminIpCidr
    description: 'Emergency SSH from the operator\'s address only. Deploys use Run Command, not SSH.'
  }
]
var rules = concat(publicRules, empty(adminIpCidr) ? [] : sshRule)

resource nsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: 'nsg-${name}-app'
  location: location
  tags: tags
  properties: {
    securityRules: [
      for r in rules: {
        name: r.name
        properties: {
          priority: r.priority
          direction: 'Inbound'
          access: 'Allow'
          protocol: r.protocol
          sourceAddressPrefix: r.source
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRanges: r.ports
          description: r.description
        }
      }
    ]
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: 'vnet-${name}'
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetCidr
      ]
    }
    subnets: [
      {
        name: 'snet-app'
        properties: {
          addressPrefix: subnetCidr
          networkSecurityGroup: {
            id: nsg.id
          }
          // The VM's own public IP carries its outbound traffic.
          defaultOutboundAccess: false
        }
      }
    ]
  }
}

resource pip 'Microsoft.Network/publicIPAddresses@2024-05-01' = {
  name: 'pip-${name}-vm'
  location: location
  tags: tags
  sku: {
    name: 'Standard'
    tier: 'Regional'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
    publicIPAddressVersion: 'IPv4'
    // Long-lived WebSockets (voice sessions) get more room than the 4-minute default.
    idleTimeoutInMinutes: 30
    dnsSettings: {
      domainNameLabel: 'fb-${env}-${suffix}'
    }
  }
}

resource nic 'Microsoft.Network/networkInterfaces@2024-05-01' = {
  name: 'nic-${name}-vm'
  location: location
  tags: tags
  properties: {
    enableAcceleratedNetworking: acceleratedNetworking
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          subnet: {
            id: vnet.properties.subnets[0].id
          }
          privateIPAllocationMethod: 'Static'
          privateIPAddress: vmPrivateIp
          publicIPAddress: {
            id: pip.id
          }
        }
      }
    ]
  }
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

module vm 'vm.bicep' = if (deployVm) {
  name: '${name}-vm'
  params: {
    location: location
    tags: tags
    vmName: vmName
    vmSize: vmSize
    adminUsername: adminUsername
    sshPublicKey: sshPublicKey
    nicId: nic.id
    // Written to /etc/fluidbuddha/host.env at first boot (cloud-init.yaml). Nothing here is secret.
    hostSettings: {
      FB_ENV: env
      ADMIN_USER: adminUsername
      KEY_VAULT: keyVaultName
      ACR_NAME: acrName
      ACR_LOGIN_SERVER: acrLoginServer
      STORAGE_ACCOUNT: storageAccountName
      PUBLIC_IP: pip.properties.ipAddress
      PRIVATE_IP: vmPrivateIp
      SITE_DOMAIN: siteDomain
      CONSOLE_DOMAIN: consoleDomain
      API_DOMAIN: apiDomain
    }
  }
}

// The VM, whether created just now or on an earlier run. A new VM's identity comes from the module
// itself: looking it up here can run before the VM exists.
resource vmRef 'Microsoft.Compute/virtualMachines@2024-07-01' existing = {
  name: vmName
}
var vmPrincipalId = deployVm ? vm!.outputs.principalId : vmRef.identity.principalId

// GitHub Actions signs in with OIDC: no password or key is stored in GitHub.
// "build" pushes images from main; "deploy" runs the release on the VM, only from the protected
// environment (a required reviewer approves each deploy).
resource buildIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${name}-build'
  location: location
  tags: tags
}

resource buildFederation 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: buildIdentity
  name: 'github-${githubBuildBranch}'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: '${githubSubjectPrefix}:ref:refs/heads/${githubBuildBranch}'
    audiences: [
      'api://AzureADTokenExchange'
    ]
  }
}

resource deployIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${name}-deploy'
  location: location
  tags: tags
}

resource deployFederation 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: deployIdentity
  name: 'github-${githubEnvironment}'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: '${githubSubjectPrefix}:environment:${githubEnvironment}'
    audiences: [
      'api://AzureADTokenExchange'
    ]
  }
}

module access 'core-access.bicep' = {
  name: '${name}-core-access'
  params: {
    acrName: acr.name
    vmName: vmName
    vmPrincipalId: vmPrincipalId
    buildPrincipalId: buildIdentity.properties.principalId
    deployPrincipalId: deployIdentity.properties.principalId
  }
  dependsOn: [
    vm
  ]
}

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: 'ag-${name}'
  location: 'global'
  tags: tags
  properties: {
    groupShortName: 'fb-${env}'
    enabled: true
    emailReceivers: [
      {
        name: 'operator'
        emailAddress: alertEmail
        useCommonAlertSchema: true
      }
    ]
  }
}

var baseAlerts = [
  {
    name: 'cpu-high'
    metric: 'Percentage CPU'
    operator: 'GreaterThan'
    threshold: 85
    description: 'CPU above 85 % for 15 minutes.'
  }
  {
    name: 'memory-low'
    metric: 'Available Memory Bytes'
    operator: 'LessThan'
    threshold: 419430400
    description: 'Less than 400 MiB of memory available for 15 minutes.'
  }
]
var creditAlert = [
  {
    name: 'cpu-credits-low'
    metric: 'CPU Credits Remaining'
    operator: 'LessThan'
    threshold: 30
    description: 'Burstable CPU credits are nearly used up, so the VM is about to be throttled. Resize it (runbook) if this repeats.'
  }
]
var metricAlerts = concat(baseAlerts, burstable ? creditAlert : [])

resource alerts 'Microsoft.Insights/metricAlerts@2018-03-01' = [
  for a in metricAlerts: {
    name: 'alert-${name}-${a.name}'
    location: 'global'
    tags: tags
    properties: {
      description: a.description
      severity: 2
      enabled: true
      scopes: [
        vmRef.id
      ]
      evaluationFrequency: 'PT5M'
      windowSize: 'PT15M'
      autoMitigate: true
      criteria: {
        'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
        allOf: [
          {
            criterionType: 'StaticThresholdCriterion'
            name: a.name
            metricName: a.metric
            metricNamespace: 'Microsoft.Compute/virtualMachines'
            operator: a.operator
            threshold: a.threshold
            timeAggregation: 'Average'
          }
        ]
      }
      actions: [
        {
          actionGroupId: actionGroup.id
        }
      ]
    }
    dependsOn: [
      vm
    ]
  }
]

resource vmHealth 'Microsoft.Insights/activityLogAlerts@2020-10-01' = {
  name: 'alert-${name}-vm-health'
  location: 'global'
  tags: tags
  properties: {
    enabled: true
    description: 'The VM became unavailable, degraded or available again (Azure Resource Health).'
    scopes: [
      resourceGroup().id
    ]
    condition: {
      allOf: [
        {
          field: 'category'
          equals: 'ResourceHealth'
        }
        {
          field: 'resourceType'
          equals: 'Microsoft.Compute/virtualMachines'
        }
      ]
    }
    actions: {
      actionGroups: [
        {
          actionGroupId: actionGroup.id
        }
      ]
    }
  }
}

output vmName string = vmName
output vmPrincipalId string = vmPrincipalId
output publicIp string = pip.properties.ipAddress
output publicFqdn string = pip.properties.dnsSettings.fqdn
output acrName string = acr.name
output buildClientId string = buildIdentity.properties.clientId
output deployClientId string = deployIdentity.properties.clientId
