@echo off
REM Build the self-hosted lobby EXE (console mode on purpose: the host has
REM to be able to read out the address it is sharing).
cd /d "%~dp0.."

python tools\download_bore.py
if errorlevel 1 exit /b 1

echo Installing/updating PyInstaller...
python -m pip install --upgrade pyinstaller --quiet

echo.
echo Building "Host Acaristan Server.exe" ...
python -m PyInstaller ^
  --onefile ^
  --console ^
  --name "Host Acaristan Server" ^
  --paths=src ^
  --paths=tools ^
  --hidden-import=net ^
  --hidden-import=net.protocol ^
  --hidden-import=net.client ^
  --hidden-import=net.discovery ^
  --hidden-import=net.portmap ^
  --add-binary "assets\bin\bore.exe;assets\bin" ^
  --add-data "assets\bin\BORE-LICENSE.txt;assets\bin" ^
  tools\mp_host_main.py

echo.
if exist "dist\Host Acaristan Server.exe" (
  echo Build complete:  dist\Host Acaristan Server.exe
  echo.
  echo Send that EXE to a friend. They double-click it and it prints the
  echo address to share. Console mode is intentional -- they need to read it.
) else (
  echo BUILD FAILED - see the PyInstaller output above.
)
pause
