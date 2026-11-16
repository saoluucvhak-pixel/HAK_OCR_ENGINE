<#[
Prepare the Windows Tesseract runtime needed by the offline EXE.
Run on a Windows BUILD MACHINE with a fully installed, licensed Tesseract distribution.
No download is performed. Do not embed it in the release without confirming its license.
#>
param([string]$TesseractHome = '')
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $TesseractHome) {
    $locations = @(
        "$env:ProgramFiles\Tesseract-OCR",
        "${env:ProgramFiles(x86)}\Tesseract-OCR"
    )
    $found = Get-Command tesseract.exe -ErrorAction SilentlyContinue
    if ($found) { $locations += (Split-Path -Parent $found.Source) }
    $TesseractHome = ($locations | Where-Object { $_ -and (Test-Path (Join-Path $_ 'tesseract.exe')) } | Select-Object -First 1)
}
if (-not $TesseractHome -or -not (Test-Path (Join-Path $TesseractHome 'tesseract.exe'))) {
    throw 'Tesseract for Windows not found. Install a legitimate x64 Tesseract 5 with Vietnamese + English language packs, then rerun with -TesseractHome C:\...'
}
$source = (Resolve-Path $TesseractHome).Path
$target = Join-Path $root 'vendor\tesseract'
# Prevent accidental copy to the source itself.
if ($source.TrimEnd('\') -ieq $target.TrimEnd('\')) {
    Write-Host "Tesseract is already in vendor/tesseract" -ForegroundColor Green
} else {
    New-Item -ItemType Directory -Force $target | Out-Null
    Get-ChildItem -LiteralPath $source -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $target -Recurse -Force
    }
}
foreach ($lang in @('vie','eng')) {
    $trained = Join-Path $target "tessdata\$lang.traineddata"
    if (-not (Test-Path $trained) -or (Get-Item $trained).Length -lt 1024) {
        throw "Tesseract language pack missing or invalid: $trained. Install/copy the correct $lang.traineddata from a trusted distribution."
    }
}
$env:TESSDATA_PREFIX = Join-Path $target 'tessdata'
$env:PATH = "$target;$env:PATH"
$exe = Join-Path $target 'tesseract.exe'
& $exe --version | Out-Host
if ($LASTEXITCODE -ne 0) { throw 'Bundled tesseract.exe cannot run' }
$langs = (& $exe --list-langs 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0 -or $langs -notmatch '(?m)^vie\r?$' -or $langs -notmatch '(?m)^eng\r?$') {
    throw "Bundled Tesseract failed to load vie and eng. Details: $langs"
}
$hash = (Get-FileHash -Algorithm SHA256 $exe).Hash
Write-Host "Bundled Tesseract OK: $exe" -ForegroundColor Green
Write-Host "Tesseract SHA256: $hash"
