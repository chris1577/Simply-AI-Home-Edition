@echo off
echo ========================================
echo  Simply AI - Home Edition (Docker)
echo ========================================
echo.
echo Stopping Docker containers...
echo.

docker-compose down

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo  Containers stopped successfully.
    echo ========================================
    echo.
) else (
    echo.
    echo ERROR: Failed to stop containers.
    echo.
)

pause
