@echo off
echo ========================================
echo  Simply AI - Home Edition (Docker)
echo ========================================
echo.
echo Starting Docker containers...
echo.

docker-compose up --build -d

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo  Application started successfully!
    echo  Access at: http://localhost:8080
    echo ========================================
    echo.
    echo To view logs: docker-compose logs -f app
    echo To stop: stop_docker.bat
    echo.
) else (
    echo.
    echo ERROR: Failed to start containers.
    echo Make sure Docker Desktop is running.
    echo.
)

pause
