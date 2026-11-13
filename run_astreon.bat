@echo off
title ASTREON - Mars Mission Site Intelligence Platform
cd /d "%~dp0"
echo =====================================================================
echo  ASTREON - Mars Mission Site Intelligence Platform
echo  Aerospace Site Evaluation, Solar/Dust Monitoring & Life Support Engine
echo =====================================================================
echo.

if exist ".venv\Scripts\activate.bat" (
    echo [INFO] Detected virtual environment. Activating...
    call .venv\Scripts\activate.bat
)

echo Starting ASTREON local server...
python run.py
if errorlevel 1 (
    echo.
    echo [NOTE] If dependencies are missing, install them with:
    echo        pip install -r requirements.txt
)
pause
