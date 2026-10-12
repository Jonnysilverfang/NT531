param(
    [ValidateSet('Init','Analyze','SelfTest','Block','Load')][string]$Action='Analyze',
    [ValidateRange(1,16)][int]$Block=1,
    [string]$Profile='nt533-lab',
    [string]$Python='C:\Users\MSI\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
)
$ErrorActionPreference='Stop'
if (-not (Test-Path -LiteralPath $Python)) { throw 'Provide an installed Python executable with -Python.' }
$runner=Join-Path $PSScriptRoot 'rtt-confirmation.py'
$arguments=@('-X','utf8',$runner,'--profile',$Profile)
switch ($Action) {
    'Init' {$arguments+='--init'}
    'Analyze' {$arguments+='--analyze'}
    'SelfTest' {$arguments+='--self-test'}
    'Block' {$arguments+=@('--block',"$Block")}
    'Load' {$arguments+='--load'}
}
& $Python @arguments
if ($LASTEXITCODE -ne 0) { throw 'RTT operation failed. Keep raw logs and inspect the cause before retrying.' }
