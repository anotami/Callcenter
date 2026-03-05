@echo off
REM =============================================================
REM Script de instalacion - Sistema IA Call Center
REM Para: Windows con GPU NVIDIA RTX
REM =============================================================

echo =============================================
echo   INSTALACION - Sistema IA Call Center
echo =============================================
echo.

REM --- Paso 1: Verificar Python ---
echo [1/6] Verificando Python...
python --version
if errorlevel 1 (
    echo ERROR: Python no encontrado. Instala Python 3.11+ desde https://python.org
    pause
    exit /b 1
)

REM --- Paso 2: Crear entorno virtual ---
echo.
echo [2/6] Creando entorno virtual...
if not exist ".venv" (
    python -m venv .venv
    echo   Entorno virtual creado en .venv\
) else (
    echo   Entorno virtual ya existe
)

call .venv\Scripts\activate.bat

REM --- Paso 3: Instalar PyTorch con CUDA ---
echo.
echo [3/6] Instalando PyTorch con CUDA 12.1...
echo   Esto puede tardar varios minutos...
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

REM --- Paso 4: Instalar dependencias ---
echo.
echo [4/6] Instalando dependencias del proyecto...
pip install -r requirements.txt

REM --- Paso 5: Crear .env ---
echo.
echo [5/6] Configurando variables de entorno...
if not exist ".env" (
    copy .env.example .env
    echo   Archivo .env creado. DEBES editarlo con tus credenciales.
) else (
    echo   Archivo .env ya existe
)

REM --- Paso 6: Crear directorios ---
echo.
echo [6/6] Creando directorios...
if not exist "audio" mkdir audio
if not exist "output" mkdir output

echo.
echo =============================================
echo   INSTALACION COMPLETADA
echo =============================================
echo.
echo Pasos siguientes:
echo   1. Edita .env con tu HF_TOKEN
echo   2. Descarga Ollama: https://ollama.com/download
echo      (O LM Studio: https://lmstudio.ai)
echo   3. En terminal: ollama pull llama3.1:8b
echo   4. Coloca audios en audio\
echo   5. Ejecuta: python main.py
echo.
echo Para verificar: python verify_setup.py
echo.
pause
