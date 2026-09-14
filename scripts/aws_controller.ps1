[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('Preflight', 'Pilot', 'Final')]
    [string]$Phase,

    [string]$TerraformDirectory = (Join-Path $PSScriptRoot '..\terraform'),
    [string]$Profile,
    [string]$PilotSummary,
    [string]$ExperimentId
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ResultsRoot = Join-Path $RepoRoot 'results\mode_b'
$ControllerRunId = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$ControllerEvidence = Join-Path $ResultsRoot "controller\$ControllerRunId"
New-Item -ItemType Directory -Path $ControllerEvidence -Force | Out-Null
if ($Profile) { $env:AWS_PROFILE = $Profile }

function Write-Utf8NoBom {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][string]$Content)
    [System.IO.File]::WriteAllText($Path, $Content, (New-Object System.Text.UTF8Encoding($false)))
}

function Invoke-Native {
    param([Parameter(Mandatory)][string]$Command, [Parameter(Mandatory)][string[]]$Arguments)
    $output = & $Command @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "$Command failed ($LASTEXITCODE): $($output -join [Environment]::NewLine)"
    }
    return ($output -join [Environment]::NewLine)
}

function Invoke-Ssm {
    param(
        [Parameter(Mandatory)][string]$InstanceId,
        [Parameter(Mandatory)][string]$Command,
        [Parameter(Mandatory)][string]$Label,
        [Parameter(Mandatory)][string]$Region
    )
    $parameterPath = Join-Path $ControllerEvidence "${Label}_parameters.json"
    Write-Utf8NoBom -Path $parameterPath -Content (@{ commands = @($Command) } | ConvertTo-Json -Depth 4)
    $commandId = Invoke-Native aws @(
        'ssm', 'send-command', '--region', $Region, '--instance-ids', $InstanceId,
        '--document-name', 'AWS-RunShellScript', '--parameters', "file://$parameterPath",
        '--query', 'Command.CommandId', '--output', 'text'
    )
    $invocation = $null
    for ($attempt = 0; $attempt -lt 360; $attempt++) {
        Start-Sleep -Seconds 2
        try {
            $raw = Invoke-Native aws @(
                'ssm', 'get-command-invocation', '--region', $Region,
                '--command-id', $commandId.Trim(), '--instance-id', $InstanceId
            )
            $invocation = $raw | ConvertFrom-Json
            if ($invocation.Status -in @('Success', 'Cancelled', 'TimedOut', 'Failed', 'Cancelling')) { break }
        } catch {
            if ($attempt -ge 359) { throw }
        }
    }
    if ($null -eq $invocation) { throw "No SSM invocation result for $Label" }
    Write-Utf8NoBom -Path (Join-Path $ControllerEvidence "${Label}_invocation.json") -Content ($invocation | ConvertTo-Json -Depth 20)
    if ($invocation.Status -ne 'Success' -or $invocation.ResponseCode -ne 0) {
        throw "SSM $Label failed: status=$($invocation.Status), response=$($invocation.ResponseCode)"
    }
    return $invocation
}

foreach ($command in @('aws', 'terraform', 'tar.exe')) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) { throw "Missing required local command: $command" }
}

$TerraformDirectory = (Resolve-Path $TerraformDirectory).Path
$inventoryRaw = Invoke-Native terraform @("-chdir=$TerraformDirectory", 'output', '-json', 'inventory')
Write-Utf8NoBom -Path (Join-Path $ControllerEvidence 'terraform_inventory.json') -Content $inventoryRaw
$inventory = $inventoryRaw | ConvertFrom-Json

$identityRaw = Invoke-Native aws @('sts', 'get-caller-identity', '--region', $inventory.region)
Write-Utf8NoBom -Path (Join-Path $ControllerEvidence 'caller_identity.json') -Content $identityRaw
$identity = $identityRaw | ConvertFrom-Json
if ($identity.Account -ne $inventory.account_id) { throw 'AWS account does not match Terraform inventory.' }
if ($identity.Arn -notmatch ':assumed-role/' -and $identity.Arn -notmatch ':user/AWSReservedSSO_') {
    throw "Refusing long-lived IAM-user deployment identity: $($identity.Arn). Use an assumed role or IAM Identity Center."
}

if ($Phase -eq 'Final') {
    if (-not $PilotSummary) { throw 'Final requires -PilotSummary after explicit pilot review.' }
    $pilot = Get-Content -Raw -LiteralPath (Resolve-Path $PilotSummary) | ConvertFrom-Json
    if ($pilot.profile -ne 'pilot' -or $pilot.n_runs -ne 3 -or $pilot.empirical -ne $true) {
        throw 'Pilot summary did not pass the profile/n_runs/empirical acceptance gate.'
    }
}

$bundlePath = Join-Path $ControllerEvidence 'runtime.tar.gz'
Invoke-Native tar.exe @('-czf', $bundlePath, '-C', $RepoRoot, 'experiment.yaml', 'scripts', 'ebpf') | Out-Null
$bundleHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $bundlePath).Hash.ToLowerInvariant()
$bundleKey = "bundles/$bundleHash.tar.gz"
Invoke-Native aws @(
    's3', 'cp', $bundlePath, "s3://$($inventory.artifact_bucket)/$bundleKey",
    '--region', $inventory.region, '--sse', 'aws:kms', '--sse-kms-key-id', $inventory.kms_key_arn
) | Out-Null

$stageCommand = @"
set -euo pipefail
release=/opt/nt531/releases/$bundleHash
mkdir -p "`$release"
aws s3 cp 's3://$($inventory.artifact_bucket)/$bundleKey' /tmp/nt531-runtime.tar.gz --region '$($inventory.region)'
printf '%s  %s\n' '$bundleHash' /tmp/nt531-runtime.tar.gz | sha256sum -c -
tar -xzf /tmp/nt531-runtime.tar.gz -C "`$release"
find "`$release/scripts" "`$release/ebpf" -type f \( -name '*.sh' -o -name '*.py' -o -name '*.c' -o -name 'Makefile' \) -exec sed -i 's/\r$//' {} +
chmod 0755 "`$release/scripts/benchmark_runner.sh" "`$release/scripts/preflight_check.sh" "`$release/scripts/dut_server_setup.sh" "`$release/ebpf/ebpf_loader.sh"
ln -sfn "`$release" /opt/capstone.next
mv -Tf /opt/capstone.next /opt/capstone
"@

foreach ($node in @($inventory.client, $inventory.server_b1, $inventory.server_b2)) {
    Invoke-Ssm -InstanceId $node.instance_id -Command $stageCommand -Label "stage_$($node.instance_id)" -Region $inventory.region | Out-Null
}

$exports = @"
export ALLOWED_ACCOUNT_ID='$($inventory.account_id)'
export CLIENT_INSTANCE_ID='$($inventory.client.instance_id)'
export TARGET_PEERING_INSTANCE_ID='$($inventory.server_b1.instance_id)'
export TARGET_TGW_INSTANCE_ID='$($inventory.server_b2.instance_id)'
export DUT_INSTANCE_ID='$($inventory.server_b1.instance_id)'
export TARGET_PEERING_IP='$($inventory.server_b1.private_ip)'
export TARGET_TGW_IP='$($inventory.server_b2.private_ip)'
export AMI_ID='$($inventory.ami_id)'
export INSTANCE_TYPE='$($inventory.instance_type)'
export CLIENT_ROUTE_TABLE_ID='$($inventory.client_route_table_id)'
export PEERING_ROUTE_TABLE_ID='$($inventory.peering_route_table_id)'
export TGW_ROUTE_TABLE_ID='$($inventory.tgw_route_table_id)'
export PEERING_CONNECTION_ID='$($inventory.peering_connection_id)'
export TRANSIT_GATEWAY_ID='$($inventory.transit_gateway_id)'
export SERVER_SECURITY_GROUP_ID='$($inventory.server_security_group_id)'
"@

if (-not $ExperimentId) {
    $prefix = $Phase.ToLowerInvariant()
    $ExperimentId = "${prefix}_$ControllerRunId"
}
$prospectiveResult = if ($Phase -eq 'Preflight') {
    Join-Path $ResultsRoot "preflight\$ExperimentId"
} else {
    Join-Path $ResultsRoot $ExperimentId
}
if (Test-Path -LiteralPath $prospectiveResult) { throw "Refusing to overwrite $prospectiveResult" }

$python = $null
if ($Phase -ne 'Preflight') {
    $python = Get-Command python3.14 -ErrorAction SilentlyContinue
    if (-not $python) { $python = Get-Command python -ErrorAction Stop }
}
if ($Phase -eq 'Final') {
    $finalSummary = Join-Path $RepoRoot 'results\final_summary.json'
    if (Test-Path -LiteralPath $finalSummary) { throw "Refusing to overwrite $finalSummary" }
    Invoke-Native $python.Source @('-c', 'import matplotlib') | Out-Null
}

if ($Phase -eq 'Preflight') {
    $remoteRelative = "results/mode_b/preflight/$ExperimentId"
    $runCommand = @"
set -euo pipefail
cd /opt/capstone
$exports
bash scripts/preflight_check.sh --scope aws --profile pilot --output-dir '/opt/capstone/$remoteRelative' \
  --account-id "`$ALLOWED_ACCOUNT_ID" --client-instance-id "`$CLIENT_INSTANCE_ID" \
  --peering-instance-id "`$TARGET_PEERING_INSTANCE_ID" --tgw-instance-id "`$TARGET_TGW_INSTANCE_ID" \
  --peering-ip "`$TARGET_PEERING_IP" --tgw-ip "`$TARGET_TGW_IP" --expected-ami-id "`$AMI_ID" \
  --expected-instance-type "`$INSTANCE_TYPE" --client-route-table-id "`$CLIENT_ROUTE_TABLE_ID" \
  --peering-route-table-id "`$PEERING_ROUTE_TABLE_ID" --tgw-route-table-id "`$TGW_ROUTE_TABLE_ID" \
  --peering-connection-id "`$PEERING_CONNECTION_ID" --transit-gateway-id "`$TRANSIT_GATEWAY_ID" \
  --server-security-group-id "`$SERVER_SECURITY_GROUP_ID"
tar -czf /tmp/$ExperimentId.tar.gz -C /opt/capstone '$remoteRelative'
aws s3 cp /tmp/$ExperimentId.tar.gz 's3://$($inventory.artifact_bucket)/runs/$ExperimentId.tar.gz' --region '$($inventory.region)' --sse aws:kms --sse-kms-key-id '$($inventory.kms_key_arn)'
"@
} else {
    $profileName = if ($Phase -eq 'Pilot') { 'pilot' } else { 'final' }
    $remoteRelative = "results/mode_b/$ExperimentId"
    $runCommand = @"
set -euo pipefail
cd /opt/capstone
$exports
bash scripts/benchmark_runner.sh --execute --profile '$profileName' --experiment-id '$ExperimentId'
tar -czf /tmp/$ExperimentId.tar.gz -C /opt/capstone '$remoteRelative'
aws s3 cp /tmp/$ExperimentId.tar.gz 's3://$($inventory.artifact_bucket)/runs/$ExperimentId.tar.gz' --region '$($inventory.region)' --sse aws:kms --sse-kms-key-id '$($inventory.kms_key_arn)'
"@
}

Invoke-Ssm -InstanceId $inventory.client.instance_id -Command $runCommand -Label "run_$ExperimentId" -Region $inventory.region | Out-Null

$download = Join-Path $ControllerEvidence "$ExperimentId.tar.gz"
Invoke-Native aws @('s3', 'cp', "s3://$($inventory.artifact_bucket)/runs/$ExperimentId.tar.gz", $download, '--region', $inventory.region) | Out-Null
Invoke-Native tar.exe @('-xzf', $download, '-C', $RepoRoot) | Out-Null

if ($Phase -ne 'Preflight') {
    $experimentDirectory = Join-Path $ResultsRoot $ExperimentId
    $summaryDirectory = Join-Path $experimentDirectory 'summary'
    New-Item -ItemType Directory -Path $summaryDirectory -Force | Out-Null
    $summaryPath = Join-Path $summaryDirectory 'mode_b_summary.json'
    Invoke-Native $python.Source @((Join-Path $PSScriptRoot 'analyze_mode_b.py'), '--experiment-dir', $experimentDirectory, '--output-json', $summaryPath) | Out-Null
    if ($Phase -eq 'Final') {
        Invoke-Native $python.Source @((Join-Path $PSScriptRoot 'generate_mode_b_graphs.py'), '--summary', $summaryPath, '--output-dir', (Join-Path $experimentDirectory 'graphs')) | Out-Null
        Copy-Item -LiteralPath $summaryPath -Destination $finalSummary
    }
    Write-Output "SUMMARY=$summaryPath"
}

Write-Output "AWS_CONTROLLER=PASS phase=$Phase experiment_id=$ExperimentId evidence=$ControllerEvidence"
