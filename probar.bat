@echo off
cd /d "%~dp0"
python pruebas\pruebas_seguro.py > pruebas\resultado_pruebas.txt 2>&1
python pruebas\pruebas_bot.py >> pruebas\resultado_pruebas.txt 2>&1
type pruebas\resultado_pruebas.txt
pause
