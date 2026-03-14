"""
Definicion de agentes y sus habilidades.
Cada agente es un miembro del equipo con skills especificos.
"""

AGENTS = {
    "transcriptor": {
        "nombre": "Transcriptor",
        "icono": "mic",
        "color": "#4A90D9",
        "descripcion": "Especialista en convertir audio a texto con alta precision. Detecta idioma automaticamente y genera transcripciones con timestamps.",
        "habilidades": [
            {
                "id": "transcribir_audio",
                "nombre": "Transcribir Audio",
                "descripcion": "Convierte un archivo de audio a texto usando IA (faster-whisper). Genera segmentos con timestamps precisos.",
                "datos_necesarios": ["Archivo de audio (.mp3, .wav, .m4a, .ogg, .flac, .wma)"],
                "resultado": "Transcripcion completa con timestamps por segmento",
                "acepta_archivo": True,
                "extensiones": [".mp3", ".wav", ".m4a", ".ogg", ".flac", ".wma"],
                "acepta_texto": False,
                "acepta_resultado_previo": False,
            },
            {
                "id": "detectar_idioma",
                "nombre": "Detectar Idioma",
                "descripcion": "Analiza un fragmento del audio para determinar el idioma hablado y su probabilidad.",
                "datos_necesarios": ["Archivo de audio"],
                "resultado": "Idioma detectado con porcentaje de confianza",
                "acepta_archivo": True,
                "extensiones": [".mp3", ".wav", ".m4a", ".ogg", ".flac", ".wma"],
                "acepta_texto": False,
                "acepta_resultado_previo": False,
            },
        ],
    },
    "diarizador": {
        "nombre": "Diarizador",
        "icono": "people-fill",
        "color": "#7B68EE",
        "descripcion": "Experto en identificar quien habla en cada momento de una conversacion. Separa las voces y asigna roles (Asesor/Cliente).",
        "habilidades": [
            {
                "id": "identificar_hablantes",
                "nombre": "Identificar Hablantes",
                "descripcion": "Detecta cuantas personas hablan en el audio y en que momentos interviene cada una usando pyannote.",
                "datos_necesarios": ["Archivo de audio"],
                "resultado": "Segmentos temporales etiquetados por hablante",
                "acepta_archivo": True,
                "extensiones": [".mp3", ".wav", ".m4a", ".ogg", ".flac", ".wma"],
                "acepta_texto": False,
                "acepta_resultado_previo": False,
            },
            {
                "id": "generar_dialogo",
                "nombre": "Generar Dialogo Completo",
                "descripcion": "Combina la transcripcion con la diarizacion para generar un dialogo estructurado con roles (Asesor, Cliente) y timestamps.",
                "datos_necesarios": [
                    "Archivo de audio",
                    "O resultado previo de Transcriptor + archivo de audio",
                ],
                "resultado": "Dialogo formateado: [timestamp] Asesor/Cliente: texto",
                "acepta_archivo": True,
                "extensiones": [".mp3", ".wav", ".m4a", ".ogg", ".flac", ".wma"],
                "acepta_texto": False,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["transcriptor"],
            },
        ],
    },
    "evaluador": {
        "nombre": "Evaluador",
        "icono": "clipboard-check",
        "color": "#28A745",
        "descripcion": "Analista de calidad que evalua las llamadas contra 8 criterios profesionales usando LLM. Genera puntajes y recomendaciones.",
        "habilidades": [
            {
                "id": "evaluar_calidad",
                "nombre": "Evaluar Calidad de Atencion",
                "descripcion": "Evalua un dialogo de call center contra 8 criterios de calidad (saludo, empatia, gestion, cierre, etc). Usa un LLM local para el analisis.",
                "datos_necesarios": [
                    "Dialogo/transcripcion de la llamada (texto)",
                    "O resultado previo de Diarizador o Transcriptor",
                ],
                "resultado": "Evaluacion JSON con puntaje 0-100, calificacion por criterio y recomendaciones",
                "acepta_archivo": False,
                "acepta_texto": True,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["diarizador", "transcriptor"],
            },
            {
                "id": "generar_reporte",
                "nombre": "Generar Reporte de Calidad",
                "descripcion": "Genera un reporte formateado y legible a partir de una evaluacion. Incluye estado por criterio, puntaje total y recomendaciones.",
                "datos_necesarios": [
                    "Resultado previo de evaluacion (JSON)",
                    "O resultado previo del Evaluador",
                ],
                "resultado": "Reporte de texto formateado con indicadores visuales",
                "acepta_archivo": False,
                "acepta_texto": True,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["evaluador"],
            },
        ],
    },
    "atlas": {
        "nombre": "Atlas",
        "icono": "graph-up-arrow",
        "color": "#FF6B35",
        "descripcion": "Centro de inteligencia del equipo. Consume los resultados de todos los agentes para generar analisis cruzados, tendencias y dashboards.",
        "habilidades": [
            {
                "id": "analisis_cruzado",
                "nombre": "Analisis Cruzado",
                "descripcion": "Toma resultados de multiples evaluaciones y genera un analisis comparativo: mejores/peores areas, patrones comunes, outliers.",
                "datos_necesarios": [
                    "2 o mas resultados previos de cualquier agente",
                ],
                "resultado": "Analisis comparativo con insights y patrones detectados",
                "acepta_archivo": True,
                "extensiones": [".json", ".csv", ".txt"],
                "acepta_texto": True,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["evaluador", "diarizador", "transcriptor"],
                "multi_resultado": True,
            },
            {
                "id": "detectar_tendencias",
                "nombre": "Detectar Tendencias",
                "descripcion": "Analiza evaluaciones a lo largo del tiempo para identificar tendencias de mejora o deterioro en la calidad.",
                "datos_necesarios": [
                    "Resultados previos de evaluaciones (multiples fechas)",
                ],
                "resultado": "Reporte de tendencias con graficos y recomendaciones estrategicas",
                "acepta_archivo": True,
                "extensiones": [".json", ".csv"],
                "acepta_texto": False,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["evaluador"],
                "multi_resultado": True,
            },
            {
                "id": "resumen_equipo",
                "nombre": "Resumen del Equipo",
                "descripcion": "Genera un resumen ejecutivo de toda la actividad del equipo de agentes: tareas completadas, resultados clave, estado general.",
                "datos_necesarios": [
                    "Se alimenta automaticamente del historial de tareas",
                ],
                "resultado": "Dashboard resumen con metricas del equipo",
                "acepta_archivo": False,
                "acepta_texto": False,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["transcriptor", "diarizador", "evaluador"],
                "multi_resultado": True,
            },
        ],
    },
}


def get_agent(agent_id: str) -> dict:
    return AGENTS.get(agent_id, {})


def get_all_agents() -> dict:
    return AGENTS


def get_skill(agent_id: str, skill_id: str) -> dict | None:
    agent = AGENTS.get(agent_id)
    if not agent:
        return None
    for skill in agent["habilidades"]:
        if skill["id"] == skill_id:
            return skill
    return None
