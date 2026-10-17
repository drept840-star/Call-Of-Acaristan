@echo off
REM Double-click this to join a friend's lobby. That is the whole job.
REM Asks for the address they sent you, then you just type to chat.
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
  echo.
  echo   Python was not found on this computer.
  echo   Ask your friend to send you "Join Acaristan.exe" instead -
  echo   that one needs nothing installed.
  echo.
  pause
  exit /b 1
)

python mp_join.py %*
if errorlevel 1 pause