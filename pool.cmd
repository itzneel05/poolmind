@echo off
REM poolmind CLI wrapper for Windows CMD
cd /d "%~dp0"
.venv\Scripts\python.exe -m app.cli %*
