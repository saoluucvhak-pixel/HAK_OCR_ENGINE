@echo off
setlocal
cd /d "%~dp0"
echo.
echo    HAK SMART OCR AI - Windows x64 EXE Builder
 echo    Requires Python 3.11 x64, Tesseract 5 vie+eng, Inno Setup 6
 echo    Build machine needs internet for Python packages, not the client app.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\build_windows_release.ps1"
set CODE=%ERRORLEVEL%
if NOT "%CODE%"=="0" (
    echo.
    echo BUILD FAILED - please read the detailed error above.
    pause
    exit /b %CODE%
)
echo.
echo BUILD SUCCEEDED. Look in dist\ for .exe and setup.
explorer.exe "dist"
pause
