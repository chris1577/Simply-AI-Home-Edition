@echo off
REM ========================================================
REM Database Reset Script for Simply AI
REM ========================================================
REM This script will:
REM 1. Delete the existing database file
REM 2. Clean up old uploads (optional)
REM 3. Initialize a fresh database with all tables
REM 4. Run all migration scripts (13 migrations)
REM    - Model columns
REM    - File attachments
REM    - Model visibility
REM    - Admin settings
REM    - Anonymous chat cleanup
REM    - RAG tables
REM    - Vision settings
REM    - Date of birth (child safety)
REM    - Child safety settings
REM    - Session token (single device login)
REM    - Model ID settings (system-level model IDs)
REM    - Token tracking (input/output tokens per message)
REM    - Rate limit settings (customizable rate limits)
REM 5. Optionally create an admin user
REM ========================================================

cd /d "%~dp0.."

echo.
echo ========================================================
echo         Simply AI - Database Reset Script
echo ========================================================
echo.
echo WARNING: This will DELETE your current database!
echo All chat history, users, and data will be LOST.
echo.
set /p "CONFIRM=Are you sure you want to continue? (yes/no): "

if /i not "%CONFIRM%"=="yes" (
    echo.
    echo [CANCELLED] Database reset cancelled.
    pause
    exit /b 0
)

echo.
echo [WORKING] Starting database reset...
echo.

REM Step 1: Activate virtual environment
echo [STEP 1/5] Activating virtual environment...
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
    echo    [OK] Virtual environment activated
) else (
    echo    [ERROR] Virtual environment not found!
    echo    [INFO] Please run: python -m venv .venv
    pause
    exit /b 1
)
echo.

REM Step 2: Delete the existing database file
echo [STEP 2/5] Deleting old database...
if exist instance\simplyai.db (
    del /f /q instance\simplyai.db
    echo    [OK] Database file deleted
) else if exist simplyai.db (
    del /f /q simplyai.db
    echo    [OK] Database file deleted
) else (
    echo    [INFO] No database file found
)

REM Optional: Clean up uploaded files
set /p "CLEAN_UPLOADS=Do you want to delete all uploaded files? (yes/no): "
if /i "%CLEAN_UPLOADS%"=="yes" (
    if exist uploads (
        echo    [WORKING] Deleting uploads folder...
        rd /s /q uploads
        echo    [OK] Uploads folder deleted
    )
)
echo.


REM Step 3: Initialize fresh database
echo [STEP 3/5] Initializing fresh database...
echo.
python scripts\setup\init_db.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Database initialization failed!
    pause
    exit /b 1
)
echo.

REM Step 4: Run migration scripts
echo [STEP 4/5] Running migration scripts...
echo.

echo    [MIGRATION 1/13] Adding model columns...
python scripts\migrations\add_model_columns.py
echo.

echo    [MIGRATION 2/13] Adding attachment support...
python scripts\migrations\add_attachments_table.py
echo.

echo    [MIGRATION 3/13] Adding model visibility...
echo yes | python scripts\migrations\add_model_visibility.py
echo.

echo    [MIGRATION 4/13] Adding admin settings...
python scripts\migrations\add_admin_settings.py
echo.

echo    [MIGRATION 5/13] Removing anonymous chat support...
echo yes | python scripts\migrations\remove_anonymous_chats.py
echo.

echo    [MIGRATION 6/13] Adding RAG (Retrieval-Augmented Generation) tables...
python scripts\migrations\add_rag_tables.py
echo.

echo    [MIGRATION 7/13] Adding local model vision settings...
python scripts\migrations\add_vision_settings.py
echo.

echo    [MIGRATION 8/13] Adding date of birth for child safety...
python scripts\migrations\add_date_of_birth.py
echo.

echo    [MIGRATION 9/13] Adding child safety settings...
python scripts\migrations\add_child_safety_settings.py
echo.

echo    [MIGRATION 10/13] Adding session token for single device login...
python scripts\migrations\add_session_token.py
echo.

echo    [MIGRATION 11/13] Adding system model ID settings...
python scripts\migrations\add_model_id_settings.py
echo.

echo    [MIGRATION 12/13] Adding token tracking columns...
python scripts\migrations\add_token_tracking.py
echo.

echo    [MIGRATION 13/13] Adding rate limit settings...
python scripts\migrations\add_rate_limit_settings.py
echo.

if %ERRORLEVEL% neq 0 (
    echo    [WARNING] Some migrations may have failed (this is OK if tables already exist)
)
echo.

REM Step 5: Create admin user
echo [STEP 5/5] Admin user creation...
echo.
echo Choose admin creation method:
echo   1. Quick admin (username: admin, password: AdminPass123!@#)
echo   2. Custom admin (interactive)
echo   3. Skip (create later)
echo.
set /p "ADMIN_CHOICE=Enter your choice (1/2/3): "

if "%ADMIN_CHOICE%"=="1" (
    echo.
    echo [INFO] Creating quick admin user...
    python scripts\setup\quick_create_admin.py
) else if "%ADMIN_CHOICE%"=="2" (
    echo.
    echo [INFO] Creating custom admin user...
    python scripts\setup\create_admin.py
) else (
    echo.
    echo [INFO] Skipping admin creation
    echo [TIP] You can create an admin later with:
    echo    python scripts\setup\create_admin.py
    echo    OR
    echo    python scripts\setup\quick_create_admin.py
)

echo.
echo ========================================================
echo [SUCCESS] Database reset complete!
echo ========================================================
echo.
echo Next steps:
echo   1. Start the server:  START_SERVER.bat
echo   2. Open browser: http://localhost:8080
echo.
echo Database file: instance\simplyai.db
echo Uploads folder: uploads/
echo.
echo Migrations applied:
echo   - Model columns (legacy - for UserSettings)
echo   - File attachments (images, PDFs, documents)
echo   - Model visibility management (admin feature)
echo   - Admin settings (sensitive info filter, etc.)
echo   - Anonymous chat cleanup (removed old feature)
echo   - RAG tables (documents, chunks for retrieval-augmented generation)
echo   - Vision settings (LM Studio and Ollama vision support)
echo   - Date of birth (child safety age tracking)
echo   - Child safety settings (age-based system prompts)
echo   - Session token (single device login enforcement)
echo   - Model ID settings (system-level model IDs in AdminSettings)
echo   - Token tracking (input/output tokens per message)
echo   - Rate limit settings (customizable rate limits)
echo.
pause
