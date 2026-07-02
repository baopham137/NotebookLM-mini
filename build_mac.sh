#!/bin/bash
echo "Building Mac Executable..."
pip install pyinstaller
pyinstaller --onefile --name=LLM_Mini_Mac launcher.py
echo "Build complete. Check the 'dist' folder."
