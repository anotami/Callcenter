"""
Motor de pipelines predefinidos para ejecucion one-click.
Permite encadenar skills de multiples agentes automaticamente.
"""

import logging
from datetime import datetime

from agent_runner import execute_skill, load_all_results

logger = logging.getLogger("callcenter.pipeline")


# ── Definiciones de Pipelines ────────────────────────────────────────────

PIPELINES = {
    "reporte_360_express": {
        "nombre": "Reporte 360 Express",
        "descripcion": (
            "Carga datos ACD, genera analisis de calidad, capacidad y "
            "produce un Informe Consolidado 360 automaticamente."
        ),
        "icono": ":material/dashboard:",
        "requiere_archivo": True,
        "extensiones": [".csv", ".xlsx", ".xls", ".json"],
        "acepta_texto": True,
        "texto_placeholder": "Contexto adicional: periodo, tarifas, metas...",
        "pasos": [
            {
                "agent_id": "cortex",
                "skill_id": "ingesta_acd",
                "skill_name": "Ingesta de Datos ACD",
                "usa_archivo": True,
                "descripcion": "Cargando y analizando datos ACD",
            },
            {
                "agent_id": "nexus",
                "skill_id": "calcular_carga_trabajo",
                "skill_name": "Calcular Carga de Trabajo",
                "usa_resultado_previo": 0,
                "descripcion": "Calculando carga de trabajo",
            },
            {
                "agent_id": "nexus",
                "skill_id": "calcular_staffing",
                "skill_name": "Calcular Staffing (Erlang C)",
                "usa_resultados_multiples": [0, 1],
                "usa_texto": True,
                "descripcion": "Calculando staffing con Erlang C",
            },
            {
                "agent_id": "atlas",
                "skill_id": "informe_consolidado",
                "skill_name": "Informe Consolidado 360",
                "usa_resultados_multiples": "all",
                "usa_texto": True,
                "descripcion": "Generando informe consolidado 360",
            },
        ],
    },
    "wbr_express": {
        "nombre": "WBR Express (Semanal)",
        "descripcion": (
            "Ingesta de datos, analisis cruzado y generacion del "
            "Weekly Business Review en un solo click."
        ),
        "icono": ":material/calendar_view_week:",
        "requiere_archivo": True,
        "extensiones": [".csv", ".xlsx", ".xls", ".json"],
        "acepta_texto": True,
        "texto_placeholder": "Periodo: ej. Semana 11 Marzo 2026, metas, contexto...",
        "pasos": [
            {
                "agent_id": "cortex",
                "skill_id": "ingesta_acd",
                "skill_name": "Ingesta de Datos ACD",
                "usa_archivo": True,
                "descripcion": "Cargando datos ACD",
            },
            {
                "agent_id": "nexus",
                "skill_id": "calcular_carga_trabajo",
                "skill_name": "Calcular Carga de Trabajo",
                "usa_resultado_previo": 0,
                "descripcion": "Calculando carga de trabajo",
            },
            {
                "agent_id": "atlas",
                "skill_id": "consolidar_wbr",
                "skill_name": "Consolidar WBR (Semanal)",
                "usa_resultados_multiples": "all",
                "usa_texto": True,
                "descripcion": "Generando Weekly Business Review",
            },
        ],
    },
    "mbr_express": {
        "nombre": "MBR Express (Mensual)",
        "descripcion": (
            "Ingesta completa y generacion automatica del Monthly "
            "Business Review consolidando todos los datos."
        ),
        "icono": ":material/calendar_month:",
        "requiere_archivo": True,
        "extensiones": [".csv", ".xlsx", ".xls", ".json"],
        "acepta_texto": True,
        "texto_placeholder": "Periodo: ej. Marzo 2026, metas mensuales, presupuesto...",
        "pasos": [
            {
                "agent_id": "cortex",
                "skill_id": "ingesta_acd",
                "skill_name": "Ingesta de Datos ACD",
                "usa_archivo": True,
                "descripcion": "Cargando datos ACD",
            },
            {
                "agent_id": "nexus",
                "skill_id": "calcular_carga_trabajo",
                "skill_name": "Calcular Carga de Trabajo",
                "usa_resultado_previo": 0,
                "descripcion": "Calculando carga de trabajo",
            },
            {
                "agent_id": "nexus",
                "skill_id": "calcular_staffing",
                "skill_name": "Calcular Staffing (Erlang C)",
                "usa_resultados_multiples": [0, 1],
                "usa_texto": True,
                "descripcion": "Calculando staffing con Erlang C",
            },
            {
                "agent_id": "atlas",
                "skill_id": "consolidar_mbr",
                "skill_name": "Consolidar MBR (Mensual)",
                "usa_resultados_multiples": "all",
                "usa_texto": True,
                "descripcion": "Generando Monthly Business Review",
            },
        ],
    },
    "analisis_calidad_audio": {
        "nombre": "Analisis de Calidad desde Audio",
        "descripcion": (
            "Transcribe audio, genera dialogo con hablantes, evalua "
            "calidad y detecta errores criticos automaticamente."
        ),
        "icono": ":material/mic:",
        "requiere_archivo": True,
        "extensiones": [".mp3", ".wav", ".m4a", ".ogg", ".flac", ".wma"],
        "acepta_texto": False,
        "pasos": [
            {
                "agent_id": "cortex",
                "skill_id": "generar_dialogo",
                "skill_name": "Generar Dialogo con Hablantes",
                "usa_audio": True,
                "descripcion": "Transcribiendo y diarizando audio",
            },
            {
                "agent_id": "sentinel",
                "skill_id": "evaluar_llamada",
                "skill_name": "Evaluar Calidad de Llamada",
                "usa_resultado_previo": 0,
                "descripcion": "Evaluando calidad de la llamada",
            },
            {
                "agent_id": "sentinel",
                "skill_id": "detectar_rac",
                "skill_name": "Detectar Errores Criticos (RAC)",
                "usa_resultados_multiples": [0, 1],
                "descripcion": "Detectando errores criticos",
            },
            {
                "agent_id": "sentinel",
                "skill_id": "generar_reporte_calidad",
                "skill_name": "Generar Reporte de Calidad",
                "usa_resultado_previo": 1,
                "descripcion": "Generando reporte de calidad",
            },
        ],
    },
    "analisis_wfm_completo": {
        "nombre": "Analisis WFM Completo",
        "descripcion": (
            "Ingesta de metricas WFM, calculo de carga, staffing "
            "y reporte por modulos automaticamente."
        ),
        "icono": ":material/groups:",
        "requiere_archivo": True,
        "extensiones": [".csv", ".xlsx", ".xls"],
        "acepta_texto": True,
        "texto_placeholder": "Contexto: metas de NdS, shrinkage, parametros...",
        "pasos": [
            {
                "agent_id": "nexus",
                "skill_id": "ingesta_wfm",
                "skill_name": "Ingesta Metricas x Antiguedad",
                "usa_archivo": True,
                "usa_texto": True,
                "descripcion": "Cargando metricas WFM",
            },
            {
                "agent_id": "atlas",
                "skill_id": "informe_por_modulo",
                "skill_name": "Informe por Modulos",
                "usa_resultados_multiples": "all",
                "usa_texto": True,
                "descripcion": "Generando informe por modulos",
            },
        ],
    },
    "facturacion_express": {
        "nombre": "Facturacion Express",
        "descripcion": (
            "Carga datos, calcula facturacion, bonos y penalidades "
            "de forma automatica."
        ),
        "icono": ":material/receipt_long:",
        "requiere_archivo": True,
        "extensiones": [".csv", ".xlsx", ".xls", ".json"],
        "acepta_texto": True,
        "texto_placeholder": "Tarifas, metas de bonos, SLAs contractuales...",
        "pasos": [
            {
                "agent_id": "cortex",
                "skill_id": "ingesta_acd",
                "skill_name": "Ingesta de Datos ACD",
                "usa_archivo": True,
                "descripcion": "Cargando datos de volumetria",
            },
            {
                "agent_id": "ledger",
                "skill_id": "calcular_facturacion",
                "skill_name": "Calcular Facturacion",
                "usa_resultados_multiples": [0],
                "usa_texto": True,
                "descripcion": "Calculando facturacion",
            },
            {
                "agent_id": "ledger",
                "skill_id": "calcular_bonos",
                "skill_name": "Calcular Bonos por Desempeno",
                "usa_resultados_multiples": [0],
                "usa_texto": True,
                "descripcion": "Calculando bonos",
            },
            {
                "agent_id": "ledger",
                "skill_id": "calcular_penalidades",
                "skill_name": "Calcular Penalidades",
                "usa_resultados_multiples": [0],
                "usa_texto": True,
                "descripcion": "Calculando penalidades",
            },
        ],
    },
}


AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".wma"}


def execute_pipeline(pipeline_id: str,
                     file_bytes: bytes | None = None,
                     filename: str = "",
                     texto: str = "",
                     status_callback=None) -> dict:
    """Ejecuta un pipeline completo paso a paso.

    Args:
        pipeline_id: ID del pipeline a ejecutar
        file_bytes: Bytes del archivo subido
        filename: Nombre del archivo
        texto: Texto/contexto adicional del usuario
        status_callback: Funcion(step_index, total_steps, description, status)

    Returns:
        dict con resultados de cada paso y el resultado final
    """
    pipeline = PIPELINES.get(pipeline_id)
    if not pipeline:
        return {"error": f"Pipeline '{pipeline_id}' no encontrado"}

    pasos = pipeline["pasos"]
    resultados = []
    errors = []

    from pathlib import Path
    ext = Path(filename).suffix.lower() if filename else ""
    is_audio = ext in AUDIO_EXTENSIONS

    for i, paso in enumerate(pasos):
        step_desc = paso.get("descripcion", paso["skill_name"])

        if status_callback:
            status_callback(i, len(pasos), f"Paso {i+1}/{len(pasos)}: {step_desc}", "running")

        # Preparar inputs para este paso
        step_file_bytes = None
        step_audio_bytes = None
        step_filename = ""
        step_texto = ""
        resultado_previo = None
        resultados_multiples = None

        # Archivo directo
        if paso.get("usa_archivo") and file_bytes:
            step_file_bytes = file_bytes
            step_filename = filename

        # Audio directo
        if paso.get("usa_audio") and file_bytes and is_audio:
            step_audio_bytes = file_bytes
            step_filename = filename

        # Texto del usuario
        if paso.get("usa_texto") and texto:
            step_texto = texto

        # Resultado previo (single)
        if "usa_resultado_previo" in paso:
            idx = paso["usa_resultado_previo"]
            if idx < len(resultados):
                resultado_previo = resultados[idx].get("resultado")

        # Resultados multiples
        if "usa_resultados_multiples" in paso:
            ref = paso["usa_resultados_multiples"]
            if ref == "all":
                resultados_multiples = resultados
            elif isinstance(ref, list):
                resultados_multiples = [
                    resultados[j] for j in ref if j < len(resultados)
                ]

        try:
            result = execute_skill(
                agent_id=paso["agent_id"],
                skill_id=paso["skill_id"],
                skill_name=paso["skill_name"],
                audio_bytes=step_audio_bytes,
                file_bytes=step_file_bytes,
                filename=step_filename,
                texto=step_texto,
                resultado_previo=resultado_previo,
                resultados_multiples=resultados_multiples,
            )

            resultados.append(result)

            # Check for errors in result
            res_data = result.get("resultado", {})
            if isinstance(res_data, dict) and "error" in res_data:
                errors.append({
                    "paso": i + 1,
                    "skill": paso["skill_name"],
                    "error": res_data["error"],
                })
                if status_callback:
                    status_callback(i, len(pasos),
                                    f"Error en paso {i+1}: {res_data['error'][:60]}",
                                    "error")
            else:
                if status_callback:
                    status_callback(i, len(pasos),
                                    f"Paso {i+1}/{len(pasos)}: {step_desc} - Completado",
                                    "complete")

        except Exception as e:
            logger.error("Pipeline %s, paso %d error: %s", pipeline_id, i, e)
            errors.append({
                "paso": i + 1,
                "skill": paso["skill_name"],
                "error": str(e),
            })
            if status_callback:
                status_callback(i, len(pasos),
                                f"Error en paso {i+1}: {str(e)[:60]}", "error")
            # Continue with remaining steps if possible
            resultados.append({"error": str(e)})

    return {
        "pipeline_id": pipeline_id,
        "pipeline_nombre": pipeline["nombre"],
        "total_pasos": len(pasos),
        "pasos_completados": len(pasos) - len(errors),
        "errores": errors,
        "resultados": resultados,
        "resultado_final": resultados[-1] if resultados else None,
        "timestamp": datetime.now().isoformat(),
    }


def get_all_pipelines() -> dict:
    """Retorna todos los pipelines disponibles."""
    return PIPELINES
