@echo off
REM ====================================================================
REM  MrRoboto - panel de control (voz + vision)
REM  Crea el entorno, instala lo del panel y abre http://127.0.0.1:8080
REM ====================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv" (
  echo [1/3] Creando entorno virtual...
  py -m venv .venv || python -m venv .venv
)

call .venv\Scripts\activate.bat

echo [2/3] Instalando dependencias del panel...
python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements-core.txt

echo [3/3] Abriendo panel...
start "" http://127.0.0.1:8080
python -m uvicorn mrroboto_backend.server:app --host 127.0.0.1 --port 8080

endlocal
