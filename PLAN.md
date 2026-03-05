# Plan de Implementacion - Sistema IA para Call Center

## Arquitectura del Sistema (4 Procesos)

```
Audio MP3/WAV
      |
      v
[1. Transcripcion] --> Whisper (OpenAI) + PyTorch + CUDA
      |
      v
[2. Diarizacion]   --> pyannote.audio (HuggingFace) - Identifica hablantes
      |
      v
[3. Analisis IA]   --> LM Studio + Llama 3.1 - Evalua calidad de atencion
      |
      v
[4. Base de Datos]  --> SQL Server - Almacena resultados y cruza con demanda
```

---

## Requisitos Previos del PC

- **Python**: 3.11+ (recomendado 3.11, mejor compatibilidad con PyTorch)
- **GPU NVIDIA**: Con soporte CUDA (opcional pero muy recomendado)
- **RAM**: Minimo 16GB (recomendado 32GB para Llama 3.1)
- **Disco**: ~20GB libres para modelos
- **SO**: Windows 10/11 o Linux

---

## FASE 1: Estructura del Proyecto y Dependencias

### Archivos a crear:
```
Callcenter/
  requirements.txt          # Dependencias Python
  config.py                 # Configuracion centralizada
  main.py                   # Pipeline principal (orquestador)
  transcriber.py            # Proceso 1: Transcripcion con Whisper
  diarizer.py               # Proceso 2: Diarizacion con pyannote
  analyzer.py               # Proceso 3: Analisis de calidad con LLM
  database.py               # Proceso 4: Conexion y almacenamiento SQL Server
  prompts.py                # Prompts para evaluacion de calidad
  audio/                    # Directorio para audios de entrada
  output/                   # Directorio para resultados
```

### Dependencias (requirements.txt):
- openai-whisper (transcripcion)
- torch + torchaudio (motor IA)
- pyannote.audio (diarizacion)
- huggingface_hub (descarga de modelos)
- openai (cliente API para LM Studio, compatible)
- pyodbc (conexion SQL Server)
- pandas (manejo de datos)
- python-dotenv (variables de entorno)

---

## FASE 2: Transcripcion de Audio (transcriber.py)

Usar Whisper de OpenAI para convertir audio a texto.

**Funcionalidad:**
- Cargar modelo Whisper (medium o large-v3 segun GPU)
- Transcribir audio completo con timestamps
- Soporte para MP3, WAV, M4A
- Deteccion automatica de idioma (espanol)

**Modelo recomendado:** `large-v3` para mejor precision en espanol

---

## FASE 3: Diarizacion (diarizer.py)

Usar pyannote.audio para separar hablantes (asesor vs cliente).

**Funcionalidad:**
- Identificar segmentos por hablante (SPEAKER_00, SPEAKER_01)
- Combinar con transcripcion de Whisper para obtener dialogo estructurado
- Formato de salida: "Asesor: ... / Cliente: ..."

**Requisito:** Token de HuggingFace (aceptar licencia de pyannote)

---

## FASE 4: Analisis de Calidad con LLM (analyzer.py)

Usar LM Studio con Llama 3.1 para evaluar la atencion.

**8 Criterios de Evaluacion:**
1. Saludo y presentacion
2. Validacion del cliente
3. Identificacion del motivo de llamada
4. Gestion del requerimiento
5. Comunicacion efectiva
6. Empatia y tono humano
7. Contencion de cliente en crisis
8. Cierre adecuado del contacto

**Evaluacion por criterio:** Si cumple / No cumple / Parcial

**Conexion:** API REST de LM Studio (compatible con formato OpenAI, puerto 1234)

---

## FASE 5: Base de Datos SQL Server (database.py)

Almacenar resultados y cruzar con datos de demanda.

**Campos a almacenar:**
- Grupo plataforma
- Registro del evento (intenciones de baja, reclamos, Cross)
- Fecha y hora de llamada
- Proveedor
- Motivo y sub motivo tipificado
- Documento identidad del asesor
- Resultados de evaluacion IA

---

## FASE 6: Pipeline Principal (main.py)

Orquestador que ejecuta todo el flujo:
1. Lee audios del directorio `audio/`
2. Transcribe con Whisper
3. Diariza con pyannote
4. Envia a LLM para analisis
5. Guarda resultados en SQL Server y exporta CSV

---

## SUGERENCIAS DE MEJORA vs. Diagrama Original

### 1. Reemplazar Chocolatey por instalacion directa con pip
> Chocolatey es innecesario. pip + PyTorch con CUDA se instala directo.

### 2. Usar faster-whisper en lugar de whisper original
> **faster-whisper** usa CTranslate2, es ~4x mas rapido y usa menos RAM.
> Misma calidad, mucho mejor rendimiento.

### 3. Usar Ollama en lugar de LM Studio
> **Ollama** es mas ligero, tiene CLI, API REST nativa, y es mas facil
> de automatizar en scripts. LM Studio es mas visual pero menos scriptable.
> Alternativa: ambos son validos, pero Ollama es mejor para automatizacion.

### 4. Agregar procesamiento por lotes (batch)
> Procesar multiples audios en paralelo usando multiprocessing.

### 5. Agregar cache de transcripciones
> Guardar transcripciones en disco para no re-procesar audios ya transcritos.

### 6. Usar WhisperX en lugar de Whisper + pyannote separados
> **WhisperX** integra transcripcion + alineamiento + diarizacion en un solo
> pipeline, lo que simplifica el codigo y mejora la precision temporal.

### 7. Exportar reportes en Excel/HTML
> Ademas de SQL Server, generar reportes visuales automaticos.

### 8. Agregar validacion de calidad de audio
> Antes de transcribir, verificar que el audio tenga calidad suficiente
> (volumen, ruido, duracion minima).

---

## Orden de Implementacion

1. [x] Crear estructura del proyecto y requirements.txt
2. [ ] Implementar config.py con configuracion centralizada
3. [ ] Implementar transcriber.py (Whisper/faster-whisper)
4. [ ] Implementar diarizer.py (pyannote.audio)
5. [ ] Implementar prompts.py (criterios de evaluacion)
6. [ ] Implementar analyzer.py (conexion LM Studio/Ollama)
7. [ ] Implementar database.py (SQL Server)
8. [ ] Implementar main.py (pipeline orquestador)
9. [ ] Testing con audios de ejemplo
