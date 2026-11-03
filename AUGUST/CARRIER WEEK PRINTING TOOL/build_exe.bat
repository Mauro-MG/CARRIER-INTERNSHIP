@echo off
setlocal
cd /d "%~dp0"

echo Checking the label template...
if not exist "assets\label_template.png" (
    echo ERROR: assets\label_template.png is missing.
    exit /b 1
)

if not exist ".build-venv\Scripts\python.exe" (
    echo Creating an isolated build environment...
    python -m venv .build-venv
    if errorlevel 1 exit /b 1
)

echo Installing build dependencies...
".build-venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements-build.txt
if errorlevel 1 (
    echo ERROR: Unable to install the build dependencies.
    exit /b 1
)

echo Building StudentLabelPrinter.exe...
".build-venv\Scripts\python.exe" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onedir ^
    --windowed ^
    --contents-directory _internal ^
    --name StudentLabelPrinter ^
    --add-data "assets;assets" ^
    --add-data "config.json;." ^
    --collect-all ttkbootstrap ^
    --hidden-import win32con ^
    --hidden-import win32print ^
    --hidden-import win32ui ^
    --hidden-import win32com.client ^
    --hidden-import pythoncom ^
    --hidden-import pywintypes ^
    --hidden-import PIL.ImageWin ^
    --exclude-module tests ^
    app.py

if errorlevel 1 (
    echo.
    echo BUILD FAILED.
    exit /b 1
)

echo Copying writable application data beside the executable...
if not exist "dist\StudentLabelPrinter\database" mkdir "dist\StudentLabelPrinter\database"
copy /Y "database\students.xlsx" "dist\StudentLabelPrinter\database\students.xlsx" >nul
if exist "database\student_id_map.json" copy /Y "database\student_id_map.json" "dist\StudentLabelPrinter\database\student_id_map.json" >nul
if exist "database\print_history.json" copy /Y "database\print_history.json" "dist\StudentLabelPrinter\database\print_history.json" >nul
copy /Y "config.json" "dist\StudentLabelPrinter\config.json" >nul

echo.
echo BUILD COMPLETE:
echo %CD%\dist\StudentLabelPrinter\StudentLabelPrinter.exe
echo.
echo Distribute the entire StudentLabelPrinter folder, not only the EXE.
endlocal
