# Execute on an OFFLINE Windows 10/11 x64 machine, from scripts/.
# Requires a prepared offline wheelhouse and local model folders. This script
# is a build recipe; it has not been executed in the current Linux environment.
param([switch]$IncludeHandwriting, [switch]$IncludeGGUF)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
if (-not (Test-Path 'wheelhouse')) {throw 'Missing offline wheelhouse'}
if (-not (Test-Path 'vendor/tesseract/tesseract.exe')) {throw 'Missing bundled Tesseract'}
foreach($lang in @('vie','eng')) {
    if(-not (Test-Path "vendor/tesseract/tessdata/$lang.traineddata")) {throw "Missing tessdata: $lang"}
}
foreach($model in @('paddle_detection','paddle_recognition','docling','doc_unwarp')) {
    if(-not (Test-Path "vendor/models/$model")) {throw "Missing model: $model"}
}
if($IncludeHandwriting -and -not (Test-Path 'vendor/models/handwriting/config.json')) {
    throw 'Missing handwriting model config.json'
}
if($IncludeGGUF -and -not (Get-ChildItem 'vendor/models/evidence_llm/*.gguf' -ErrorAction SilentlyContinue)) {
    throw 'Missing GGUF model'
}
if (-not (Test-Path '.venv/Scripts/python.exe')) {py -3.11 -m venv .venv}
$python=Join-Path $root '.venv/Scripts/python.exe'
& $python -m pip install --no-index --find-links wheelhouse -r requirements-advanced.txt pyinstaller pytest
if($LASTEXITCODE -ne 0){throw 'Offline installation failed'}
if($IncludeGGUF){
    & $python -m pip install --no-index --find-links wheelhouse llama-cpp-python
    if($LASTEXITCODE -ne 0){throw 'llama-cpp-python wheel missing'}
}
& $python -m pytest tests -q
if($LASTEXITCODE -ne 0){throw 'Tests failed'}
& $python cli.py advanced-check
if($LASTEXITCODE -ne 0){throw 'Advanced checks failed'}
$collect=@('--collect-all','paddleocr','--collect-all','paddle',
    '--collect-all','docling','--collect-all','transformers','--collect-all','torch',
    '--collect-all','fitz','--collect-all','cv2')
if($IncludeGGUF) { $collect+=@('--collect-all','llama_cpp') }
& $python -m PyInstaller --clean --noconfirm --windowed --onedir --name HAKSmartOCRAI `
    --add-data 'vendor/tesseract;vendor/tesseract' `
    --add-data 'vendor/models;vendor/models' @collect run.py
if($LASTEXITCODE -ne 0){throw 'PyInstaller failed'}
Write-Host 'Built: dist/HAKSmartOCRAI/HAKSmartOCRAI.exe' -ForegroundColor Green
Write-Warning 'IMPORTANT: test on CLEAN OFFLINE WINDOWS, including Paddle/Docling/UVDoc real weights, OCR output, EXE restart, backup and restoration.'
