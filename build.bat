@echo off
cd /d "%~dp0"
python tools\build_windows.py %*
if errorlevel 1 (echo BUILD FAILED & exit /b 1)
echo.
echo Done: dist\Call of Acaristan\Call of Acaristan.exe  (onedir, no admin needed)
pause
