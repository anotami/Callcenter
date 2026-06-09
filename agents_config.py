"""
Definicion de agentes y sus habilidades.
Equipo operativo de Call Center con 5 roles especializados.

CORTEX   -> Datos e ingesta
NEXUS    -> WFM y capacidad
SENTINEL -> Calidad y monitoreo
LEDGER   -> Financiero
ATLAS    -> Estrategia ejecutiva
"""

_SKILL_VISUALIZAR = {
    "id": "visualizar_datos",
    "nombre": "Visualizar Datos",
    "descripcion": (
        "Genera graficos interactivos (Plotly) a partir de resultados previos o archivos de datos. "
        "Detecta automaticamente el tipo de datos y produce los graficos mas adecuados: "
        "barras, lineas, torta, radar, heatmap, box plot, gauge, histogramas y mas. "
        "Permite exportar todos los graficos a PDF o PNG."
    ),
    "datos_necesarios": [
        "Resultado previo de cualquier agente o archivo de datos (.csv, .xlsx)",
    ],
    "resultado": "Graficos interactivos con opcion de exportar a PDF",
    "acepta_archivo": True,
    "extensiones": [".csv", ".xlsx", ".xls", ".json"],
    "acepta_texto": False,
    "acepta_resultado_previo": True,
    "agentes_compatibles": ["cortex", "nexus", "sentinel", "ledger", "atlas"],
    "multi_resultado": True,
}

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
        "rol": "Datos e Ingesta WFM",
        "icono": "database",
        "color": "#4A90D9",
        "descripcion": (
            "Especialista en ingesta, documentacion y validacion de fuentes de datos. "
            "Procesa Cubos de Trafico, Mallas de Proveedor, datos GTR en tiempo real, "
            "archivos ACD, reportes de QA y encuestas CX. "
            "Tambien transcribe y diariza audios de llamadas."
        ),
        "habilidades": [
            {
                "id": "ingesta_cubo_trafico",
                "nombre": "Ingesta Cubo de Trafico",
                "descripcion": (
                    "Carga el Cubo de Trafico historico desde INTEGRATEL. "
                    "Contiene volumen de llamadas por intervalo (30min), dia, semana y mes. "
                    "Detecta columnas: FECHA, INTERVALO, SKILL/COLA, LLAMADAS_RECIBIDAS, "
                    "LLAMADAS_ATENDIDAS, ABANDONADAS, TMO, ASA, NIVEL_SERVICIO. "
                    "Este es el INPUT principal para el pronostico de volumen."
                ),
                "datos_necesarios": ["Archivo Cubo de Trafico (.csv, .xlsx)"],
                "resultado": "Cubo de trafico estructurado con volumenes por intervalo, tendencias y estacionalidad",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": True,
                "acepta_resultado_previo": False,
            },
            {
                "id": "ingesta_malla",
                "nombre": "Ingesta Malla Proveedor",
                "descripcion": (
                    "Carga la Malla de Proveedor desde Kipu. Contiene la programacion "
                    "planificada con campos: FECHA, INTERVALO, PROVEEDOR, PLANIFICADO, "
                    "DISPONIBLE, PRONOSTICO, TMO, NIVEL_INTERVALO. "
                    "Se usa para comparar planificado vs real en el ciclo WFM."
                ),
                "datos_necesarios": ["Archivo Malla Proveedor (.csv, .xlsx)"],
                "resultado": "Malla estructurada con dotacion planificada por intervalo y proveedor",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": True,
                "acepta_resultado_previo": False,
            },
            {
                "id": "ingesta_gtr",
                "nombre": "Ingesta Datos GTR",
                "descripcion": (
                    "Carga datos de Gestion en Tiempo Real (GTR) del proveedor. "
                    "Incluye: FECHA, INTERVALO, LOGUEADOS_REAL, DISPONIBLES_REAL, "
                    "AUX_BREAK, AUX_COACHING, AUX_CAPACITACION, AUX_OTROS, "
                    "LLAMADAS_REAL, TMO_REAL, ATENDIDAS_REAL. "
                    "Datos clave para comparar programado vs real."
                ),
                "datos_necesarios": ["Archivo GTR con datos reales (.csv, .xlsx)"],
                "resultado": "Datos GTR estructurados con logueados, disponibles y auxiliares reales",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": True,
                "acepta_resultado_previo": False,
            },
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
            _SKILL_VISUALIZAR,
        ],
    },

    # ── 2. NEXUS: WFM Capacidad ───────────────────────────────────────
    "nexus": {
        "nombre": "NEXUS",
        "rol": "WFM Ciclo Completo",
        "icono": "calculator",
        "color": "#7B68EE",
        "descripcion": (
            "Experto en Workforce Management con ciclo completo: "
            "Pronostico (Erlang con cubo de trafico) → Planificacion (+10% + reductores) → "
            "Programacion (turnos, TNPs, breaks) → GTR (real vs planificado) → "
            "Reportes (COP/COR). Genera los 6 OUTPUTs del proceso WFM."
        ),
        "habilidades": [
            {
                "id": "pronostico_erlang",
                "nombre": "OUTPUT I: Pronostico (Rac Requerido)",
                "descripcion": (
                    "Calcula el Rac Requerido Disponible usando Erlang C con datos del Cubo de Trafico. "
                    "Pronostica volumen entrante a 30/60/90 dias y calcula agentes necesarios "
                    "por intervalo con pronostico de TMO. Es el OUTPUT I del proceso WFM."
                ),
                "datos_necesarios": [
                    "Cubo de Trafico (resultado de CORTEX) o parametros manuales",
                ],
                "resultado": "OUTPUT I: Rac Requerido Disponible por intervalo (Erlang con pronostico)",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": True,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["cortex", "nexus"],
                "multi_resultado": True,
            },
            {
                "id": "planificacion_proveedor",
                "nombre": "OUTPUT II: Planificacion Proveedor",
                "descripcion": (
                    "Calcula el Rac Planificado Disponible: Erlang con pronostico +10% de volumen, "
                    "pronostico de TMO y Reductores (ausentismo, rotacion, capacitacion). "
                    "Es el dato teorico que el centro deberia cubrir al programar horarios. "
                    "Genera la Malla Proveedor para cargar en Kipu."
                ),
                "datos_necesarios": [
                    "OUTPUT I (Pronostico) o Cubo de Trafico + parametros de reductores",
                ],
                "resultado": "OUTPUT II: Rac Planificado Disponible con +10% y reductores por intervalo",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": True,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["nexus", "cortex"],
                "multi_resultado": True,
            },
            {
                "id": "programacion_turnos",
                "nombre": "OUTPUT III-V: Programacion Turnos",
                "descripcion": (
                    "Genera la programacion de turnos del proveedor. Calcula 3 OUTPUTs: "
                    "III (Rac Programado Logueado = agentes citados en horario), "
                    "IV (Programado Logueado - Break = agentes menos breaks programados), "
                    "V (Rac Programado Disponible = agentes que deben estar disponibles). "
                    "Programa TNPs: Break, Coach, Capacitaciones, etc."
                ),
                "datos_necesarios": [
                    "OUTPUT II (Planificacion) o Malla Proveedor + dotacion real por proveedor",
                ],
                "resultado": "OUTPUTs III/IV/V: Programado Logueado, -Break, Disponible por intervalo",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": True,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["nexus", "cortex"],
                "multi_resultado": True,
            },
            {
                "id": "analisis_gtr",
                "nombre": "Analisis GTR (Real vs Plan)",
                "descripcion": (
                    "Compara datos reales de GTR vs programacion planificada. "
                    "Calcula: Logueado Real vs Programado Logueado, "
                    "Disponible Real vs Requerido Disponible, "
                    "Rac Requerido Disponible Real (Erlang con trafico y TMO real). "
                    "Detecta desviaciones y genera alertas en tiempo real."
                ),
                "datos_necesarios": [
                    "Datos GTR reales (resultado de CORTEX) + Programacion (OUTPUT III-V)",
                ],
                "resultado": "Comparativo real vs plan con desviaciones, alertas y Erlang real por intervalo",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": True,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["nexus", "cortex"],
                "multi_resultado": True,
            },
            {
                "id": "calcular_cop_cor",
                "nombre": "OUTPUT VI: COP y COR",
                "descripcion": (
                    "Calcula Capacidad Operativa Planificada (COP) y Real (COR). "
                    "COP = Erlang aplicado a valores de pronostico de volumen. "
                    "COR = Total Atendidas Real x TMO + Tiempo de Avail. "
                    "Compara COP vs COR para medir eficiencia de la operacion."
                ),
                "datos_necesarios": [
                    "Malla con pronostico (CORTEX) + Datos GTR reales (CORTEX) o resultados previos",
                ],
                "resultado": "OUTPUT VI: COP, COR, diferencia y eficiencia operativa por intervalo",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": True,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["nexus", "cortex"],
                "multi_resultado": True,
            },
            {
                "id": "ingesta_wfm",
                "nombre": "Ingesta Metricas x Antiguedad",
                "descripcion": (
                    "Carga y procesa la base 'Metricas x Antiguedad' con metricas por agente y periodo. "
                    "Reconoce 60+ columnas: PERIODO, PROVEEDOR, PLATAFORMA, AGENTE, ANTIGUEDAD, "
                    "ATENDIDAS, REITERADAS, TRANSFERENCIAS, TMO, LLAMADAS_CORTAS, AVAIL, NO_READY, "
                    "OCUPACION, HOLD, NPS, CALIDAD, SOLUCION, ERROR_ENVIO_A_CAMPO, CUARTILES. "
                    "Valida datos, calcula KPIs agregados y genera un perfil completo."
                ),
                "datos_necesarios": ["Archivo Metricas x Antiguedad (.csv, .xlsx)"],
                "resultado": "Resumen completo con KPIs por dimension, cuartiles y alertas",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls"],
                "acepta_texto": True,
                "acepta_resultado_previo": False,
            },
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
                    "Calculo base de Erlang C para dimensionamiento. "
                    "Calcula agentes necesarios para un nivel de servicio objetivo. "
                    "Considera carga, TMO, shrinkage y NdS target (ej: 80/20)."
                ),
                "datos_necesarios": [
                    "Carga de trabajo y TMO (resultados de NEXUS) o parametros manuales",
                ],
                "resultado": "Staffing requerido con ocupacion y nivel de servicio proyectado",
                "acepta_archivo": True,
                "extensiones": [".csv", ".xlsx", ".xls", ".json"],
                "acepta_texto": True,
                "acepta_resultado_previo": True,
                "agentes_compatibles": ["nexus", "cortex"],
                "multi_resultado": True,
            },
            _SKILL_VISUALIZAR,
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
            _SKILL_VISUALIZAR,
        ],
    },

    # ── 4. LEDGER: Financiero ─────────────────────────────────────────
    "ledger": {
        "nombre": "LEDGER",
        "rol": "Financiero y Facturacion",
        "icono": "currency-dollar",
        "color": "#FFC107",
        "descripcion": (
            "Contador del equipo. Calcula facturacion usando COP/COR de NEXUS, "
            "soportes de Bitacora, bonos por desempeno segun KPIs alcanzados "
            "y penalidades por incumplimiento de SLAs. Paga, Bonifica, Penaliza."
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
            _SKILL_VISUALIZAR,
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
            _SKILL_VISUALIZAR,
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
