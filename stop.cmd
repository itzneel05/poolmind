@echo off
REM poolmind — stop all services

echo Stopping poolmind web UI...
taskkill /F /FI "WINDOWTITLE eq poolmind*" /T 2>nul
taskkill /F /IM python.exe /FI "CPUTIME gt 00:00:01" 2>nul

echo Stopping freellmapi AI backend...
taskkill /F /FI "WINDOWTITLE eq freellmapi*" /T 2>nul
taskkill /F /IM node.exe /FI "CPUTIME gt 00:00:01" 2>nul

echo Done.
