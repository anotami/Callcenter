#!/bin/bash
# =============================================================
# Script de instalacion - Sistema IA Call Center
# Para: Windows (Git Bash/WSL) o Linux con GPU NVIDIA RTX
# =============================================================
set -e

echo "============================================="
echo "  INSTALACION - Sistema IA Call Center"
echo "============================================="
echo ""

# --- Paso 1: Verificar Python ---
echo "[1/6] Verificando Python..."
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo "ERROR: Python no encontrado. Instala Python 3.11+ desde https://python.org"
    exit 1
fi
$PYTHON --version

# --- Paso 2: Crear entorno virtual ---
echo ""
echo "[2/6] Creando entorno virtual..."
if [ ! -d ".venv" ]; then
    $PYTHON -m venv .venv
    echo "  Entorno virtual creado en .venv/"
else
    echo "  Entorno virtual ya existe"
fi

# Activar entorno virtual
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
fi

# --- Paso 3: Instalar PyTorch con CUDA ---
echo ""
echo "[3/6] Instalando PyTorch con CUDA..."
echo "  Detectando GPU..."
if command -v nvidia-smi &> /dev/null; then
    echo "  GPU NVIDIA detectada:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    echo "  Instalando PyTorch con CUDA 12.1..."
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
else
    echo "  GPU no detectada. Instalando PyTorch CPU..."
    echo "  (Si tienes GPU, instala primero los drivers NVIDIA y CUDA Toolkit)"
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
fi

# --- Paso 4: Instalar dependencias ---
echo ""
echo "[4/6] Instalando dependencias del proyecto..."
pip install -r requirements.txt

# --- Paso 5: Crear .env si no existe ---
echo ""
echo "[5/6] Configurando variables de entorno..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  Archivo .env creado. DEBES editarlo con tus credenciales:"
    echo "    - HF_TOKEN: Token de HuggingFace"
    echo "    - SQL_PASSWORD: Password de SQL Server (o usa --no-db)"
else
    echo "  Archivo .env ya existe"
fi

# --- Paso 6: Crear directorios ---
echo ""
echo "[6/6] Creando directorios..."
mkdir -p audio output
echo "  audio/  -> Coloca aqui tus archivos de audio"
echo "  output/ -> Aqui se guardaran los resultados"

echo ""
echo "============================================="
echo "  INSTALACION COMPLETADA"
echo "============================================="
echo ""
echo "Pasos siguientes:"
echo "  1. Edita el archivo .env con tu HF_TOKEN"
echo "  2. Instala Ollama: curl -fsSL https://ollama.com/install.sh | sh"
echo "     (O descarga LM Studio: https://lmstudio.ai)"
echo "  3. Descarga Llama 3.1: ollama pull llama3.1:8b"
echo "  4. Coloca audios en audio/"
echo "  5. Ejecuta: python main.py"
echo ""
echo "Para verificar la instalacion: python verify_setup.py"
