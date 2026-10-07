# Requires applied management.tf and four Online SSM managed nodes.
# Prepares idle listeners, then checks nodes sequentially to avoid iperf server contention.
param(
    [string]$Profile = 'nt533-lab',
    [string]$Region = 'us-east-1',
    [ValidateSet('peering','tgw')][string]$Mode = 'peering',
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
# AWS CLI on Windows must emit Unicode systemd output as UTF-8 when redirected.
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$projectRoot = Split-Path $PSScriptRoot -Parent
$tfDirectory = Join-Path $projectRoot 'infra/terraform'
$raw = & terraform "-chdir=$tfDirectory" output -json
if ($LASTEXITCODE -ne 0) { throw 'Cannot read Terraform outputs.' }
$outputs = ($raw -join "`n") | ConvertFrom-Json
if ($outputs.routing.value.mode -ne $Mode) { throw 'Mode differs from applied Terraform output.' }
$instances = $outputs.instances.value
$tempDir = Join-Path $projectRoot 'tmp'
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
$runId = [guid]::NewGuid().ToString('N')
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Invoke-LabCommand([string]$Node, [string[]]$Commands, [string]$Stage) {
    $instanceId = $instances.$Node.id
    if (-not $instanceId) { throw "Missing instance ID: $Node" }
    $request = @{
        DocumentName = 'AWS-RunShellScript'
        InstanceIds = @($instanceId)
        TimeoutSeconds = 120
        Comment = "NT531 $Stage $Node $Mode"
        Parameters = @{ commands = $Commands; executionTimeout = @('600') }
    }
    $requestFile = Join-Path $tempDir "ssm-$runId-$Stage-$Node-request.json"
    [IO.File]::WriteAllText($requestFile, ($request | ConvertTo-Json -Depth 8), $utf8)
    $commandId = & aws ssm send-command --cli-input-json "file://$requestFile" --profile $Profile --region $Region --query Command.CommandId --output text --no-cli-pager
    if ($LASTEXITCODE -ne 0) { throw "SSM send failed: $Node" }
    $commandId = ($commandId -join '').Trim()
    Write-Output "SSM $Stage $Node command=$commandId"
    $deadline = (Get-Date).AddMinutes(12)
    do {
        Start-Sleep -Seconds 5
        # systemd's success messages on stderr contain Unicode arrows which some
        # AWS CLI Windows builds cannot serialize. Keep stdout/status here; full
        # stderr remains available in the AWS Run Command console by command ID.
        $response = & aws ssm get-command-invocation --command-id $commandId --instance-id $instanceId --profile $Profile --region $Region --query '{Status:Status,StandardOutputContent:StandardOutputContent,ResponseCode:ResponseCode,CommandId:CommandId,InstanceId:InstanceId}' --output json --no-cli-pager 2> (Join-Path $tempDir "ssm-$runId-poll-error.txt")
        if ($LASTEXITCODE -ne 0) { throw "Cannot read SSM invocation $commandId; inspect AWS Run Command before retrying." }
        $result = ($response -join "`n") | ConvertFrom-Json
        if ($result.Status -in @('Success','Failed','Cancelled','TimedOut')) {
            $resultFile = Join-Path $tempDir "ssm-$runId-$Stage-$Node-result.json"
            [IO.File]::WriteAllText($resultFile, ($response -join "`n"), $utf8)
            Write-Output $result.StandardOutputContent
            if ($result.Status -ne 'Success') {
                Write-Output $result.StandardErrorContent
                throw "SSM $Stage failed on $Node ($($result.Status)); result=$resultFile"
            }
            return
        }
    } while ((Get-Date) -lt $deadline)
    throw "Timed out waiting for $commandId; inspect AWS Run Command before retrying."
}

# Verify all nodes are Online before changing any instance.
$onlineRaw = & aws ssm describe-instance-information --profile $Profile --region $Region --output json --no-cli-pager
if ($LASTEXITCODE -ne 0) { throw 'Cannot query SSM registration.' }
$online = (($onlineRaw -join "`n") | ConvertFrom-Json).InstanceInformationList
foreach ($node in @('a','b','c','d')) {
    if (-not ($online | Where-Object { $_.InstanceId -eq $instances.$node.id -and $_.PingStatus -eq 'Online' })) {
        throw "Node $node is not Online in SSM yet. Check profile, agent and outbound connectivity."
    }
}
if (-not $CheckOnly) {
    $commands = @('set -eu')
    foreach ($filename in @('prepare-measurement.sh','setup-measurement-server.sh','check-connectivity.sh')) {
        $content = [IO.File]::ReadAllText((Join-Path $PSScriptRoot $filename)).Replace("`r`n", "`n")
        $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($content))
        $commands += "printf '%s' '$encoded' | base64 -d > /home/ec2-user/$filename"
        $commands += "chown ec2-user:ec2-user /home/ec2-user/$filename"
    }
    $commands += 'runuser -l ec2-user -c "bash /home/ec2-user/setup-measurement-server.sh"'
    foreach ($node in @('a','b','c','d')) { Invoke-LabCommand $node $commands 'setup' }
}
foreach ($node in @('a','b','c','d')) {
    Invoke-LabCommand $node @('set -eu', "runuser -l ec2-user -c 'bash /home/ec2-user/check-connectivity.sh $Mode'") 'connectivity'
}
