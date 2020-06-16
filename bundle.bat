@echo off
pyinstaller --onefile --console --add-binary "PolyConverter.exe;." --name PolyEditor --icon=icon.ico editor.py
pyinstaller --onefile --console --add-binary "PolyConverterNet.exe;." --name PolyEditorNet --icon=icon.ico editor.py
pause