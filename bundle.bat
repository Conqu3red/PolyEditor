@echo off
pyinstaller --onefile --add-binary "PolyConverter.exe;." --add-data "favicon.ico;." --name PolyEditor --icon=pb_sheep.ico editor.py
pause