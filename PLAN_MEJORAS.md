# PLAN DE MEJORAS - CallCenter AI Team
## Analisis Estrategico y Hoja de Ruta

---

## 1. DIAGNOSTICO: COMO ESTA HOY

### Tu Equipo Digital (Espejo de la Gerencia)

```
TU (Gerente)  ←→  ATLAS (Estrategia)
    ├── Datos        ←→  CORTEX    (ingesta, validacion)
    ├── WFM          ←→  NEXUS     (capacidad, staffing)
    ├── Calidad      ←→  SENTINEL  (QA, errores criticos)
    └── Finanzas     ←→  LEDGER    (facturacion, bonos, penalidades)
```

### Flujo Actual de Comunicacion

```
HOY: Manual, paso a paso (6-10 clicks por reporte)

  [Usuario sube archivo]
       ↓ click
  [Selecciona CORTEX → Ingesta ACD] → resultado guardado
       ↓ click
  [Selecciona NEXUS → Calcular TMO] → selecciona resultado CORTEX → click
       ↓ click
  [Selecciona SENTINEL → Monitoreo KPIs] → selecciona resultado CORTEX → click
       ↓ click
  [Selecciona LEDGER → Facturacion] → selecciona resultado CORTEX → click
       ↓ click
  [Selecciona ATLAS → Informe 360] → selecciona TODOS los resultados → click
       ↓
  Reporte final
```

**Problema central:** Cada agente es una isla. Tu (ATLAS) tiene que ir oficina por oficina pidiendo reportes.

---

## 2. PROBLEMAS DETECTADOS (por prioridad)

### CRITICO: Sin Pipeline Automatico
- **Impacto:** 6-10 clicks para un reporte que deberia ser 1
- **Causa:** No existe orquestacion; todo es manual via UI
- **En la vida real:** Es como si tu equipo no tuviera reuniones regulares y tuvieras que ir escritorio por escritorio

### ALTO: Comunicacion entre Agentes Deficiente
- Los agentes no se "hablan" entre si
- ATLAS recibe datos truncados (limite de 4000 chars en prompts)
- Se pierde informacion critica en la consolidacion
- No hay memoria compartida entre sesiones

### ALTO: Ingesta No Optimizada para Volumen
- Sin limite de tamano de archivo (puede crashear con >500MB)
- Sin chunking para archivos grandes
- `_df_summary()` solo muestra 5 filas de muestra
- Los KPIs se detectan por keywords rigidos (no adaptativo)

### MEDIO: ATLAS (Tu Rol) Pierde Contexto
- `_build_atlas_insumos` trunca datos a 4000 caracteres
- Con 4 agentes reportando, cada uno recibe ~1000 chars
- Datos criticos se pierden en la truncacion
- No hay priorizacion de que datos son mas importantes

### MEDIO: LLM Subutilizado
- Temperatura fija 0.1 para todo (bueno para datos, malo para insights)
- Max tokens 2000-3000 (limita reportes complejos)
- Sin cache de prompts (repite contexto identico)
- Sin validacion de calidad del output JSON

### BAJO: UI Requiere Muchos Clicks
- No hay vista "Dashboard" consolidado
- No hay "un click para todo"
- Historial sin busqueda ni filtros
- Sin comparacion entre periodos

---

## 3. PLAN DE MEJORAS

### FASE 1: Pipeline Automatico (Mayor Impacto, Menor Riesgo)
**Objetivo:** De 10 clicks a 1 click

```
PROPUESTA: "Pipeline Express"

  [Usuario sube archivo] → 1 CLICK → "Ejecutar Pipeline Completo"
       ↓ automatico
  CORTEX analiza tipo de datos y ingesta
       ↓ automatico
  NEXUS calcula metricas WFM (si aplica)
       ↓ automatico
  SENTINEL evalua calidad (si aplica)
       ↓ automatico
  LEDGER calcula financieros (si aplica)
       ↓ automatico
  ATLAS consolida todo en Informe 360
       ↓
  Dashboard interactivo + Graficos + PDF
```

**Implementacion:**
- Nuevo modulo `pipeline.py` con funcion `run_full_pipeline()`
- Detecta tipo de datos y decide que agentes activar
- Pasa resultados automaticamente entre agentes
- Barra de progreso en tiempo real
- Boton "Pipeline Express" en la pagina principal

**Archivos a modificar:**
- Crear: `pipeline.py`
- Modificar: `app.py` (agregar boton pipeline y vista de progreso)
- No rompe nada existente (es aditivo)

---

### FASE 2: Memoria Compartida y Contexto Inteligente
**Objetivo:** Que ATLAS tenga toda la informacion, no fragmentos

```
PROPUESTA: "Memoria de Equipo"

  Cada agente escribe en un "tablero compartido":

  shared_context = {
      "cortex": {resumen_ejecutivo, kpis_clave, alertas},
      "nexus":  {staffing_req, tmo_promedio, ocupacion},
      "sentinel": {score_calidad, errores_criticos, tendencia},
      "ledger": {facturacion_total, bonos, penalidades},
      "metadata": {periodo, archivos_procesados, timestamp}
  }
```

**Implementacion:**
- Cada runner genera un `resumen_ejecutivo` compacto (500 chars max)
- Nuevo formato `agent_brief` con solo KPIs clave por agente
- ATLAS recibe briefs compactos + acceso a datos completos si necesita profundizar
- Elimina truncacion arbitraria de 4000 chars

**Archivos a modificar:**
- Modificar: `agent_runner.py` (agregar `_generate_brief()` a cada runner)
- Modificar: funciones de ATLAS (usar briefs en vez de datos crudos)

---

### FASE 3: Ingesta Inteligente
**Objetivo:** Soportar archivos grandes, detectar tipo automaticamente

```
PROPUESTA: "Ingesta Universal"

  [Archivo cualquiera] → Auto-deteccion:
      ├── Tiene columnas ACD? → ingesta_acd
      ├── Tiene columnas QA? → ingesta_qa
      ├── Tiene columnas CX? → ingesta_cx
      ├── Tiene columnas WFM (60+)? → ingesta_wfm
      └── Desconocido → ingesta_generica + LLM clasifica
```

**Implementacion:**
- Funcion `auto_detect_data_type(df)` que analiza columnas
- Chunking: procesar archivos >100K filas en lotes de 50K
- Validacion de tamano antes de cargar (warning si >200MB)
- `_df_summary()` mejorado con percentiles, outliers, data quality score

**Archivos a modificar:**
- Modificar: `agent_runner.py` (agregar `auto_detect_data_type`, mejorar `_df_summary`)
- No rompe ingestas existentes (detecta y delega)

---

### FASE 4: Dashboard en Tiempo Real
**Objetivo:** Vista de gerente, todo en una pantalla

```
PROPUESTA: "Vista ATLAS"

  ┌─────────────────────────────────────────────────┐
  │  OPERACION: 2024-02       Score: 78/100  🟡     │
  ├──────────┬──────────┬──────────┬────────────────┤
  │ VOLUMEN  │   WFM    │ CALIDAD  │  FINANCIERO    │
  │ 12,450   │ 85% NdS  │ 82/100   │  $45,200,000   │
  │ calls    │ TMO: 401s│ 3 RAC    │  Bono: 12%     │
  │ 🟢 +5%   │ 🟡 -2%   │ 🟢 +3%   │  🔴 Penalidad  │
  ├──────────┴──────────┴──────────┴────────────────┤
  │  [Graficos Interactivos - Plotly]                │
  │  Tendencia | Cuartiles | Composicion | Radar     │
  ├─────────────────────────────────────────────────┤
  │  ALERTAS: 2 criticas, 5 warnings                │
  │  > TMO alto en MASIVO_MOVIL (+15% vs target)    │
  │  > 23 agentes en cuartil 4                      │
  ├─────────────────────────────────────────────────┤
  │  [Descargar PDF] [Descargar Excel] [Compartir]  │
  └─────────────────────────────────────────────────┘
```

**Implementacion:**
- Nueva pagina/tab "Dashboard" en app.py
- Se alimenta automaticamente del ultimo pipeline ejecutado
- Graficos Plotly integrados (ya implementados en chart_builder.py)
- Comparacion vs periodo anterior
- Semaforos por area

**Archivos a modificar:**
- Modificar: `app.py` (nueva seccion Dashboard)
- Reutiliza: `chart_builder.py` (ya existe)

---

### FASE 5: LLM Optimizado
**Objetivo:** Mejores respuestas, menor costo, mas rapido

**5a. Cache de Contexto:**
- Cachear system prompts (identicos entre llamadas)
- Cachear datos de referencia (targets, SLAs)
- Ahorro estimado: 30-40% tokens

**5b. Temperatura Adaptativa:**
- Ingesta/calculo: 0.1 (preciso)
- Analisis/insights: 0.3 (creativo)
- Reportes ejecutivos: 0.2 (equilibrado)

**5c. Validacion de Output:**
- Verificar que JSON sea valido antes de guardar
- Retry automatico si LLM devuelve formato incorrecto
- Schema validation por tipo de skill

**5d. Tokens Adaptativos:**
- Ingesta simple: 1500 tokens
- Analisis complejo (ATLAS 360): 4000 tokens
- Evaluar si el modelo soporta mas contexto

---

## 4. COMPARACION: MODELO ACTUAL vs PROPUESTO

```
                    HOY                         PROPUESTO
Orquestacion    Manual (usuario)            Pipeline automatico
Clicks           6-10 por reporte            1-2 por reporte
Comunicacion    Via archivos JSON            Memoria compartida + briefs
Contexto ATLAS  4000 chars truncados         Briefs inteligentes + drill-down
Ingesta          Por tipo (manual)           Auto-deteccion universal
Archivos grandes Crash potencial             Chunking + validacion
Dashboard       No existe                   Vista consolidada en 1 pantalla
Graficos        Recien agregados            Integrados en pipeline + PDF
LLM tokens      Sin optimizar               Cache + temperatura adaptativa
Comparacion     No existe                   vs periodo anterior automatico
```

---

## 5. ORDEN DE IMPLEMENTACION

| Fase | Esfuerzo | Impacto | Riesgo | Prioridad |
|------|----------|---------|--------|-----------|
| 1. Pipeline Express | Medio | MUY ALTO | Bajo | PRIMERO |
| 2. Memoria Compartida | Medio | Alto | Bajo | SEGUNDO |
| 3. Ingesta Inteligente | Bajo | Medio | Bajo | TERCERO |
| 4. Dashboard ATLAS | Medio | Alto | Bajo | CUARTO |
| 5. LLM Optimizado | Bajo | Medio | Bajo | QUINTO |

**Principio guia:** Cada fase es aditiva y no rompe funcionalidad existente.

---

## 6. METRICAS DE EXITO

- **Clicks para reporte completo:** de 10 → 2
- **Tiempo de generacion:** de 15min manual → 3min automatico
- **Datos que llegan a ATLAS:** de ~30% → 95%
- **Soporte archivos grandes:** de crash → hasta 1M filas
- **Satisfaccion del gerente:** Dashboard en 1 pantalla vs navegar 5 agentes

---

## 7. ARQUITECTURA OBJETIVO

```
                    ┌──────────────┐
                    │   USUARIO    │
                    │  (Gerente)   │
                    └──────┬───────┘
                           │ 1 click
                    ┌──────▼───────┐
                    │  PIPELINE    │
                    │  EXPRESS     │ ← Orquestador automatico
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼──┐  ┌─────▼──┐  ┌─────▼──┐
        │CORTEX  │  │SENTINEL│  │LEDGER  │
        │(Datos) │  │(Calidad)│ │(Finanzas)│
        └───┬────┘  └───┬────┘  └───┬────┘
            │            │            │
            └────┬───────┘            │
           ┌─────▼──┐                 │
           │ NEXUS  │                 │
           │ (WFM)  │                 │
           └───┬────┘                 │
               │                      │
        ┌──────▼──────────────────────▼──┐
        │     MEMORIA COMPARTIDA         │
        │  (briefs + KPIs + alertas)     │
        └──────────────┬─────────────────┘
                       │
                ┌──────▼───────┐
                │    ATLAS     │
                │ (Dashboard)  │ ← Tu vision consolidada
                └──────┬───────┘
                       │
              ┌────────▼────────┐
              │   DASHBOARD     │
              │  Graficos + PDF │
              │  1 pantalla     │
              └─────────────────┘
```

---

*Documento generado como hoja de ruta. Cada fase puede implementarse independientemente sin afectar las demas.*
