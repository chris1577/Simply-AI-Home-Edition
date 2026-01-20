@echo off
echo Activating virtual environment...
call .venv\Scripts\activate.bat
echo.
echo Starting Flask Server...
echo.
python run.py
pause
