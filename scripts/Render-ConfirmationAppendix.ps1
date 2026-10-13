#requires -Version 7.0
param()
$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$sourcePath = Join-Path $workspace 'docs\31-phu-luc-bang-chung-thong-ke.docx'
$outputDir = Join-Path $workspace 'tmp\confirmation-appendix-render'
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
$pdfPath = Join-Path $outputDir '31-phu-luc-bang-chung-thong-ke.pdf'
$renderInput = Join-Path $outputDir 'render-input.docx'
$sourceHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash
Copy-Item -LiteralPath $sourcePath -Destination $renderInput -Force
$word = $null
$document = $null
try {
    # Windows lacks bundled LibreOffice; use a separate hidden Word instance.
    # Render a disposable writable copy; PDF conversion of a read-only
    # document stalls in this Word version. Never save changes to the source.
    $word = New-Object -ComObject Word.Application
    Write-Output 'Hidden Word instance initialized'
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $document = $word.Documents.Open($renderInput, $false, $false)
    Write-Output 'Disposable appendix copy opened with macros disabled'
    # Page count is read from the exported PDF by the QA step.
    # Avoid ComputeStatistics, which can stall on the native equation fields.
    Write-Output 'Exporting PDF'
    # SaveAs2 PDF succeeds in this installed Word version; its fixed-format
    # export API stalled. The disposable copy is closed without saving.
    $document.SaveAs2($pdfPath, 17)
    [pscustomobject]@{Renderer='Microsoft Word';Version=$word.Version;PDF=$pdfPath} | ConvertTo-Json
} finally {
    if ($null -ne $document) { $document.Close(0); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($document) }
    if ($null -ne $word) { $word.Quit(0); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word) }
    if ((Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash -ne $sourceHash) { throw 'Source document changed during render' }
}
