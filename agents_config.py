"""
Definicion de agentes y sus habilidades.
Equipo operativo de Call Center con 5 roles especializados.

CORTEX   -> Datos e ingesta
NEXUS    -> WFM y capacidad
SENTINEL -> Calidad y monitoreo
LEDGER   -> Financiero
ATLAS    -> Estrategia ejecutiva
"""

AGENTS = {
    # ── 0. MODELOS: Configuracion LLM ──────────────────────────────────
    "modelos": {
        "nombre": "MODELOS",
        "rol": "Configuracion LLM",
        "icono": "cpu",
        "color": "#17A2B8",
        "descripcion": (
            "Detecta y prueba los modelos LLM disponibles en tu servidor local (Ollama/LM Studio). "
            "Permite seleccionar cual modelo usaran los demas agentes para sus analisis."
        ),
        "habilidades": [
            {
                "id": "probar_modelos",
                "nombre": "Probar Modelos Disponibles",
                "descripcion": (
                    "Conecta al servidor LLM, lista todos los modelos disponibles, "
                    "y permite probar cada uno con un mensaje de prueba para verificar "
                    "que responden correctamente."
                ),
                "datos_necesarios": [],
                "resultado": "Lista de modelos con estado de conexion y modelo seleccionado",
                "acepta_archivo": False,
                "acepta_texto": False,
                "acepta_resultado_previo": False,
            },
        ],
    },

    # ── 1. CORTEX: Datos ───────────────────────────────────────────────
    "cortex": {
        "nombre": "CORTEX",
        "rol": "Datos",
        "icono": "database",
        "color": "#4A90D9",
        "descripcion": (
            "Especialista en ingesta, documentacion y validacion de fuentes de datos. "
            "Procesa archivos ACD, reportes de QA y encuestas CX. "
            "Tambien transcribe y diariza audios de llamadas."
        ),
        "habilidades": [
            {
                "id": "ingesta_acd",
                "nombre": "Ingesta de Datos ACD",
                "descripcion": (
                    "Carga y procesa archivos de datos del sistema ACD (Automatic Call Distribution). "
                    "Valida formato, detecta columnas clave (llamadas recibidas, atendidas, abandonadas, "
                    "tiempos de espera, TMO) y genera un resumen estructurado."
                ),
                "datos_necesarios": ["Archivo ACD (.csv, .xlsx, .json)"],
                "resultado": "Resumen estructurado de datos ACD con metricas clave y validacion",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": False,
                "acepta_resultado_previo": False,
            },
            {
                "id": "ingesta_qa",
                "nombre": "Ingesta de Datos QA",
                "descripcion": (
                    "Carga reportes de Quality Assurance. Extrae metricas de calidad, "
                    "puntajes por agente, criterios evaluados y tendencias de cumplimiento."
                ),
                "datos_necesarios": ["Archivo QA (.csv, .xlsx, .json)"],
                "resultado": "Datos QA estructurados con puntajes y distribucion por criterio",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": False,
                "acepta_resultado_previo": False,
            },
            {
                "id": "ingesta_cx",
                "nombre": "Ingesta de Encuestas CX",
                "descripcion": (
                    "Procesa encuestas de experiencia del cliente (CSAT, NPS, CES). "
                    "Calcula indicadores de satisfaccion y detecta verbatims negativos."
                ),
                "datos_necesarios": ["Archivo de encuestas CX (.csv, .xlsx, .json)"],
                "resultado": "Indicadores CX (CSAT, NPS) con distribucion y verbatims destacados",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": False,
                "acepta_resultado_previo": False,
            },
            {
                "id": "validar_fuentes",
                "nombre": "Validar y Documentar Fuentes",
                "descripcion": (
                    "Toma resultados de ingestas previas y valida consistencia entre fuentes: "
                    "cruza volumenes ACD vs registros QA, verifica completitud de datos, "
                    "y genera un reporte de calidad de datos."
                ),
                "datos_necesarios": ["2 o mas resultados previos de ingesta"],
                "resultado": "Reporte de validacion cruzada con alertas de inconsistencias",
                "acepta_archivo": False,
                "acepta_texto": False,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["cortex"],
                "multi_resultado": True,
            },
            {
                "id": "transcribir_audio",
                "nombre": "Transcribir Audio",
                "descripcion": (
                    "Convierte un archivo de audio de llamada a texto usando IA (faster-whisper). "
                    "Genera segmentos con timestamps precisos."
                ),
                "datos_necesarios": ["Archivo de audio (.mp3, .wav, .m4a, .ogg, .flac, .wma)"],
                "resultado": "Transcripcion completa con timestamps por segmento",
                "acepta_archivo": True,
                "extensiones": [".mp3", ".wav", ".m4a", ".ogg", ".flac", ".wma"],
                "acepta_texto": False,
                "acepta_resultado_previo": False,
            },
            {
                "id": "generar_dialogo",
                "nombre": "Generar Dialogo con Hablantes",
                "descripcion": (
                    "Transcribe y diariza un audio para generar un dialogo estructurado "
                    "con roles (Asesor/Cliente) y timestamps."
                ),
                "datos_necesarios": ["Archivo de audio"],
                "resultado": "Dialogo formateado: [timestamp] Asesor/Cliente: texto",
                "acepta_archivo": True,
                "extensiones": [".mp3", ".wav", ".m4a", ".ogg", ".flac", ".wma"],
                "acepta_texto": False,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["cortex"],
            },
        ],
    },

    # ── 2. NEXUS: WFM Capacidad ───────────────────────────────────────
    "nexus": {
        "nombre": "NEXUS",
        "rol": "WFM Capacidad",
        "icono": "calculator",
        "color": "#7B68EE",
        "descripcion": (
            "Experto en Workforce Management. Calcula carga de trabajo, TMO y staffing "
            "necesario. Proyecta demanda y dimensiona equipos para cumplir niveles de servicio."
        ),
        "habilidades": [
            {
                "id": "calcular_carga_trabajo",
                "nombre": "Calcular Carga de Trabajo",
                "descripcion": (
                    "A partir de datos ACD o volumetria, calcula la carga de trabajo por intervalo, "
                    "dia, semana. Identifica picos y valles de demanda."
                ),
                "datos_necesarios": [
                    "Datos ACD (resultado de CORTEX) o archivo de volumetria",
                ],
                "resultado": "Carga de trabajo por periodo con picos, valles y distribucion horaria",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": False,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["cortex"],
            },
            {
                "id": "calcular_tmo",
                "nombre": "Calcular TMO",
                "descripcion": (
                    "Calcula el Tiempo Medio de Operacion (TMO = AHT) desglosado en "
                    "tiempo de conversacion (talk time), hold y after call work (ACW). "
                    "Detecta outliers y calcula TMO objetivo."
                ),
                "datos_necesarios": [
                    "Datos ACD con tiempos detallados o archivo de tiempos",
                ],
                "resultado": "TMO desglosado (talk/hold/ACW), outliers y TMO objetivo",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": False,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["cortex"],
            },
            {
                "id": "calcular_staffing",
                "nombre": "Calcular Staffing (Erlang C)",
                "descripcion": (
                    "Calcula el numero de agentes necesarios para cumplir el nivel de servicio "
                    "objetivo usando el modelo Erlang C. Considera carga, TMO, shrinkage y "
                    "nivel de servicio target (ej: 80/20)."
                ),
                "datos_necesarios": [
                    "Carga de trabajo y TMO (resultados de NEXUS) o parametros manuales",
                ],
                "resultado": "Staffing requerido por intervalo con ocupacion y nivel de servicio proyectado",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": True,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["nexus", "cortex"],
                "multi_resultado": True,
            },
        ],
    },

    # ── 3. SENTINEL: Calidad ──────────────────────────────────────────
    "sentinel": {
        "nombre": "SENTINEL",
        "rol": "Calidad",
        "icono": "shield-check",
        "color": "#28A745",
        "descripcion": (
            "Guardian de calidad del call center. Monitorea KPIs de calidad, "
            "detecta errores criticos (RAC - Resolucion al Cliente) y evalua "
            "llamadas contra criterios profesionales usando IA."
        ),
        "habilidades": [
            {
                "id": "evaluar_llamada",
                "nombre": "Evaluar Calidad de Llamada",
                "descripcion": (
                    "Evalua un dialogo de call center contra 8 criterios de calidad "
                    "(saludo, validacion, gestion, empatia, cierre, etc). "
                    "Usa un LLM local para el analisis objetivo."
                ),
                "datos_necesarios": [
                    "Dialogo/transcripcion (texto o resultado de CORTEX)",
                ],
                "resultado": "Evaluacion con puntaje 0-100, calificacion por criterio y recomendaciones",
                "acepta_archivo": False,
                "acepta_texto": True,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["cortex"],
            },
            {
                "id": "monitoreo_kpis",
                "nombre": "Monitoreo de KPIs de Calidad",
                "descripcion": (
                    "Analiza datos de QA para monitorear KPIs clave: "
                    "% cumplimiento de calidad, error critico (RAC), "
                    "precision de evaluacion, calibracion entre evaluadores. "
                    "Genera alertas cuando un KPI esta fuera de rango."
                ),
                "datos_necesarios": [
                    "Datos QA (resultado de CORTEX) o archivo de metricas",
                ],
                "resultado": "Dashboard de KPIs con semaforos, alertas y tendencia",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": False,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["cortex", "sentinel"],
                "multi_resultado": True,
            },
            {
                "id": "detectar_rac",
                "nombre": "Detectar Errores Criticos (RAC)",
                "descripcion": (
                    "Analiza evaluaciones o transcripciones para detectar errores criticos "
                    "de Resolucion al Cliente (RAC): informacion incorrecta, "
                    "procesos no seguidos, compromisos incumplidos, escalamientos omitidos."
                ),
                "datos_necesarios": [
                    "Evaluaciones o dialogos (resultados de SENTINEL o CORTEX)",
                ],
                "resultado": "Lista de errores criticos con severidad, tipo y recomendacion",
                "acepta_archivo": False,
                "acepta_texto": True,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["sentinel", "cortex"],
                "multi_resultado": True,
            },
            {
                "id": "generar_reporte_calidad",
                "nombre": "Generar Reporte de Calidad",
                "descripcion": (
                    "Genera un reporte formateado de calidad a partir de evaluaciones "
                    "realizadas. Incluye estado por criterio, puntaje y recomendaciones."
                ),
                "datos_necesarios": [
                    "Resultado de evaluacion (de SENTINEL)",
                ],
                "resultado": "Reporte de texto formateado con indicadores visuales",
                "acepta_archivo": False,
                "acepta_texto": True,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["sentinel"],
            },
        ],
    },

    # ── 4. LEDGER: Financiero ─────────────────────────────────────────
    "ledger": {
        "nombre": "LEDGER",
        "rol": "Financiero",
        "icono": "currency-dollar",
        "color": "#FFC107",
        "descripcion": (
            "Contador del equipo. Calcula facturacion por volumenes atendidos, "
            "bonos por desempeno segun KPIs alcanzados y penalidades por "
            "incumplimiento de SLAs."
        ),
        "habilidades": [
            {
                "id": "calcular_facturacion",
                "nombre": "Calcular Facturacion",
                "descripcion": (
                    "Calcula la facturacion del periodo basado en llamadas atendidas, "
                    "tarifa por llamada/minuto, y ajustes por tipo de gestion. "
                    "Soporta modelos por transaccion, por minuto o por FTE."
                ),
                "datos_necesarios": [
                    "Datos ACD con volumenes (resultado de CORTEX) o archivo de volumetria",
                    "Parametros de tarifa (texto o archivo de configuracion)",
                ],
                "resultado": "Desglose de facturacion por linea, totales y comparativo vs periodo anterior",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": True,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["cortex", "nexus"],
                "multi_resultado": True,
            },
            {
                "id": "calcular_bonos",
                "nombre": "Calcular Bonos por Desempeno",
                "descripcion": (
                    "Calcula bonificaciones basadas en cumplimiento de KPIs: "
                    "nivel de servicio, calidad (QA score), CSAT, TMO objetivo. "
                    "Aplica la matriz de bonos segun contrato."
                ),
                "datos_necesarios": [
                    "KPIs del periodo (resultados de NEXUS, SENTINEL o CORTEX)",
                    "Tabla de bonos/metas (texto o archivo)",
                ],
                "resultado": "Calculo de bono con detalle de cumplimiento por KPI",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": True,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["cortex", "nexus", "sentinel"],
                "multi_resultado": True,
            },
            {
                "id": "calcular_penalidades",
                "nombre": "Calcular Penalidades",
                "descripcion": (
                    "Calcula penalidades por incumplimiento de SLAs contractuales: "
                    "nivel de servicio bajo target, abandono sobre limite, "
                    "calidad bajo minimo, TMO excedido."
                ),
                "datos_necesarios": [
                    "KPIs del periodo (resultados de otros agentes)",
                    "Tabla de penalidades/SLAs (texto o archivo)",
                ],
                "resultado": "Desglose de penalidades con monto, KPI incumplido y gap vs target",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": True,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["cortex", "nexus", "sentinel"],
                "multi_resultado": True,
            },
        ],
    },

    # ── 5. ATLAS: Estrategia ──────────────────────────────────────────
    "atlas": {
        "nombre": "ATLAS",
        "rol": "Estrategia",
        "icono": "graph-up-arrow",
        "color": "#FF6B35",
        "descripcion": (
            "Centro de inteligencia del equipo. Consolida resultados de todos los agentes "
            "para generar reportes ejecutivos para comites WBR (Weekly Business Review) "
            "y MBR (Monthly Business Review). Vision 360 de la operacion."
        ),
        "habilidades": [
            {
                "id": "consolidar_wbr",
                "nombre": "Consolidar WBR (Semanal)",
                "descripcion": (
                    "Genera el reporte semanal de negocio (Weekly Business Review) consolidando: "
                    "volumetria (CORTEX), staffing (NEXUS), calidad (SENTINEL) y facturacion (LEDGER). "
                    "Incluye semaforos, tendencias vs semana anterior y acciones requeridas."
                ),
                "datos_necesarios": [
                    "Resultados de 2 o mas agentes del periodo semanal",
                ],
                "resultado": "Reporte WBR ejecutivo con KPIs, semaforos y plan de accion",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": True,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["cortex", "nexus", "sentinel", "ledger"],
                "multi_resultado": True,
            },
            {
                "id": "consolidar_mbr",
                "nombre": "Consolidar MBR (Mensual)",
                "descripcion": (
                    "Genera el reporte mensual de negocio (Monthly Business Review). "
                    "Vision completa del mes: tendencias, cumplimiento de SLAs, "
                    "facturacion vs presupuesto, calidad vs target, y recomendaciones estrategicas."
                ),
                "datos_necesarios": [
                    "Resultados acumulados del mes de todos los agentes",
                ],
                "resultado": "Reporte MBR ejecutivo con analisis de tendencias y recomendaciones",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": True,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["cortex", "nexus", "sentinel", "ledger"],
                "multi_resultado": True,
            },
            {
                "id": "analisis_cruzado",
                "nombre": "Analisis Cruzado",
                "descripcion": (
                    "Toma resultados de multiples agentes y genera un analisis comparativo: "
                    "correlaciones entre KPIs (ej: TMO vs calidad, staffing vs abandono), "
                    "patrones, outliers y recomendaciones."
                ),
                "datos_necesarios": [
                    "2 o mas resultados de cualquier agente",
                ],
                "resultado": "Analisis comparativo con correlaciones, patrones y recomendaciones",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": True,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["cortex", "nexus", "sentinel", "ledger"],
                "multi_resultado": True,
            },
            {
                "id": "resumen_equipo",
                "nombre": "Resumen de Actividad del Equipo",
                "descripcion": (
                    "Genera un resumen ejecutivo de toda la actividad del equipo de agentes: "
                    "tareas completadas, datos procesados, evaluaciones realizadas, "
                    "alertas generadas."
                ),
                "datos_necesarios": [
                    "Se alimenta automaticamente del historial de tareas",
                ],
                "resultado": "Dashboard resumen con metricas de actividad del equipo",
                "acepta_archivo": False,
                "acepta_texto": False,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["cortex", "nexus", "sentinel", "ledger"],
                "multi_resultado": True,
            },
            {
                "id": "informe_por_modulo",
                "nombre": "Informe por Modulos",
                "descripcion": (
                    "Genera informes individuales detallados por cada modulo (Datos, Capacidad, "
                    "Calidad, Financiero). Cada informe incluye KPIs, hallazgos, alertas y "
                    "recomendaciones con trazabilidad completa de fuentes."
                ),
                "datos_necesarios": [
                    "Resultados de 1 o mas agentes",
                ],
                "resultado": "Informes detallados por modulo con dashboard, conclusiones y fuentes",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": True,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["cortex", "nexus", "sentinel", "ledger"],
                "multi_resultado": True,
            },
            {
                "id": "informe_consolidado",
                "nombre": "Informe Consolidado 360",
                "descripcion": (
                    "Genera el informe ejecutivo mas completo: consolida TODOS los modulos "
                    "en una vision 360 con dashboard ejecutivo, analisis cruzado, conclusiones "
                    "estrategicas y plan de accion. Indica la fuente de cada dato."
                ),
                "datos_necesarios": [
                    "Resultados de multiples agentes (idealmente todos)",
                ],
                "resultado": "Informe 360 con score de operacion, dashboard, conclusiones y plan de accion",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": True,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["cortex", "nexus", "sentinel", "ledger"],
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
