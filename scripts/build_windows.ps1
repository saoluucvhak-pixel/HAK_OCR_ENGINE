# HAK Smart OCR AI 1.0 — Windows x64 offline builder
# Run ON Windows, in PowerShell, from project root with an ALREADY prepared wheelhouse.
# Example: powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
if (-not (Test-Path 'wheelhouse')) { throw 'Missing wheelhouse. Prepare wheels on a separate build machine.' }
if (-not (Test-Path 'vendor/tesseract/tesseract.exe')) { throw 'Missing vendor/tesseract/tesseract.exe' }
foreach ($lang in @('vie','eng')) {
    if (-not (Test-Path "vendor/tesseract/tessdata/$lang.traineddata")) {
        throw "Missing Tesseract model $lang.traineddata"
    }
}
py -3.11 -m venv .venv
$python=Join-Path $root '.venv/Scripts/python.exe'
& $python -m pip install --no-index --find-links wheelhouse -r requirements.txt pyinstaller pytest
if ($LASTEXITCODE -ne 0) { throw 'Offline dependency installation failed' }
& $python -m pytest tests -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
& $python -m PyInstaller --clean --noconfirm --windowed --onedir `
    --name HAKSmartOCRAI --add-data 'vendor/tesseract;vendor/tesseract' `
    --collect-submodules pytesseract --collect-all cv2 --collect-all fitz `
    run.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }
Write-Host 'Build completed at dist/HAKSmartOCRAI/HAKSmartOCRAI.exe' -ForegroundColor Green
Write-Host 'MANDATORY: test offline PDF/image OCR and GUI on a clean Windows machine.' -ForegroundColor Yellow
