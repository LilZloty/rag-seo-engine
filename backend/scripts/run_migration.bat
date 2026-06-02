@echo off
echo ==========================================
echo Database Migration - Add Sales Periods
echo ==========================================
echo.

REM Navigate to backend directory
cd /d "%~dp0\.."

REM Run the migration script
python scripts\migrate_sales_periods.py

echo.
echo Press any key to exit...
pause >nul
