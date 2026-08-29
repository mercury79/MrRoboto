@echo off
REM ====================================================================
REM  Instala las dependencias PESADAS: voz (Whisper, TTS) + vision (OpenCV).
REM  Corre esto una vez para habilitar la conversacion y el reconocimiento.
REM  La primera transcripcion descargara el modelo Whisper (unos cientos de MB).
REM ====================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv" (
  echo Creando entorno virtual...
  py -m venv .venv || python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul 2>&1

echo Instalando voz + vision (puede tardar varios minutos)...
pip install -r requirements-full.txt

echo.
echo Listo. Ya puedes usar voz y reconocimiento facial en el panel.
pause
endlocal
