@echo off
setlocal EnableDelayedExpansion

REM ========================================================
REM Simply AI - Home Edition
REM Windows Build Script
REM ========================================================
REM
REM Prerequisites:
REM   1. Python 3.10+ with pip
REM   2. Virtual environment with all dependencies
REM   3. Inno Setup 6.x (for installer creation)
REM
REM This script will:
REM   1. Install build dependencies (PyInstaller)
REM   2. Compile the application using PyInstaller
REM   3. Create the installer using Inno Setup (if available)
REM ========================================================

cd /d "%~dp0.."
set "PROJECT_ROOT=%CD%"
set "BUILD_DIR=%PROJECT_ROOT%\build"
set "DIST_DIR=%PROJECT_ROOT%\dist"

echo.
echo ========================================================
echo   Simply AI - Home Edition
echo   Windows Build Script
echo ========================================================
echo.
echo Project Root: %PROJECT_ROOT%
echo Build Dir:    %BUILD_DIR%
echo.

REM --------------------------------------------------------
REM Step 1: Check Python and activate virtual environment
REM --------------------------------------------------------
echo [1/5] Checking Python environment...

if exist "%PROJECT_ROOT%\.venv\Scripts\activate.bat" (
    call "%PROJECT_ROOT%\.venv\Scripts\activate.bat"
    echo       Using virtual environment
) else (
    echo       [WARNING] Virtual environment not found
    echo       Using system Python
)

python --version
if errorlevel 1 (
    echo.
    echo [ERROR] Python not found! Please install Python 3.10+
    pause
    exit /b 1
)
echo.

REM --------------------------------------------------------
REM Step 2: Install build dependencies
REM --------------------------------------------------------
echo [2/5] Installing build dependencies...

pip install pyinstaller --quiet
if errorlevel 1 (
    echo       [ERROR] Failed to install PyInstaller
    pause
    exit /b 1
)
echo       PyInstaller installed
echo.

REM --------------------------------------------------------
REM Step 3: Clean previous builds and cache
REM --------------------------------------------------------
echo [3/5] Cleaning previous builds and cache...

if exist "%DIST_DIR%\SimplyAI" (
    rmdir /s /q "%DIST_DIR%\SimplyAI"
    echo       Removed old dist\SimplyAI
)

if exist "%PROJECT_ROOT%\build\SimplyAI" (
    rmdir /s /q "%PROJECT_ROOT%\build\SimplyAI"
    echo       Removed old build\SimplyAI
)

REM Clean PyInstaller analysis cache (lowercase 'simplyai' folder)
if exist "%PROJECT_ROOT%\build\simplyai" (
    rmdir /s /q "%PROJECT_ROOT%\build\simplyai"
    echo       Removed PyInstaller cache build\simplyai
)

if exist "%PROJECT_ROOT%\installer_output" (
    rmdir /s /q "%PROJECT_ROOT%\installer_output"
    echo       Removed old installer_output
)

REM Clean Python bytecode cache to ensure fresh compilation
echo       Cleaning Python cache files...
for /d /r "%PROJECT_ROOT%\app" %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d" 2>nul
for /d /r "%PROJECT_ROOT%\scripts" %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d" 2>nul
if exist "%PROJECT_ROOT%\__pycache__" rmdir /s /q "%PROJECT_ROOT%\__pycache__" 2>nul
echo       Cache cleaned
echo.

REM --------------------------------------------------------
REM Step 4: Build with PyInstaller
REM --------------------------------------------------------
echo [4/5] Building executable with PyInstaller...
echo       This may take several minutes...
echo.

cd "%PROJECT_ROOT%"

REM Run PyInstaller with the spec file
pyinstaller --clean --noconfirm "%BUILD_DIR%\simplyai.spec"

if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build failed!
    echo.
    echo Common issues:
    echo   - Missing dependencies: pip install -r requirements.txt
    echo   - Antivirus blocking: Add exception for project folder
    echo   - Memory issues: Close other applications
    echo.
    pause
    exit /b 1
)

echo.
echo       Build completed successfully!
echo.

REM --------------------------------------------------------
REM Step 5: Create Installer (optional)
REM --------------------------------------------------------
echo [5/5] Creating installer...

REM Check if Inno Setup is installed
set "ISCC="
if exist "C:\Users\chris\AppData\Local\Programs\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Users\chris\AppData\Local\Programs\Inno Setup 6\ISCC.exe"
) else if exist "C:\Users\chris\AppData\Local\Programs\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Users\chris\AppData\Local\Programs\Inno Setup 6\ISCC.exe"
)

if defined ISCC (
    echo       Found Inno Setup at: !ISCC!
    echo       Building installer...
    echo.

    mkdir "%PROJECT_ROOT%\installer_output" 2>nul

    "!ISCC!" "%BUILD_DIR%\installer.iss"

    if errorlevel 1 (
        echo.
        echo       [WARNING] Installer creation failed
        echo       The executable is still available in dist\SimplyAI
    ) else (
        echo.
        echo       Installer created successfully!
    )
) else (
    echo       [INFO] Inno Setup not found
    echo       Skipping installer creation
    echo.
    echo       To create an installer:
    echo       1. Download Inno Setup from https://jrsoftware.org/isinfo.php
    echo       2. Install it to the default location
    echo       3. Run this script again
    echo.
    echo       OR manually open build\installer.iss in Inno Setup Compiler
)

echo.
echo ========================================================
echo   Build Complete!
echo ========================================================
echo.
echo   Executable location:
echo     %DIST_DIR%\SimplyAI\SimplyAI.exe
echo.

if exist "%PROJECT_ROOT%\installer_output\SimplyAI-Setup-*.exe" (
    echo   Installer location:
    for %%f in ("%PROJECT_ROOT%\installer_output\SimplyAI-Setup-*.exe") do echo     %%f
    echo.
)

echo   To test the build:
echo     1. Navigate to dist\SimplyAI
echo     2. Run SimplyAI.exe
echo     3. The app will perform first-time setup automatically
echo.
echo   Note: When using the installer, you will be prompted to
echo   create your own admin username and password during setup.
echo.
echo ========================================================
echo.

pause
