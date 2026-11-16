# Internet allowed ONLY on separate Windows build machine, not on client PC.
$ErrorActionPreference='Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
New-Item -ItemType Directory -Force wheelhouse | Out-Null
py -3.11 -m pip download -r requirements.txt -d wheelhouse
py -3.11 -m pip download pyinstaller pytest -d wheelhouse
Write-Host 'Copy wheelhouse and a licensed Tesseract Windows portable distribution to offline build machine.'
