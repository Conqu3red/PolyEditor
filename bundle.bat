@echo off
pyinstaller --onefile --add-binary "PolyConverter.exe;." --name PolyEditor --icon=icon.ico editor.py
pause