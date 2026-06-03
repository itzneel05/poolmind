@echo off
REM poolmind — one-click startup
REM Starts freellmapi (AI backend) + poolmind web UI

cd /d "%~dp0"

echo ============================================================
echo  poolmind — Cybersecurity Resource Pool
echo ============================================================
echo.
echo [1/3] Starting AI backend (freellmapi)...
echo.

start "freellmapi" /MIN cmd /c "cd /d "%~dp0freellmapi" && npm run dev"

echo  Waiting for AI backend to initialize...
echo  (check the freellmapi window for progress)
timeout /t 8 /nobreak >nul
echo.
echo [2/3] Starting web UI server...
echo.
echo  Dashboard: http://127.0.0.1:5000
echo  AI API:    http://localhost:3001
echo.
echo [3/3] Open http://127.0.0.1:5000 in your browser
echo.
echo  Press Ctrl+C to stop poolmind
echo  (close freellmapi window separately to stop AI)
echo ============================================================
echo.

.venv\Scripts\python.exe -m app.webui
