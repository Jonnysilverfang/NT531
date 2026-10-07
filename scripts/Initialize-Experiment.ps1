# Run from Windows after Terraform apply and after all four instances are ready.
# Keeps SSH host keys in tmp/known_hosts; does not disable host identity checking.
param([string]$KeyPath = '', [switch]$CheckOnly, [ValidateSet('peering','tgw')][string]$Mode = 'peering')
$ErrorActionPreference = 'Stop'
$sshCommand = Join-Path $env:WINDIR 'System32/OpenSSH/ssh.exe'
$scpCommand = Join-Path $env:WINDIR 'System32/OpenSSH/scp.exe'
$projectRoot = Split-Path $PSScriptRoot -Parent
if (-not $KeyPath) { $KeyPath = Join-Path $projectRoot 'nt531-key.pem' }
if (-not (Test-Path -LiteralPath $KeyPath)) { throw 'Private key not found.' }
$tfDirectory = Join-Path $projectRoot 'infra/terraform'
$outputRaw = & terraform "-chdir=$tfDirectory" output -json instances
if ($LASTEXITCODE -ne 0) { throw 'Cannot read Terraform outputs.' }
$instances = ($outputRaw -join "`n") | ConvertFrom-Json
$routingRaw = & terraform "-chdir=$tfDirectory" output -json routing
if ($LASTEXITCODE -ne 0) { throw 'Cannot read routing outputs.' }
$routing = ($routingRaw -join "`n") | ConvertFrom-Json
if ($routing.mode -ne $Mode) { throw 'Requested mode differs from applied Terraform output.' }
$tempDir = Join-Path $projectRoot 'tmp'
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
$knownHosts = (Join-Path $tempDir 'known_hosts').Replace('\','/')
$sshOptions = @('-i', $KeyPath, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', '-o', 'StrictHostKeyChecking=accept-new', '-o', "UserKnownHostsFile=$knownHosts")
# First prepare ALL receivers, then check the mesh from each node.
if (-not $CheckOnly) {
    foreach ($node in @('a','b','c','d')) {
        $endpoint = $instances.$node.public_ip
        if (-not $endpoint) { throw "No EIP output for $node" }
        $remote = "ec2-user@$endpoint"
        & $scpCommand @sshOptions (Join-Path $PSScriptRoot 'prepare-measurement.sh') (Join-Path $PSScriptRoot 'setup-measurement-server.sh') (Join-Path $PSScriptRoot 'check-connectivity.sh') "${remote}:/home/ec2-user/"
        if ($LASTEXITCODE -ne 0) { throw "Upload failed: $node" }
        & $sshCommand @sshOptions $remote 'bash ~/setup-measurement-server.sh'
        if ($LASTEXITCODE -ne 0) { throw "Setup failed: $node" }
    }
}
foreach ($node in @('a','b','c','d')) {
    $endpoint = $instances.$node.public_ip
    if (-not $endpoint) { throw "No EIP output for $node" }
    Write-Output "Checking $node ($Mode)"
    & $sshCommand @sshOptions "ec2-user@$endpoint" "bash ~/check-connectivity.sh $Mode"
    if ($LASTEXITCODE -ne 0) { throw "Connectivity failed: $node" }
}
