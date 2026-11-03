@echo off
setlocal
cd /d "%~dp0"
set "APP_NODE=node"
where node >nul 2>nul
if errorlevel 1 (
  if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" (
    set "APP_NODE=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
  )
)
"%APP_NODE%" scripts/build_windows.js
if errorlevel 1 (
  echo.
  echo Build failed. See README.md for the build prerequisites.
) else (
  echo.
  echo The installer and portable executable are in the release folder.
)
pause
