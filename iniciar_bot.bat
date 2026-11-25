@echo off
cd /d "%~dp0"
:inicio
python bot.py
echo.
echo El bot se detuvo. Se reinicia en 5 segundos (cierra esta ventana para apagarlo).
timeout /t 5 >nul
goto inicio
