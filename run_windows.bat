@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" run.py
) else (
  echo Chua co .venv. Vui long doc README.md de cai thu vien offline.
  pause
)
endlocal
