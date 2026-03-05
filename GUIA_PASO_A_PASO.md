# Guia Paso a Paso - Montar Sistema IA Call Center

## Requisitos de tu PC
- Windows 10/11 (o Linux)
- GPU NVIDIA GeForce RTX (cualquier modelo)
- 16GB+ RAM (32GB recomendado)
- 20GB disco libre
- Conexion a internet (solo para descargar modelos la primera vez)

---

## PASO 1: Instalar Python 3.11

Si no tienes Python instalado:
1. Ve a https://python.org/downloads/
2. Descarga Python 3.11.x (NO 3.13, tiene problemas de compatibilidad)
3. Al instalar, MARCA la casilla **"Add Python to PATH"**
4. Verifica en terminal: `python --version`

---

## PASO 2: Instalar drivers NVIDIA + CUDA

Tu GPU RTX necesita drivers actualizados:
1. Ve a https://www.nvidia.com/drivers
2. Descarga e instala el driver mas reciente para tu RTX
3. Verifica en terminal: `nvidia-smi`
   - Debe mostrar tu GPU y la version de CUDA

> Si ya tienes drivers actualizados y `nvidia-smi` funciona, salta este paso.

---

## PASO 3: Clonar el repositorio e instalar

### Opcion A: Windows (doble click)
```
1. Abre una terminal (cmd o PowerShell) en la carpeta del proyecto
2. Ejecuta: install.bat
```

### Opcion B: Linux/WSL/Git Bash
```bash
chmod +x install.sh
./install.sh
```

### Opcion C: Manual (si prefieres hacerlo tu mismo)
```bash
# Crear entorno virtual
python -m venv .venv

# Activar (Windows)
.venv\Scripts\activate
# Activar (Linux/Mac)
source .venv/bin/activate

# Instalar PyTorch con CUDA
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

# Instalar el resto de dependencias
pip install -r requirements.txt
```

---

## PASO 4: Obtener token de HuggingFace

El modelo de diarizacion (pyannote) requiere aceptar una licencia:

1. Crea cuenta en https://huggingface.co (gratis)
2. Ve a https://huggingface.co/settings/tokens
3. Crea un token con permisos de lectura
4. **IMPORTANTE**: Acepta la licencia en estas 2 paginas:
   - https://huggingface.co/pyannote/speaker-diarization-3.1
   - https://huggingface.co/pyannote/segmentation-3.0
   (Click en "Agree and access repository" en cada una)
5. Copia el token (empieza con `hf_...`)

---

## PASO 5: Configurar archivo .env

1. Abre el archivo `.env` (se creo en PASO 3)
2. Reemplaza los valores:

```
HF_TOKEN=hf_TU_TOKEN_REAL_AQUI

LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.1:8b

WHISPER_MODEL=large-v3
WHISPER_DEVICE=cuda
WHISPER_LANGUAGE=es
```

> Si usas LM Studio en vez de Ollama, cambia:
> `LLM_BASE_URL=http://localhost:1234/v1`

---

## PASO 6: Instalar Ollama + Llama 3.1

### Opcion A: Ollama (RECOMENDADO - mas facil para automatizar)

**Windows:**
1. Descarga de https://ollama.com/download
2. Instala y abre Ollama
3. En terminal:
```bash
ollama pull llama3.1:8b
```
4. Ollama queda corriendo automaticamente en puerto 11434

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1:8b
```

### Opcion B: LM Studio (interfaz visual)

1. Descarga de https://lmstudio.ai
2. Abre LM Studio
3. Busca "llama 3.1 8b instruct" en el buscador
4. Descarga el modelo (GGUF Q4_K_M recomendado, ~4.7GB)
5. Ve a la pestana "Local Server" y click "Start Server"
6. El servidor queda en puerto 1234

---

## PASO 7: Verificar instalacion

```bash
# Activar entorno virtual primero
# Windows: .venv\Scripts\activate
# Linux:   source .venv/bin/activate

python verify_setup.py
```

Debes ver algo como:
```
[OK] Python: 3.11.x
[OK] PyTorch: v2.x.x | CUDA OK | GPU: NVIDIA GeForce RTX xxxx
[OK] faster-whisper: Instalado correctamente
[OK] pyannote.audio: Instalado correctamente
[OK] HF_TOKEN: Configurado (hf_abc123...)
[OK] LLM Server: Conectado | Modelos: llama3.1:8b
[FAIL] SQL Server: ...  (es opcional, no te preocupes)

RESULTADO: 6/7 componentes OK
Estado: LISTO para procesar audios
```

---

## PASO 8: Procesar tu primer audio

1. Coloca un archivo de audio (MP3, WAV, etc.) en la carpeta `audio/`
2. Ejecuta:

```bash
# Sin base de datos (recomendado para la primera prueba)
python main.py --no-db

# O un archivo especifico
python main.py audio/mi_llamada.mp3 --no-db
```

3. Los resultados se guardaran en `output/`:
   - `*_transcripcion.txt` - Dialogo completo con hablantes
   - `*_evaluacion.json` - Evaluacion detallada en JSON
   - `*_reporte.txt` - Reporte legible de calidad

---

## PASO 9 (Opcional): Configurar SQL Server

Solo si necesitas guardar en base de datos:

1. Instala SQL Server Express (gratis):
   https://www.microsoft.com/sql-server/sql-server-downloads
2. Instala ODBC Driver 17:
   https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server
3. Crea una base de datos llamada "CallCenter"
4. Edita `.env` con los datos de conexion
5. Ejecuta sin `--no-db`:
   ```bash
   python main.py
   ```

---

## Solucion de Problemas Comunes

### "CUDA not available" pero tengo GPU RTX
- Verifica que `nvidia-smi` funcione
- Reinstala PyTorch: `pip install torch --index-url https://download.pytorch.org/whl/cu121`
- La version de CUDA del driver debe ser >= 12.1

### "HF_TOKEN not configured"
- Edita `.env` y agrega tu token de HuggingFace
- Asegurate de aceptar las licencias de pyannote en HuggingFace

### "Connection refused" al LLM
- Asegurate de que Ollama o LM Studio esten corriendo
- Verifica el puerto: Ollama=11434, LM Studio=1234
- Verifica en `.env` que `LLM_BASE_URL` sea correcto

### Transcripcion muy lenta
- Verifica que CUDA este activo (ver verify_setup.py)
- Usa modelo mas pequeno: cambia `WHISPER_MODEL=medium` en `.env`
- El modelo `large-v3` necesita ~3GB VRAM

### Error de memoria GPU (Out of Memory)
- Usa modelo whisper mas pequeno: `medium` o `small`
- Cierra otras aplicaciones que usen GPU
- Reduce batch size en el LLM
