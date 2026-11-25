// The VM: Ubuntu 24.04 LTS (Gen2, Trusted Launch), 64 GiB Premium SSD, a system-assigned identity
// for Key Vault, the registry and backups. Created once: custom data and the OS profile can't change
// afterwards, so provision.ps1 skips this module when the VM already exists.
param location string
param tags object
param vmName string
param vmSize string
param adminUsername string
param sshPublicKey string
param nicId string

@description('Values for the __NAME__ placeholders in cloud-init.yaml.')
param hostSettings object

// bootstrap.sh travels base64-encoded, so YAML indentation can't break it.
var placeholders = union(hostSettings, {
  BOOTSTRAP_B64: base64(loadTextContent('../bootstrap.sh'))
})
var cloudInit = reduce(
  items(placeholders),
  loadTextContent('../cloud-init.yaml'),
  (text, setting) => replace(text, '__${setting.key}__', string(setting.value))
)

resource vm 'Microsoft.Compute/virtualMachines@2024-07-01' = {
  name: vmName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    hardwareProfile: {
      vmSize: vmSize
    }
    securityProfile: {
      securityType: 'TrustedLaunch'
      uefiSettings: {
        secureBootEnabled: true
        vTpmEnabled: true
      }
    }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: 'ubuntu-24_04-lts'
        sku: 'server'
        version: 'latest'
      }
      osDisk: {
        createOption: 'FromImage'
        caching: 'ReadWrite'
        diskSizeGB: 64
        managedDisk: {
          storageAccountType: 'Premium_LRS'
        }
        // Deleting the VM by mistake keeps the disk, and with it the live database.
        deleteOption: 'Detach'
      }
    }
    osProfile: {
      computerName: vmName
      adminUsername: adminUsername
      customData: base64(cloudInit)
      linuxConfiguration: {
        disablePasswordAuthentication: true
        ssh: {
          publicKeys: [
            {
              path: '/home/${adminUsername}/.ssh/authorized_keys'
              keyData: sshPublicKey
            }
          ]
        }
        provisionVMAgent: true
        patchSettings: {
          // Ubuntu's unattended-upgrades patches the VM (cloud-init.yaml).
          patchMode: 'ImageDefault'
          assessmentMode: 'ImageDefault'
        }
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: nicId
          properties: {
            deleteOption: 'Detach'
          }
        }
      ]
    }
    diagnosticsProfile: {
      bootDiagnostics: {
        enabled: true
      }
    }
  }
}

output principalId string = vm.identity.principalId
