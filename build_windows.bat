@echo off
echo Building Windows Executable...
pip install pyinstaller
pyinstaller --onefile --name=LLM_Mini_Windows launcher.py
echo Build complete. Check the 'dist' folder.
