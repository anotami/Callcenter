# CallCenter AI Team

Sistema de inteligencia artificial para operaciones de call center, con un equipo de **5 agentes especializados** que procesan datos, evaluan calidad, calculan staffing, facturacion y generan reportes ejecutivos.

---

## Arquitectura del Proyecto

```
Callcenter/
├── app.py                 # UI Streamlit - Panel de agentes
├── agents_config.py       # Definicion de 5 agentes y 20 habilidades
├── agent_runner.py        # Motor de ejecucion y versionado de resultados
├── analyzer.py            # Evaluacion de calidad con LLM local
├── transcriber.py         # Transcripcion de audio (faster-whisper)
├── diarizer.py            # Diarizacion de hablantes (pyannote)
├── prompts.py             # 8 criterios de evaluacion de calidad
├── database.py            # Conexion SQL Server y persistencia
├── config.py              # Configuracion centralizada
├── main.py                # Pipeline CLI (audio → evaluacion → BD)
├── verify_setup.py        # Verificacion de dependencias
├── requirements.txt       # Dependencias Python
├── .env.example           # Template de variables de entorno
├── install.sh             # Instalador Linux
├── install.bat            # Instalador Windows
├── examples/              # Datos de ejemplo para probar agentes
│   ├── acd_sample.csv
│   ├── qa_sample.csv
│   └── cx_sample.csv
├── audio/                 # Audios de llamadas (entrada)
├── output/                # Resultados exportados
└── agent_results/         # Resultados versionados por agente
```

---

## Equipo de Agentes

### 1. CORTEX — Datos
Especialista en ingesta, documentacion y validacion de fuentes de datos.

| Habilidad | Descripcion | Input |
|---|---|---|
| **Ingesta ACD** | Procesa datos del distribuidor automatico de llamadas | `.csv` `.xlsx` `.json` |
| **Ingesta QA** | Carga reportes de Quality Assurance | `.csv` `.xlsx` `.json` |
| **Ingesta CX** | Procesa encuestas de experiencia del cliente (CSAT, NPS) | `.csv` `.xlsx` `.json` |
| **Validar Fuentes** | Cruza y valida consistencia entre 2+ fuentes | Resultados previos |
| **Transcribir Audio** | Convierte audio a texto con timestamps (faster-whisper) | `.mp3` `.wav` `.m4a` `.ogg` |
| **Generar Dialogo** | Transcribe + diariza para generar dialogo Asesor/Cliente | `.mp3` `.wav` `.m4a` `.ogg` |

### 2. NEXUS — WFM Capacidad
Experto en Workforce Management y dimensionamiento de equipos.

| Habilidad | Descripcion | Input |
|---|---|---|
| **Calcular Carga de Trabajo** | Calcula volumetria por intervalo, picos y valles | Archivo o resultado CORTEX |
| **Calcular TMO** | Tiempo Medio de Operacion desglosado (talk/hold/ACW) | Archivo o resultado CORTEX |
| **Calcular Staffing (Erlang C)** | Agentes necesarios segun nivel de servicio objetivo | Texto con parametros o resultados NEXUS |

### 3. SENTINEL — Calidad
Guardian de calidad del call center.

| Habilidad | Descripcion | Input |
|---|---|---|
| **Evaluar Llamada** | Evalua dialogo contra 8 criterios de calidad (0-100) | Texto o resultado CORTEX |
| **Monitoreo de KPIs** | Dashboard de KPIs con semaforos y alertas | Archivo o resultados previos |
| **Detectar Errores Criticos (RAC)** | Identifica errores de Resolucion al Cliente | Evaluaciones o dialogos |
| **Generar Reporte de Calidad** | Reporte formateado con indicadores visuales | Resultado de SENTINEL |

### 4. LEDGER — Financiero
Contador del equipo.

| Habilidad | Descripcion | Input |
|---|---|---|
| **Calcular Facturacion** | Facturacion por volumenes (por llamada/minuto/FTE) | Archivo + parametros tarifa |
| **Calcular Bonos** | Bonificaciones segun cumplimiento de KPIs | KPIs + tabla de metas |
| **Calcular Penalidades** | Penalidades por incumplimiento de SLAs | KPIs + tabla de SLAs |

### 5. ATLAS — Estrategia
Centro de inteligencia para reportes ejecutivos.

| Habilidad | Descripcion | Input |
|---|---|---|
| **Consolidar WBR** | Reporte semanal (Weekly Business Review) | 2+ resultados de agentes |
| **Consolidar MBR** | Reporte mensual (Monthly Business Review) | Resultados acumulados del mes |
| **Analisis Cruzado** | Correlaciones entre KPIs y patrones | 2+ resultados de cualquier agente |
| **Resumen de Equipo** | Dashboard de actividad del equipo | Automatico del historial |

---

## Flujo de Trabajo entre Agentes

```
                    ┌──────────────────────────────────────────┐
                    │              CORTEX (Datos)               │
                    │  Audio → Transcripcion → Dialogo          │
                    │  CSV/Excel → Ingesta ACD / QA / CX       │
                    └──────┬──────────┬──────────┬─────────────┘
                           │          │          │
              ┌────────────▼──┐  ┌────▼────┐  ┌──▼───────────┐
              │ NEXUS (WFM)   │  │SENTINEL │  │ LEDGER       │
              │ Carga trabajo │  │Calidad  │  │ Financiero   │
              │ TMO, Staffing │  │KPIs, RAC│  │ Facturacion  │
              └──────┬────────┘  └────┬────┘  └──┬───────────┘
                     │                │           │
                     └────────┬───────┘───────────┘
                              │
                    ┌─────────▼──────────┐
                    │  ATLAS (Estrategia) │
                    │  WBR / MBR / Cross  │
                    └─────────────────────┘
```

---

## Requisitos del Sistema

### Hardware Minimo
- **CPU**: 4 cores
- **RAM**: 16 GB (8 GB minimo sin GPU)
- **Disco**: 20 GB libres (modelos IA)
- **GPU**: NVIDIA con 8GB+ VRAM (recomendado, no obligatorio)

### Software
- Python 3.11+
- CUDA 12.1+ (si usa GPU)
- Ollama o LM Studio (para LLM local)

---

## Instalacion

### 1. Clonar el repositorio
```bash
git clone https://github.com/anotami/Callcenter.git
cd Callcenter
```

### 2. Crear entorno virtual
```bash
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate         # Windows
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

O usar los scripts automaticos:
```bash
# Linux/Mac
chmod +x install.sh && ./install.sh

# Windows
install.bat
```

### 4. Configurar variables de entorno
```bash
cp .env.example .env
```

Editar `.env` con tus valores:
```env
# Token de HuggingFace (necesario para pyannote diarizacion)
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxx

# LLM Local
LLM_BASE_URL=http://localhost:1234/v1    # LM Studio
# LLM_BASE_URL=http://localhost:11434/v1 # Ollama
LLM_MODEL=llama-3.1-8b-instruct

# Whisper (transcripcion)
WHISPER_MODEL=large-v3
WHISPER_DEVICE=cuda    # o "cpu" si no tienes GPU
WHISPER_LANGUAGE=es

# SQL Server (opcional)
SQL_SERVER=localhost
SQL_DATABASE=CallCenter
SQL_USERNAME=sa
SQL_PASSWORD=tu_password
```

### 5. Instalar LLM local

**Opcion A: Ollama (recomendado)**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.1:8b
```

**Opcion B: LM Studio**
- Descargar desde https://lmstudio.ai
- Descargar modelo Llama 3.1 8B
- Iniciar servidor local en puerto 1234

### 6. Obtener token HuggingFace (para diarizacion)
1. Crear cuenta en https://huggingface.co
2. Ir a Settings → Access Tokens → New token
3. Aceptar terminos de https://huggingface.co/pyannote/speaker-diarization-3.1
4. Copiar el token en `.env`

### 7. Verificar instalacion
```bash
python verify_setup.py
```

---

## Uso

### Interfaz Web (Streamlit)
```bash
streamlit run app.py
```

Abre http://localhost:8501 en tu navegador.

**Como usar los agentes:**

1. **Selecciona un agente** en el panel lateral izquierdo
2. **Elige una habilidad** de la lista
3. **Sube un archivo** (CSV, Excel, JSON o audio) o **pega texto**
4. **Selecciona resultados previos** si la habilidad los acepta
5. **Ejecuta** y ve el resultado con metricas visuales
6. Los resultados se guardan automaticamente y quedan disponibles para otros agentes

**Ejemplo de flujo completo:**

```
1. CORTEX → Ingesta ACD     (sube archivo CSV con datos de llamadas)
2. CORTEX → Ingesta QA      (sube archivo con evaluaciones de calidad)
3. NEXUS  → Calcular TMO    (usa resultado de ingesta ACD)
4. NEXUS  → Staffing        (usa resultados de carga + TMO)
5. SENTINEL → Monitoreo KPIs (usa resultados de CORTEX)
6. LEDGER → Facturacion     (usa datos ACD + parametros de tarifa)
7. ATLAS  → Consolidar WBR  (selecciona todos los resultados de la semana)
```

### Pipeline CLI (procesamiento de audio)
```bash
# Procesar un audio
python main.py

# Procesar sin base de datos
python main.py --no-db

# Procesamiento paralelo
python main.py --parallel
```

Coloca archivos de audio en la carpeta `audio/` antes de ejecutar.

---

## Datos de Ejemplo

La carpeta `examples/` contiene archivos CSV de ejemplo para probar cada agente:

- **`acd_sample.csv`** → Para CORTEX (Ingesta ACD) y NEXUS (Carga/TMO)
- **`qa_sample.csv`** → Para CORTEX (Ingesta QA) y SENTINEL (Monitoreo KPIs)
- **`cx_sample.csv`** → Para CORTEX (Ingesta CX)

---

## Stack Tecnologico

| Componente | Tecnologia |
|---|---|
| Transcripcion | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CTranslate2) |
| Diarizacion | [pyannote.audio](https://github.com/pyannote/pyannote-audio) 3.1 |
| LLM Local | [Ollama](https://ollama.ai) / [LM Studio](https://lmstudio.ai) + Llama 3.1 |
| UI | [Streamlit](https://streamlit.io) |
| Datos | pandas + SQL Server (pyodbc) |
| GPU | PyTorch + CUDA 12.1 |

---

## Criterios de Evaluacion de Calidad

SENTINEL evalua llamadas contra 8 criterios profesionales:

| # | Criterio | Que evalua |
|---|---|---|
| 1 | Saludo y presentacion | Protocolo de apertura correcto |
| 2 | Validacion del cliente | Verificacion de identidad |
| 3 | Identificacion del motivo | Escucha activa y comprension |
| 4 | Gestion del requerimiento | Resolucion efectiva |
| 5 | Comunicacion efectiva | Claridad y lenguaje apropiado |
| 6 | Empatia y tono humano | Conexion emocional con el cliente |
| 7 | Contencion en crisis | Manejo de clientes molestos |
| 8 | Cierre adecuado | Resumen y despedida correcta |

Puntaje final: **0-100** con calificacion por criterio (OK / PARCIAL / FAIL).

---

## Estructura de Resultados

Los resultados se guardan en `agent_results/` con versionado automatico:

```
agent_results/
├── cortex/
│   ├── ingesta_acd_2025-03-15_v1.json
│   ├── ingesta_qa_2025-03-15_v1.json
│   └── transcribir_audio_2025-03-15_v1.json
├── nexus/
│   ├── calcular_tmo_2025-03-15_v1.json
│   └── calcular_staffing_2025-03-15_v1.json
├── sentinel/
│   └── evaluar_llamada_2025-03-15_v1.json
├── ledger/
│   └── calcular_facturacion_2025-03-15_v1.json
└── atlas/
    └── consolidar_wbr_2025-03-15_v1.json
```

Cada archivo JSON contiene: agente, skill, version, fecha, hora, input_summary y resultado completo.

---

## Solucion de Problemas

| Problema | Solucion |
|---|---|
| `CUDA not available` | Instalar PyTorch con CUDA: `pip install torch --index-url https://download.pytorch.org/whl/cu121` |
| `HF_TOKEN invalid` | Verificar token en huggingface.co y aceptar terminos de pyannote |
| `LLM connection refused` | Verificar que Ollama/LM Studio esta corriendo en el puerto configurado |
| `Out of memory` | Usar `WHISPER_MODEL=medium` o `WHISPER_DEVICE=cpu` |
| `pyodbc error` | Instalar ODBC Driver 17 o usar `--no-db` para omitir SQL Server |

---

## Repositorio

- **GitHub**: https://github.com/anotami/Callcenter
- **Branch principal**: `main`
- **Branch desarrollo**: `claude/improve-app-code-K7Y34`

---

## Licencia

Uso interno. Todos los derechos reservados.
