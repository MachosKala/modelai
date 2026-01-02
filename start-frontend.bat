@echo off
echo.
echo ========================================
echo   AI Model Generator - Frontend Server
echo ========================================
echo.
echo Starting frontend at http://localhost:3000
echo.

cd frontend
python -m http.server 3000

