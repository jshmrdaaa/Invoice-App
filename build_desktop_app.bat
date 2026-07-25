@echo off
cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo Python was not found. Install Python and check Add python.exe to PATH.
    pause
    exit /b
)

python -m pip install -r requirements_desktop.txt
python -m pip install pyinstaller

if exist build rmdir /S /Q build
if exist dist rmdir /S /Q dist
if exist "TA Invoices and Estimates.spec" del /Q "TA Invoices and Estimates.spec"
if exist "TA Invoices and Estimates.exe" del /Q "TA Invoices and Estimates.exe"

python -m PyInstaller --clean --noconfirm --onefile --windowed --name "TA Invoices and Estimates" --hidden-import pypdf --add-data "logo_grayblue_transparent.png;." adael_desktop.py

if not exist "dist\TA Invoices and Estimates.exe" (
    echo The desktop app did not build correctly. Send Thiago a picture of this window.
    pause
    exit /b
)

copy /Y "dist\TA Invoices and Estimates.exe" "TA Invoices and Estimates.exe"
echo Done. Use TA Invoices and Estimates.exe from this folder.
pause
