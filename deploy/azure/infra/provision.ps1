<#
.SYNOPSIS
Provisions FluidBuddha on Azure: two resource groups, the VM and everything around it
(docs/deployment/azure-production-plan.md, section 3). Safe to run again: an existing VM is left
exactly as it is, and a soft-deleted Key Vault is recovered with its secrets.

.EXAMPLE
# Preview the changes. Nothing is created.
./deploy/azure/infra/provision.ps1 -SshPublicKeyPath "$env:USERPROFILE\.ssh\fluidbuddha_prod.pub" -AdminIp 203.0.113.7 -AlertEmail ops@example.com -Preview

.EXAMPLE
# Create or update, then store the outputs as GitHub repository variables.
./deploy/azure/infra/provision.ps1 -SshPublicKeyPath "$env:USERPROFILE\.ssh\fluidbuddha_prod.pub" -AdminIp 203.0.113.7 -AlertEmail ops@example.com -SetGitHubVariables
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $SshPublicKeyPath,
    [Parameter(Mandatory = $true)] [string] $AlertEmail,
    # Your public IPv4 address; only it may SSH in. Leave it out to keep SSH closed.
    [string] $AdminIp = '',
    # Subscription name or ID. Default: the one az is set to.
    [string] $Subscription = '',
    [ValidateSet('prod', 'staging', 'dev')] [string] $Environment = 'prod',
    [string] $Location = 'centralindia',
    [string] $VmSize = 'Standard_B2s_v2',
    [int] $BudgetUsd = 120,
    # Show what would change (az what-if) and stop.
    [switch] $Preview,
    # Store the outputs as GitHub repository variables with gh (needs admin rights on the repo).
    [switch] $SetGitHubVariables
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$template = Join-Path $here 'main.bicep'

function Invoke-Az {
    # Runs az and returns its output as one string; stops on a non-zero exit code.
    $out = & az @args
    if ($LASTEXITCODE -ne 0) { throw "az $($args -join ' ') failed (exit code $LASTEXITCODE)." }
    ($out | Out-String).Trim()
}

function Get-AzQuietly {
    # Runs az and returns its output, or an empty string if it fails (for example: not found).
    # Windows PowerShell turns redirected stderr into errors, so relax that for the call.
    $saved = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = & az @args 2>$null
        if ($LASTEXITCODE -ne 0) { return '' }
        return ($out | Out-String).Trim()
    } finally {
        $ErrorActionPreference = $saved
    }
}

Write-Host "FluidBuddha on Azure: provisioning '$Environment'" -ForegroundColor Cyan

# 1. Subscription.
if ($Subscription) { Invoke-Az account set --subscription $Subscription | Out-Null }
$account = Invoke-Az account show -o json | ConvertFrom-Json
Write-Host "Subscription: $($account.name) ($($account.id))"

# 2. Inputs.
if (-not (Test-Path -LiteralPath $SshPublicKeyPath)) {
    throw "No SSH public key at $SshPublicKeyPath (operator guide, step A2)."
}
$sshKey = (Get-Content -Raw -LiteralPath $SshPublicKeyPath).Trim()
if ($sshKey -notmatch '^(ssh-ed25519|ssh-rsa|ecdsa-sha2-\S+) ') {
    throw "$SshPublicKeyPath doesn't look like an SSH public key. Use the .pub file."
}
$adminCidr = ''
if ($AdminIp) {
    $adminCidr = $AdminIp.Trim()
    if ($adminCidr -notmatch '/') { $adminCidr = "$adminCidr/32" }
    if ($adminCidr -notmatch '^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$') {
        throw "-AdminIp must be an IPv4 address, like 203.0.113.7."
    }
} else {
    Write-Warning 'No -AdminIp: SSH stays closed. Deploys use Run Command, so they still work.'
}
if ($AlertEmail -notmatch '^[^@\s]+@[^@\s]+\.[^@\s]+$') { throw "-AlertEmail doesn't look like an email address." }

# 3. The person running this gets Key Vault Secrets Officer, and must be allowed to assign roles.
$me = Invoke-Az ad signed-in-user show --query id -o tsv
$myRoles = Invoke-Az role assignment list --assignee $me --scope "/subscriptions/$($account.id)" --include-inherited --query "[].roleDefinitionName" -o tsv
if (-not ($myRoles -split "`r?`n" | Where-Object { $_ -in @('Owner', 'User Access Administrator') })) {
    Write-Warning 'Could not confirm Owner or User Access Administrator for you on this subscription. Provisioning creates role assignments and fails without one of them.'
}

# 4. Resource providers (registered once per subscription; usually already are).
$providers = @('Microsoft.Compute', 'Microsoft.Network', 'Microsoft.KeyVault', 'Microsoft.Storage',
    'Microsoft.ContainerRegistry', 'Microsoft.ManagedIdentity', 'Microsoft.Insights', 'Microsoft.Consumption')
foreach ($ns in $providers) {
    $state = Invoke-Az provider show --namespace $ns --query registrationState -o tsv
    if ($state -ne 'Registered') {
        if ($Preview) { Write-Warning "$ns isn't registered yet; a real run registers it." }
        else { Write-Host "Registering $ns ..."; Invoke-Az provider register --namespace $ns --wait | Out-Null }
    }
}

# 5. What exists already. An existing VM is left alone: its custom data and OS profile can't change.
$rgCore = "rg-fb-$Environment-core"
$rgData = "rg-fb-$Environment-data"
$vmName = "vm-fb-$Environment-01"
$vmExists = [bool](Get-AzQuietly vm show --resource-group $rgCore --name $vmName --query id -o tsv)
if ($vmExists) {
    Write-Host "VM $vmName exists: it is kept as it is (resize or rebuild it with the runbook)."
} else {
    # Quota for the VM's family in the region, and the regional total.
    $family = $null
    if ($VmSize -match '^Standard_B\d+al?s_v2$') { $family = 'standardBasv2Family' }
    elseif ($VmSize -match '^Standard_B\d+l?s_v2$') { $family = 'standardBsv2Family' }
    elseif ($VmSize -match '^Standard_B\d+m?s$') { $family = 'standardBSFamily' }
    elseif ($VmSize -match '^Standard_D\d+as_v5$') { $family = 'standardDASv5Family' }
    $cores = [int]($VmSize -replace '^Standard_[A-Z]+(\d+).*$', '$1')
    $usage = Invoke-Az vm list-usage --location $Location -o json | ConvertFrom-Json
    foreach ($u in $usage | Where-Object { $_.name.value -eq 'cores' -or $_.name.value -eq $family }) {
        $free = [int]$u.limit - [int]$u.currentValue
        if ($free -lt $cores) {
            throw "Not enough vCPU quota for $VmSize in ${Location}: '$($u.localName)' has $free free. Request more under Portal > Quotas > Compute."
        }
    }
    Write-Host "Quota: enough vCPUs for $VmSize in $Location."
}

# A soft-deleted vault comes back with its secrets (SECRETS-KEY decrypts stored API keys).
$deletedVaults = Invoke-Az keyvault list-deleted --resource-type vault --query "[?starts_with(name, 'kv-fb-$Environment-')].name" -o tsv
foreach ($vault in ($deletedVaults -split "`r?`n" | Where-Object { $_ })) {
    if ($Preview) {
        Write-Warning "Key Vault $vault is soft-deleted. A real run recovers it with its secrets."
    } else {
        Write-Host "Recovering Key Vault $vault with its secrets ..."
        Invoke-Az group create --name $rgData --location $Location --tags product=fluidbuddha env=$Environment managedBy=bicep | Out-Null
        Invoke-Az keyvault recover --name $vault | Out-Null
    }
}

# A budget keeps the start month it was created with.
$budgetStart = (Get-Date).ToUniversalTime().ToString('yyyy-MM-01')
$existingStart = Get-AzQuietly rest --method get --url "https://management.azure.com/subscriptions/$($account.id)/providers/Microsoft.Consumption/budgets/budget-fb-$($Environment)?api-version=2023-05-01" --query properties.timePeriod.startDate -o tsv
if ($existingStart) { $budgetStart = $existingStart.Substring(0, 10) }

# 6. Deploy (or preview).
$parameters = [ordered]@{
    '$schema'      = 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#'
    contentVersion = '1.0.0.0'
    parameters     = [ordered]@{
        location            = @{ value = $Location }
        env                 = @{ value = $Environment }
        vmSize              = @{ value = $VmSize }
        sshPublicKey        = @{ value = $sshKey }
        adminIpCidr         = @{ value = $adminCidr }
        alertEmail          = @{ value = $AlertEmail }
        operatorPrincipalId = @{ value = $me }
        deployVm            = @{ value = (-not $vmExists) }
        budgetAmount        = @{ value = $BudgetUsd }
        budgetStartDate     = @{ value = $budgetStart }
    }
}
$paramFile = Join-Path ([IO.Path]::GetTempPath()) "fluidbuddha-$Environment-parameters.json"
[IO.File]::WriteAllText($paramFile, ($parameters | ConvertTo-Json -Depth 5), (New-Object Text.UTF8Encoding($false)))

$deployment = @('--name', "fb-$Environment-$(Get-Date -Format 'yyyyMMdd-HHmm')", '--location', $Location,
    '--template-file', $template, '--parameters', "@$paramFile")
try {
    if ($Preview) {
        Write-Host "`nWhat would change (nothing is created):" -ForegroundColor Cyan
        & az deployment sub what-if @deployment
        if ($LASTEXITCODE -ne 0) { throw "what-if failed (exit code $LASTEXITCODE)." }
        return
    }
    Write-Host "`nDeploying. This takes about 5 to 10 minutes ..." -ForegroundColor Cyan
    $outputs = Invoke-Az deployment sub create @deployment --query properties.outputs -o json | ConvertFrom-Json
} finally {
    Remove-Item -LiteralPath $paramFile -ErrorAction SilentlyContinue
}

# 7. Outputs. None are secret.
$values = [ordered]@{}
foreach ($p in $outputs.PSObject.Properties) { $values[$p.Name] = $p.Value.value }
$outFile = Join-Path $here "outputs.$Environment.json"
[IO.File]::WriteAllText($outFile, ($values | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))
Write-Host "`nDone. Outputs (also in $outFile):" -ForegroundColor Green
$values.GetEnumerator() | ForEach-Object { '{0,-24} {1}' -f $_.Key, $_.Value } | Write-Host

if ($SetGitHubVariables) {
    $variables = [ordered]@{
        AZURE_TENANT_ID        = $values.AZURE_TENANT_ID
        AZURE_SUBSCRIPTION_ID  = $values.AZURE_SUBSCRIPTION_ID
        AZURE_BUILD_CLIENT_ID  = $values.AZURE_BUILD_CLIENT_ID
        AZURE_DEPLOY_CLIENT_ID = $values.AZURE_DEPLOY_CLIENT_ID
        AZURE_RESOURCE_GROUP   = $values.RESOURCE_GROUP
        AZURE_VM_NAME          = $values.VM_NAME
        ACR_NAME               = $values.ACR_NAME
    }
    foreach ($v in $variables.GetEnumerator()) {
        & gh variable set $v.Key --body $v.Value
        if ($LASTEXITCODE -ne 0) { throw "gh variable set $($v.Key) failed." }
    }
    Write-Host 'GitHub repository variables set.' -ForegroundColor Green
}

Write-Host @"

Next (docs/deployment/azure-operator-guide.md):
  - The VM finishes installing by itself over the next 5 minutes (cloud-init).
  - Key Vault $($values.KEY_VAULT): add the secrets you own (Part B3).
  - GoDaddy: point fluidbuddha.com, app and gateway at $($values.PUBLIC_IP) (Part B4).
"@
