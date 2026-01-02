@echo off
echo.
echo ========================================
echo   AI Model Generator - Backend Server
echo ========================================
echo.

cd backend

IF NOT EXIST "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing dependencies...
pip install -r requirements.txt -q

echo.
echo Starting server...
echo.
python run.py

