#requires -Version 7.0
param()
$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$source = Join-Path $workspace 'nt531-key.pem'
$folder = Join-Path $workspace 'tmp\ssh-download-private'
$target = Join-Path $folder 'nt531.pem'
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw 'Existing NT531 SSH key is missing; do not generate a new cohort key' }
New-Item -ItemType Directory -Path $folder -Force | Out-Null
$owner = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
$acl = [System.Security.AccessControl.FileSecurity]::new()
$acl.SetOwner($owner)
$acl.SetAccessRuleProtection($true, $false)
$acl.AddAccessRule([System.Security.AccessControl.FileSystemAccessRule]::new($owner, 'Read', 'Allow'))
if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
    Copy-Item -LiteralPath $source -Destination $target
    Set-Acl -LiteralPath $target -AclObject $acl
}
$actual = Get-Acl -LiteralPath $target
if (-not $actual.AreAccessRulesProtected -or $actual.Access.Count -ne 1 -or $actual.Access[0].IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]) -ne $owner) { throw 'Private copy ACL verification failed' }
if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $target).Hash) { throw 'Private key copy mismatch' }
Write-Output 'Existing key copied privately; only current user can read it. Original key untouched.'
