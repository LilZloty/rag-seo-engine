@echo off
echo ==========================================
echo AI Analysis Cache Migration
echo ==========================================
echo.

REM Navigate to backend directory
cd /d "%~dp0\.."

REM Run the migration script
python scripts\migrate_ai_cache.py

echo.
echo Press any key to exit...
pause >nul
