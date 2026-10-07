param()
$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$resultsRoot = Join-Path $workspace 'results'
$backupRoot = Join-Path $workspace 'backups'
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$zipPath = Join-Path $backupRoot "nt531-results-$stamp.zip"
if (Test-Path -LiteralPath $zipPath) { throw 'Backup name already exists; rerun after one second.' }
$resultFiles = @(Get-ChildItem -LiteralPath $resultsRoot -Recurse -File)
if ($resultFiles.Count -eq 0) { throw 'No result files found.' }
$files = @($resultFiles) + @(Get-ChildItem -LiteralPath (Join-Path $workspace 'docs') -Recurse -File) + @(Get-Item -LiteralPath (Join-Path $workspace 'README.md'))
$files += @(Get-Item -LiteralPath (Join-Path $workspace 'scripts\build-results-report.py'), (Join-Path $workspace 'scripts\Render-ResultsReport.ps1'), (Join-Path $workspace 'scripts\report_formulas.py'), (Join-Path $workspace 'scripts\report_context.py'), (Join-Path $workspace 'scripts\verify-results-for-review.py'))
$payload = @($files | Sort-Object FullName | ForEach-Object {
    [pscustomobject]@{ source=$_.FullName; entry=$_.FullName.Substring($workspace.Length+1).Replace('\','/'); bytes=$_.Length; sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
})
$rawCounts = @()
foreach ($session in @(@{mode='peering';epoch='1791293390'},@{mode='tgw';epoch='1791296141'})) {
    $relative = "results/formal/$($session.mode)/tcp-fanin/audit-$($session.epoch)/full-backup-manifest.json"
    $manifest = Get-Content -LiteralPath (Join-Path $workspace $relative) -Raw | ConvertFrom-Json
    foreach ($item in $manifest) {
        $folder = Join-Path $workspace $item.folder
        $count = @(Get-ChildItem -LiteralPath $folder -File).Count
        if ($count -ne $item.files) { throw "Raw file count mismatch: $folder" }
        $archiveRelative = "tmp/fanin-$($session.mode)-backup-$($item.node).tar.gz"
        $sourceArchive = Get-Item -LiteralPath (Join-Path $workspace $archiveRelative)
        $archiveHash = (Get-FileHash -LiteralPath $sourceArchive.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($archiveHash -ne $item.archive_sha256 -or $sourceArchive.Length -ne $item.archive_bytes) { throw "Source archive mismatch: $archiveRelative" }
        $payload += [pscustomobject]@{ source=$sourceArchive.FullName; entry="source-archives/$($session.mode)-fanin-$($session.epoch)-$($item.node).tar.gz"; bytes=$sourceArchive.Length; sha256=$archiveHash }
        $rawCounts += [pscustomobject]@{mode=$session.mode;epoch=$session.epoch;node=$item.node;files=$count;folder=$item.folder.Replace('\','/')}
    }
}
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$manifestData = [pscustomobject]@{
    created_utc=$stamp
    scope='All local results, project docs, root README, report builder/render scripts, and eight verified original fan-in archives. Contains existing duplicate/pilot files; duplicates are not independent measurements.'
    result_file_count=$resultFiles.Count
    fanin_raw_files=($rawCounts | Measure-Object files -Sum).Sum
    fanin_sessions=$rawCounts
    files=@($payload | Select-Object entry,bytes,sha256)
}
$manifestBytes = [Text.Encoding]::UTF8.GetBytes(($manifestData | ConvertTo-Json -Depth 8))
$readme = @'
NT531 - Results backup

This ZIP contains all result files currently saved in the workspace,
project documentation, report builder/render scripts and eight original fan-in archives verified against
the EC2 archive SHA256 values. BACKUP-MANIFEST.json lists every payload
file, byte size and SHA256. Empty stderr files are preserved.

Canonical fan-in results:
  results/formal/peering/tcp-fanin/A, B, C, D (session 1791293390)
  results/formal/tgw/tcp-fanin/A, B, C, D (session 1791296141)
Each session contains 146 raw files (47 A, 5 B, 47 C, 47 D).

Other principal results:
  results/pilot-peering/rtt-idle-a-b/nt531-results/
  results/formal/tgw/rtt-idle-a-b/nt531-results/
  results/formal/peering/tcp-single-a-b/A and B
  results/formal/tgw/tcp-single-a-b/A and B

The snapshot also preserves older pilot/connectivity files and duplicate
manual copies. These must not be counted as independent repeated runs.
Two-pair Peering is supplemental; a complete raw backup for that session
has not been verified. This ZIP contains only files already saved locally.

Extract the ZIP to an empty folder to view the saved data. Keep a copy on
another device or storage service. Local files and the ZIP on the same
disk are not protection against loss of that disk.
'@
$readmeBytes = [Text.Encoding]::UTF8.GetBytes($readme)
$zip = [IO.Compression.ZipFile]::Open($zipPath,[IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($file in $payload) {
        [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip,$file.source,$file.entry,[IO.Compression.CompressionLevel]::Optimal) | Out-Null
    }
    foreach ($meta in @(@{name='BACKUP-MANIFEST.json';data=$manifestBytes},@{name='BACKUP-README.txt';data=$readmeBytes})) {
        $stream = $zip.CreateEntry($meta.name).Open()
        try { $stream.Write($meta.data,0,$meta.data.Length) } finally { $stream.Dispose() }
    }
} finally { $zip.Dispose() }
$zip = [IO.Compression.ZipFile]::OpenRead($zipPath)
try {
    if ($zip.Entries.Count -ne $payload.Count+2) { throw 'ZIP entry count mismatch.' }
    foreach ($file in $payload) {
        $entry = $zip.GetEntry($file.entry)
        if (-not $entry -or $entry.Length -ne $file.bytes) { throw "ZIP file missing or truncated: $($file.entry)" }
        $stream = $entry.Open()
        $hasher = [Security.Cryptography.SHA256]::Create()
        try { $hash = ([BitConverter]::ToString($hasher.ComputeHash($stream))).Replace('-','').ToLowerInvariant() } finally { $stream.Dispose(); $hasher.Dispose() }
        if ($hash -ne $file.sha256) { throw "ZIP checksum mismatch: $($file.entry)" }
    }
} finally { $zip.Dispose() }
$zipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
"$zipHash  $([IO.Path]::GetFileName($zipPath))" | Set-Content -LiteralPath "$zipPath.sha256" -Encoding UTF8
[pscustomobject]@{zip=$zipPath;bytes=(Get-Item -LiteralPath $zipPath).Length;result_files=$resultFiles.Count;fanin_raw_files=$manifestData.fanin_raw_files;verified_payload_files=$payload.Count;sha256=$zipHash} | ConvertTo-Json
