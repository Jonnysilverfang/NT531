param(
    [string]$Profile = 'nt533-lab',
    [string]$Region = 'us-east-1'
)
$ErrorActionPreference = 'Stop'
# Read IDs from the active configuration's state; do not rely on cached public IPs.
$terraformDirectory = Join-Path $PSScriptRoot '../infra/terraform'
$raw = & terraform "-chdir=$terraformDirectory" show -json
if ($LASTEXITCODE -ne 0) { throw 'Cannot read Terraform state.' }
# Parse locally; never print the full state, which may contain sensitive values.
$state = ($raw -join "`n") | ConvertFrom-Json
$instanceIds = @($state.values.root_module.resources |
    Where-Object { $_.mode -eq 'managed' -and $_.type -eq 'aws_instance' -and $_.name -in @('a', 'b', 'extra') } |
    ForEach-Object { $_.values.id })
if ($instanceIds.Count -eq 0) { throw 'No experiment EC2 instances found in state.' }
$rawInstances = & aws ec2 describe-instances --profile $Profile --region $Region --instance-ids @instanceIds --output json --no-cli-pager
if ($LASTEXITCODE -ne 0) { throw 'AWS lookup failed. Check profile login and Region.' }
$response = ($rawInstances -join "`n") | ConvertFrom-Json
foreach ($reservation in $response.Reservations) {
    foreach ($instance in $reservation.Instances) {
        [pscustomobject]@{
            Name = ($instance.Tags | Where-Object Key -eq 'Name').Value
            ID = $instance.InstanceId
            State = $instance.State.Name
            PrivateIP = $instance.PrivateIpAddress
            PublicIP = $instance.PublicIpAddress
            KeyName = $instance.KeyName
        }
    }
}
