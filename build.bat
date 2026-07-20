@echo off
cd /d "%~dp0"

echo Installing/updating PyInstaller...
python -m pip install --upgrade pyinstaller --quiet

echo Building executable...
python -m PyInstaller ^
  --onefile ^
  --windowed ^
  --name "Call of Acaristan" ^
  --icon=assets\logo.ico ^
  --add-data "assets;assets" ^
  --hidden-import=pygame ^
  --hidden-import=pygame._sdl2 ^
  --collect-all=pygame ^
  acaristan.py

echo.
echo Build complete! Check dist\Call of Acaristan.exe
pause