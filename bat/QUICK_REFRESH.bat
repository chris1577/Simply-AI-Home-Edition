@echo off
REM ========================================================
REM QUICK REFRESH - For Fast Testing
REM ========================================================
REM Ultra-fast database and file cleanup for development.
REM This script:
REM   1. Deletes database (instance\simplyai.db)
REM   2. Deletes uploads folder (uploads/images, uploads/documents)
REM   3. Recreates database with all tables and migrations
REM   4. Creates quick admin (admin/AdminPass123!@#)
REM
REM NO PROMPTS - Instant reset for rapid testing!
REM ========================================================

cd /d "%~dp0.."

echo.
echo ========================================================
echo       QUICK REFRESH - Resetting Application State
echo ========================================================
echo.

REM Step 1: Delete database files
echo [1/4] Cleaning database...
if exist instance\simplyai.db (
    del /f /q instance\simplyai.db >nul 2>&1
    echo    [OK] Database deleted: instance\simplyai.db
) else if exist simplyai.db (
    del /f /q simplyai.db >nul 2>&1
    echo    [OK] Database deleted: simplyai.db
) else (
    echo    [INFO] No database found
)

REM Step 2: Delete uploads
echo [2/4] Cleaning uploads...
if exist uploads\images (
    rd /s /q uploads\images >nul 2>&1
    echo    [OK] Deleted uploads\images
)
if exist uploads\documents (
    rd /s /q uploads\documents >nul 2>&1
    echo    [OK] Deleted uploads\documents
)
if exist uploads (
    rd /s /q uploads >nul 2>&1
    echo    [OK] Deleted uploads folder
)

REM Step 3: Recreate database
echo [3/4] Recreating database...
python scripts\setup\init_db.py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo    [OK] Database initialized
) else (
    echo    [ERROR] Database initialization failed!
    pause
    exit /b 1
)

REM Run all migrations silently
python scripts\migrations\add_model_columns.py >nul 2>&1
python scripts\migrations\add_attachments_table.py >nul 2>&1
echo yes | python scripts\migrations\add_model_visibility.py >nul 2>&1
python scripts\migrations\add_admin_settings.py >nul 2>&1
echo yes | python scripts\migrations\remove_anonymous_chats.py >nul 2>&1
python scripts\migrations\add_rag_tables.py >nul 2>&1
python scripts\migrations\add_vision_settings.py >nul 2>&1
python scripts\migrations\add_date_of_birth.py >nul 2>&1
python scripts\migrations\add_child_safety_settings.py >nul 2>&1
python scripts\migrations\add_session_token.py >nul 2>&1
python scripts\migrations\add_model_id_settings.py >nul 2>&1
python scripts\migrations\add_token_tracking.py >nul 2>&1
python scripts\migrations\add_rate_limit_settings.py >nul 2>&1
python scripts\migrations\add_distilled_context.py >nul 2>&1
echo    [OK] All migrations applied (including model IDs, RAG, vision, child safety, session token, token tracking, rate limits, distilled context)

REM Step 4: Create admin user
echo [4/4] Creating admin user...
python scripts\setup\quick_create_admin.py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo    [OK] Admin user created
) else (
    echo    [ERROR] Admin creation failed!
    pause
    exit /b 1
)

echo.
echo ========================================================
echo [SUCCESS] Application refreshed and ready for testing!
echo ========================================================
echo.
echo Quick admin credentials:
echo   Username: admin
echo   Password: AdminPass123!@#
echo.
echo Database: instance\simplyai.db (fresh)
echo Uploads:  uploads/ (empty)
echo.
echo Start server: python run.py
echo          OR:  start_server.bat
echo.
echo ========================================================
