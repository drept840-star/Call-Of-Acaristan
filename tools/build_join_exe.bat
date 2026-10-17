@echo off
REM Build "Join Acaristan.exe" -- the file you send to a friend.
REM It needs no Python, no game install, nothing. They double-click it,
REM paste the address you texted them, and they are in the chat.
cd /d "%~dp0.."

echo Installing/updating PyInstaller...
python -m pip install --upgrade pyinstaller --quiet

echo.
echo Building "Join Acaristan.exe" ...
python -m PyInstaller ^
  --onefile ^
  --console ^
  --name "Join Acaristan" ^
  --paths=src ^
  --hidden-import=net ^
  --hidden-import=net.protocol ^
  --hidden-import=net.client ^
  --hidden-import=net.discovery ^
  --hidden-import=net.portmap ^
  tools\mp_join.py

echo.
if exist "dist\Join Acaristan.exe" (
  echo Done: "dist\Join Acaristan.exe"
  echo Send that one file to your friend. Nothing else needed.
) else (
  echo BUILD FAILED - see the output above.
)
echo.
pause