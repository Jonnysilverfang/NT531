param()
$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$inputPath = Join-Path $workspace 'docs\13-chuong-ket-qua.docx'
$qaPath = Join-Path $workspace 'tmp\report-render'
New-Item -ItemType Directory -Path $qaPath -Force | Out-Null
$pdfPath = Join-Path $qaPath '13-chuong-ket-qua.pdf'
$word = $null
$document = $null
try {
    # A separate hidden Word automation instance renders a read-only copy.
    $word = New-Object -ComObject Word.Application
    Write-Output 'Word automation initialized'
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $document = $word.Documents.Open($inputPath, $false, $true)
    Write-Output 'Read-only document opened'
    $document.Repaginate()
    $pages = $document.ComputeStatistics(2)
    $document.ExportAsFixedFormat($pdfPath, 17)
    [pscustomobject]@{Renderer='Microsoft Word';Version=$word.Version;Pages=$pages;PDF=$pdfPath} | ConvertTo-Json
} finally {
    if ($null -ne $document) { $document.Close(0); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($document) }
    if ($null -ne $word) { $word.Quit(0); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word) }
}
