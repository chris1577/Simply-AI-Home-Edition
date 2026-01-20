@echo off
echo ========================================
echo Simply AI - Virtual Environment Setup
echo ========================================
echo.

:: Check if venv already exists
if exist ".venv" (
    echo Virtual environment already exists.
    set /p RECREATE="Do you want to recreate it? (y/n): "
    if /i "%RECREATE%"=="y" (
        echo Removing existing virtual environment...
        rmdir /s /q .venv
    ) else (
        echo Skipping venv creation, installing requirements only...
        goto install
    )
)

echo Creating virtual environment...
python -m venv .venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment.
    echo Make sure Python is installed and in your PATH.
    pause
    exit /b 1
)
echo Virtual environment created successfully.
echo.

:install
echo Installing requirements...
.venv\Scripts\pip.exe install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install requirements.
    pause
    exit /b 1
)

echo.
echo Running database reset...
call bat\RESET_DATABASE.bat
if errorlevel 1 (
    echo ERROR: Failed to reset database.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Setup complete!
echo ========================================
echo.
echo To activate the virtual environment:
echo   Command Prompt: .venv\Scripts\activate
echo   PowerShell:     .venv\Scripts\Activate.ps1
echo.
pause
