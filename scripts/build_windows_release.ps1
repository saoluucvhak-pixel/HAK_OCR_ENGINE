<#[
Build a real PyInstaller Windows EXE + optional Inno Setup EXE installer.
Run on Windows x64. BUILD HOST may connect to pip to prepare dependencies;
END USER application requires NO Internet.

powershell -ExecutionPolicy Bypass -File scripts\build_windows_release.ps1
powershell -ExecutionPolicy Bypass -File scripts\build_windows_release.ps1 -OfflineBuild
powershell -ExecutionPolicy Bypass -File scripts\build_windows_release.ps1 -PortableOnly
#>
param(
    [switch]$OfflineBuild,
    [switch]$PortableOnly,
    [switch]$Advanced,
    [string]$TesseractHome = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
if (-not [Environment]::Is64BitOperatingSystem) { throw 'Windows 64-bit required.' }
if ($PSVersionTable.PSEdition -ne 'Desktop' -and $PSVersionTable.PSEdition -ne 'Core') { throw 'PowerShell required.' }
$pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
if (-not $pythonLauncher) { throw 'Python Launcher py.exe missing. Install Python 3.11 x64 on the build PC.' }
& py -3.11 -c 'import sys; assert sys.maxsize > 2**32, "Python must be 64 bit"'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 x64 missing.' }

& (Join-Path $PSScriptRoot 'prepare_windows_runtime.ps1') -TesseractHome $TesseractHome
if ($LASTEXITCODE -ne 0) { throw 'Could not bundle Tesseract' }

if ($Advanced) {
    foreach ($model in @('paddle_detection','paddle_recognition','docling','doc_unwarp','handwriting')) {
        $folder = Join-Path $root "vendor\models\$model"
        if (-not (Test-Path $folder) -or @((Get-ChildItem $folder -File -Recurse -ErrorAction SilentlyContinue)).Count -eq 0) {
            throw "Advanced model missing: $folder. This build cannot claim advanced model support without weights."
        }
    }
}
if (-not (Test-Path '.venv\Scripts\python.exe')) { & py -3.11 -m venv .venv }
if ($LASTEXITCODE -ne 0) { throw 'Creating venv failed.' }
$python = Join-Path $root '.venv\Scripts\python.exe'
$req = if ($Advanced) { 'requirements-advanced.txt' } else { 'requirements.txt' }
if ($OfflineBuild) {
    if (-not (Test-Path wheelhouse)) { throw 'OfflineBuild requires a wheelhouse folder (all wheels including PyInstaller/pytest).' }
    & $python -m pip install --disable-pip-version-check --no-index --find-links wheelhouse -r $req pytest pyinstaller
} else {
    & $python -m pip install --disable-pip-version-check -r $req pytest pyinstaller
}
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $python -m pytest tests -q
if ($LASTEXITCODE -ne 0) { throw 'Automated tests failed. Build cancelled.' }
& $python -m compileall -q hak_ocr run.py cli.py
if ($LASTEXITCODE -ne 0) { throw 'Python compile check failed.' }

$diagnostic = Join-Path $root 'validation\prebuild-check.json'
& $python run.py --self-test $diagnostic --require-bundled
if ($LASTEXITCODE -ne 0) { throw "Python self-test failed: $diagnostic" }
if (-not (Test-Path $diagnostic) -or -not (Get-Content $diagnostic -Raw | ConvertFrom-Json).ok) { throw 'Self-test JSON not passed.' }

$pyArgs = @('--noconfirm', '--clean', '--onedir', '--windowed', '--name', 'HAKSmartOCRAI',
    '--add-data', 'vendor/tesseract;vendor/tesseract',
    '--collect-all', 'cv2', '--collect-all', 'pypdfium2', '--collect-all', 'fitz',
    '--collect-submodules', 'pytesseract')
if ($Advanced) {
    $pyArgs += @('--add-data', 'vendor/models;vendor/models',
        '--collect-all', 'paddleocr','--collect-all','paddle',
        '--collect-all','docling','--collect-all','transformers','--collect-all','torch')
}
$pyArgs += 'run.py'
& $python -m PyInstaller @pyArgs
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller packaging failed.' }

$exe = Join-Path $root 'dist\HAKSmartOCRAI\HAKSmartOCRAI.exe'
if (-not (Test-Path $exe)) { throw "EXE not found: $exe" }
# Crucial! Executing built EXE checks where PyInstaller actually placed
# the Tesseract binary and whether its language data and native DLLs load.
$smoke = Join-Path $root 'validation\packaged-check.json'
if (Test-Path $smoke) { Remove-Item $smoke -Force }
$frozenProcess = Start-Process -FilePath $exe -ArgumentList @('--self-test', $smoke, '--require-bundled') -Wait -PassThru -NoNewWindow
if ($frozenProcess.ExitCode -ne 0) { throw "Frozen EXE smoke test returned error: $($frozenProcess.ExitCode)" }
if (-not (Test-Path $smoke)) { throw 'Frozen EXE failed to write diagnostics.' }
$report = Get-Content $smoke -Raw | ConvertFrom-Json
if (-not $report.ok -or -not $report.frozen) { throw "Packaged EXE failed: $smoke" }

$version='1.2.0-alpha'
$manifest = [ordered]@{
    version=$version; channel='alpha'; built_at=(Get-Date).ToUniversalTime().ToString('o')
    architecture='x64'; advanced=$Advanced.IsPresent
    executable_sha256=(Get-FileHash -Algorithm SHA256 $exe).Hash
    packaged_self_test=$report
    python=( & $python --version 2>&1 | Out-String).Trim()
    installed_packages=(& $python -m pip freeze | Out-String).Trim()
}
$manifest | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 (Join-Path $root 'dist\HAKSmartOCRAI\release-manifest.json')

# portable ZIP contains an .exe AND all native libraries/assets.
$portable = Join-Path $root "dist\HAKSmartOCRAI-Portable-$version-Windows-x64.zip"
if (Test-Path $portable) { Remove-Item $portable -Force }
Compress-Archive -Path (Join-Path $root 'dist\HAKSmartOCRAI') -DestinationPath $portable -Force
Write-Host "PORTABLE EXE: $exe" -ForegroundColor Green
Write-Host "PORTABLE ZIP: $portable" -ForegroundColor Green

if (-not $PortableOnly) {
    $compiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if (-not $compiler) {
        $candidates=@("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe")
        $compiler=($candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1)
    } else { $compiler = $compiler.Source }
    if (-not $compiler) { throw 'Inno Setup 6 (ISCC.exe) missing. Install it on build PC or rerun with -PortableOnly.' }
    & $compiler "/DMyAppVersion=$version" 'scripts\HAKSmartOCRAI.iss'
    if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed.' }
    Write-Host "SETUP EXE: dist\HAKSmartOCRAI-Setup-$version.exe" -ForegroundColor Green
}
Write-Host 'Release build passed local smoke tests. A real clean Windows OFFLINE acceptance test is still required.' -ForegroundColor Yellow
