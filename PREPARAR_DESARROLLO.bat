@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup-dev.ps1" -Dev
if errorlevel 1 (
  echo No se pudo preparar el proyecto. Revisa el mensaje anterior.
  pause
  exit /b 1
)
echo Listo. Abre INICIAR_CONTROL.vbs para usar el programa sin consola.
pause
