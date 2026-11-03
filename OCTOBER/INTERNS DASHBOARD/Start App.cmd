@echo off
cd /d "%~dp0"
if exist "%~dp0release\win-unpacked\Intern Program.exe" (
  start "" "%~dp0release\win-unpacked\Intern Program.exe"
  exit /b
)
where node >nul 2>nul
if errorlevel 1 (
  if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" (
    "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" server.js --open
    if errorlevel 1 pause
    exit /b
  ) else (
    echo Install Node.js 20 or newer, then run npm install in this folder.
    pause
    exit /b 1
  )
)
node server.js --open
if errorlevel 1 pause
