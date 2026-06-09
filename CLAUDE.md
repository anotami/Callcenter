# Callcenter — Plataforma Multi-Agente WFM

## Arquitectura

Sistema multi-agente para operaciones de Call Center con 5 agentes especializados que se pasan datos entre sí:

```
CORTEX (Datos) → NEXUS (WFM) → ATLAS (Reportes)
                  SENTINEL (Calidad) ↗
                  LEDGER (Finanzas) ↗
```

## Agentes disponibles

| Agente | Rol | Invocación |
|--------|-----|------------|
| **CORTEX** | Ingesta de datos (ACD, QA, CX, Cubo Tráfico, Malla, GTR) | `@cortex` |
| **NEXUS** | Ciclo WFM completo (6 OUTPUTs, Erlang C) | `@nexus` |
| **SENTINEL** | Calidad y monitoreo (evaluación llamadas, RAC, KPIs) | `@sentinel` |
| **LEDGER** | Financiero (facturación, bonos, penalidades con COP/COR) | `@ledger` |
| **ATLAS** | Inteligencia estratégica (WBR, MBR, informes 360) | `@atlas` |
| **ORQUESTADOR** | Coordina agentes, ejecuta pipelines completos | `@orquestador` |

## Flujo de datos entre agentes

Los agentes se comunican mediante archivos JSON en `agent_results/{agent_id}/`:

1. **CORTEX** ingesta archivos crudos → produce `agent_results/cortex/*.json`
2. **NEXUS** lee resultados de CORTEX → calcula WFM → produce `agent_results/nexus/*.json`
3. **SENTINEL** lee datos de QA/audio → evalúa calidad → produce `agent_results/sentinel/*.json`
4. **LEDGER** lee COP/COR de NEXUS → calcula finanzas → produce `agent_results/ledger/*.json`
5. **ATLAS** lee TODOS los resultados → consolida reportes ejecutivos

## Convenciones de código

- Idioma: español para variables, funciones, comentarios, UI
- Estilo: snake_case, prefijo `run_` para skill runners, `_` para funciones internas
- Datos: siempre JSON serializable, usar `_SafeEncoder` para numpy/pandas
- Resultados: versionados como `{skill_id}_{YYYY-MM-DD}_v{N}.json`
- LLM: usar `_llm_analyze()` de `agent_runner.py` (maneja fallback y cache)

## Estructura de archivos clave

```
app.py                 → UI Streamlit (dashboard)
agents_config.py       → Definición de 5 agentes + 32 skills
agent_runner.py        → Motor de ejecución + SKILL_RUNNERS dict
pipeline_runner.py     → 6 pipelines predefinidos (cadenas de skills)
prompt_manager.py      → Prompts versionados por agente
analyzer.py            → Integración LLM multi-provider
chart_builder.py       → Auto-visualización Plotly
config.py              → Configuración centralizada
agent_results/         → Resultados versionados por agente
agent_prompts/         → Prompts versionados por agente
examples/              → Datos de ejemplo (acd_sample.csv, qa_sample.csv, etc.)
```

## Contrato de datos entre agentes

Todo resultado sigue esta estructura:
```json
{
  "agent_id": "cortex",
  "skill_id": "ingesta_acd",
  "skill_name": "Ingesta de Datos ACD",
  "timestamp": "2026-06-09T10:30:00",
  "version": 1,
  "prompt_version": 0,
  "input_summary": "acd_sample.csv",
  "resultado": {
    "resumen": "...",
    "kpis": {"llamadas": 270, "nds": 80.5, "tmo": 362.5},
    "datos": [...],
    "alertas": [...]
  }
}
```

## Cómo ejecutar

```bash
# UI web
streamlit run app.py

# Ejecutar skill individual desde Python
python -c "
from agent_runner import execute_skill
result = execute_skill('cortex', 'ingesta_acd', 'Ingesta ACD',
                       file_bytes=open('examples/acd_sample.csv','rb').read(),
                       filename='acd_sample.csv')
print(result)
"

# Pipeline completo
python -c "
from pipeline_runner import execute_pipeline
results = execute_pipeline('ciclo_wfm_completo',
                           file_bytes=open('datos.csv','rb').read(),
                           filename='datos.csv')
"
```

## Datos de ejemplo

- `examples/acd_sample.csv` — datos ACD (llamadas, NdS, TMO por intervalo)
- `examples/qa_sample.csv` — evaluaciones de calidad por agente
- `examples/cx_sample.csv` — encuestas CSAT/NPS/CES
- `examples/metricas_x_antiguedad_sample.csv` — métricas WFM por antigüedad
