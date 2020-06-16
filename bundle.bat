@echo off
pyinstaller --onefile --console --add-binary "PolyConverter.exe;." --name PolyEditor --icon=icon.ico editor.py
pause