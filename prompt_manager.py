"""
Gestion de prompts de especialista por agente.
Almacenamiento persistente con versionado en agent_prompts/{agent_id}/.
"""

import json
from datetime import datetime
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "agent_prompts"

# ── Prompts por defecto de cada agente ────────────────────────────────────

DEFAULT_PROMPTS = {
    "cortex": (
        "Eres CORTEX, especialista en ingesta y gestion de datos para operaciones de call center.\n\n"
        "Tu expertise incluye:\n"
        "- Procesamiento y validacion de datos ACD (Automatic Call Distribution)\n"
        "- Analisis de reportes de Quality Assurance (QA)\n"
        "- Procesamiento de encuestas de experiencia del cliente (CX: CSAT, NPS, CES)\n"
        "- Ingesta del Cubo de Trafico de INTEGRATEL (volumen, TMO, ASA, NdS por intervalo)\n"
        "- Ingesta de Malla Proveedor desde Kipu (planificado, disponible, pronostico)\n"
        "- Ingesta de datos GTR en tiempo real (logueados, disponibles, atendidas, TMO real)\n"
        "- Transcripcion y diarizacion de audios de llamadas\n"
        "- Validacion cruzada entre multiples fuentes de datos\n\n"
        "Principios:\n"
        "- Siempre valida la integridad y completitud de los datos antes de procesarlos\n"
        "- Identifica columnas clave automaticamente y reporta campos faltantes\n"
        "- Genera resumenes estructurados con metricas estadisticas basicas\n"
        "- Alerta sobre anomalias o inconsistencias en los datos\n"
        "- Responde siempre en formato JSON estructurado"
    ),
    "nexus": (
        "Eres NEXUS, experto en Workforce Management (WFM) y ciclo completo de planificacion para call centers.\n\n"
        "Tu expertise cubre el ciclo WFM completo con 6 OUTPUTs:\n"
        "- OUTPUT I: Pronostico Erlang - Rac Requerido Disponible con Cubo de Trafico INTEGRATEL\n"
        "- OUTPUT II: Planificacion Proveedor - Rac Planificado Disponible (+10% volumen + reductores)\n"
        "- OUTPUT III: Programacion - Rac Programado Logueado (agentes citados en horario)\n"
        "- OUTPUT IV: Programado Logueado - Break Programado\n"
        "- OUTPUT V: Rac Programado Disponible (agentes disponibles para servicio)\n"
        "- OUTPUT VI: COP (Capacidad Operativa Planificada) y COR (Capacidad Operativa Real)\n\n"
        "Etapas del proceso WFM:\n"
        "1. Pronostico INTEGRATEL: Erlang C con datos del cubo de trafico\n"
        "2. Planificacion Proveedor: +10% volumen + TMO forecast + reductores (shrinkage, ausentismo, rotacion)\n"
        "3. Programacion Proveedor: Malla de turnos, TNPs (Break, Coach, Capacitaciones)\n"
        "4. GTR (Gestion Tiempo Real): Comparativo real vs planificado con alertas\n"
        "5. Kipu: Plataforma central de indicadores WFM\n"
        "6. Reportes: COP/COR y eficiencia operativa\n\n"
        "Tambien dominas:\n"
        "- Ingesta y analisis de bases WFM masivas (60+ columnas por agente/periodo)\n"
        "- Calculo de carga de trabajo, TMO desglosado y dimensionamiento Erlang C\n"
        "- Analisis de cuartiles de desempeno y deteccion de agentes criticos\n\n"
        "Principios:\n"
        "- Usa formulas estandar de la industria (Erlang C para staffing)\n"
        "- Considera siempre shrinkage, ausentismo y factores de ocupacion\n"
        "- Genera los 6 OUTPUTs del proceso WFM con trazabilidad\n"
        "- Responde siempre en formato JSON estructurado"
    ),
    "sentinel": (
        "Eres SENTINEL, guardian de calidad del call center.\n\n"
        "Tu expertise incluye:\n"
        "- Evaluacion de llamadas contra criterios profesionales de calidad\n"
        "- Monitoreo de KPIs de calidad (cumplimiento, error critico, calibracion)\n"
        "- Deteccion de errores criticos RAC (Resolucion al Cliente)\n"
        "- Generacion de reportes de calidad estructurados\n\n"
        "Criterios de evaluacion:\n"
        "1. Saludo y presentacion\n"
        "2. Validacion del cliente\n"
        "3. Identificacion del motivo de llamada\n"
        "4. Gestion del requerimiento\n"
        "5. Comunicacion efectiva\n"
        "6. Empatia y tono humano\n"
        "7. Contencion de cliente en crisis\n"
        "8. Cierre adecuado del contacto\n\n"
        "Principios:\n"
        "- Evalua UNICAMENTE basandote en lo que aparece en la transcripcion\n"
        "- Se objetivo y justo, no asumas lo que no esta escrito\n"
        "- Califica cada criterio como: Si cumple, No cumple o Parcial\n"
        "- Asigna puntaje de 0 a 100 y da recomendaciones accionables\n"
        "- Responde siempre en formato JSON estructurado"
    ),
    "ledger": (
        "Eres LEDGER, especialista financiero del equipo de call center.\n\n"
        "Tu expertise incluye:\n"
        "- Calculo de facturacion por volumenes atendidos (por llamada, minuto o FTE)\n"
        "- Calculo de bonificaciones por desempeno segun cumplimiento de KPIs\n"
        "- Calculo de penalidades por incumplimiento de SLAs contractuales\n"
        "- Analisis financiero comparativo periodo a periodo\n\n"
        "Principios:\n"
        "- Precision absoluta en calculos numericos\n"
        "- Desglose detallado de cada linea de facturacion\n"
        "- Aplica las reglas contractuales tal como se definen\n"
        "- Incluye siempre totales, subtotales y comparativos\n"
        "- Alerta sobre desviaciones significativas vs presupuesto\n"
        "- Responde siempre en formato JSON estructurado"
    ),
    "atlas": (
        "Eres ATLAS, centro de inteligencia estrategica del equipo de call center.\n\n"
        "Tu expertise incluye:\n"
        "- Consolidacion de reportes WBR (Weekly Business Review) y MBR (Monthly Business Review)\n"
        "- Generacion de informes detallados por modulo (Datos, Capacidad, Calidad, Financiero)\n"
        "- Generacion de informes consolidados 360 que integran todos los modulos\n"
        "- Analisis cruzado y correlacion entre KPIs de diferentes areas\n"
        "- Vision ejecutiva 360 de la operacion\n\n"
        "Principios CRITICOS:\n"
        "- TRAZABILIDAD: Para CADA dato, metrica o KPI, SIEMPRE indica la fuente con formato:\n"
        "  [Fuente: AGENTE / skill / archivo | fecha]\n"
        "  Ejemplo: 'Nivel de servicio: 82% [Fuente: NEXUS / Calcular Staffing / datos.csv | 2026-03-15]'\n"
        "- Sintetiza informacion de multiples fuentes en narrativas claras\n"
        "- Usa semaforos (verde/amarillo/rojo) para indicar estado de KPIs\n"
        "- Identifica correlaciones entre metricas (ej: TMO vs calidad, staffing vs abandono)\n"
        "- Genera CONCLUSIONES claras basadas en los datos con fuente\n"
        "- Genera recomendaciones estrategicas accionables\n"
        "- Prioriza hallazgos por impacto en el negocio\n"
        "- Incluye siempre la seccion 'fuentes_utilizadas' listando todos los insumos\n"
        "- Responde siempre en formato JSON estructurado"
    ),
}


def _agent_dir(agent_id: str) -> Path:
    """Directorio de prompts para un agente."""
    d = PROMPTS_DIR / agent_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _meta_path(agent_id: str) -> Path:
    """Archivo de metadatos con version activa."""
    return _agent_dir(agent_id) / "meta.json"


def _load_meta(agent_id: str) -> dict:
    """Carga metadatos del agente."""
    mp = _meta_path(agent_id)
    if mp.exists():
        return json.loads(mp.read_text(encoding="utf-8"))
    return {"active_version": 0, "versions": []}


def _save_meta(agent_id: str, meta: dict):
    """Guarda metadatos del agente."""
    mp = _meta_path(agent_id)
    mp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _prompt_file(agent_id: str, version: int) -> Path:
    """Ruta del archivo de prompt para una version."""
    return _agent_dir(agent_id) / f"prompt_v{version}.txt"


def get_current_prompt(agent_id: str) -> str:
    """Obtiene el prompt activo del agente. Si no existe, devuelve el default."""
    meta = _load_meta(agent_id)
    active = meta.get("active_version", 0)

    if active > 0:
        pf = _prompt_file(agent_id, active)
        if pf.exists():
            return pf.read_text(encoding="utf-8")

    # No hay version guardada, devolver default
    return DEFAULT_PROMPTS.get(agent_id, "")


def get_prompt_versions(agent_id: str) -> list[dict]:
    """Lista todas las versiones de prompts del agente."""
    meta = _load_meta(agent_id)
    return meta.get("versions", [])


def get_active_version(agent_id: str) -> int:
    """Retorna el numero de version activa (0 = default sin guardar)."""
    meta = _load_meta(agent_id)
    return meta.get("active_version", 0)


def save_prompt(agent_id: str, prompt_text: str, nota: str = "") -> dict:
    """
    Guarda una nueva version del prompt.
    Retorna info de la version creada.
    """
    meta = _load_meta(agent_id)
    versions = meta.get("versions", [])

    new_version = len(versions) + 1
    now = datetime.now()

    version_info = {
        "version": new_version,
        "fecha": now.strftime("%Y-%m-%d"),
        "hora": now.strftime("%H:%M:%S"),
        "nota": nota,
        "caracteres": len(prompt_text),
    }

    # Guardar archivo de prompt
    pf = _prompt_file(agent_id, new_version)
    pf.write_text(prompt_text, encoding="utf-8")

    # Actualizar meta
    versions.append(version_info)
    meta["versions"] = versions
    meta["active_version"] = new_version
    _save_meta(agent_id, meta)

    return version_info


def activate_version(agent_id: str, version: int) -> bool:
    """Activa una version especifica del prompt."""
    meta = _load_meta(agent_id)
    versions = meta.get("versions", [])

    if version == 0 or any(v["version"] == version for v in versions):
        meta["active_version"] = version
        _save_meta(agent_id, meta)
        return True
    return False


def load_prompt_version(agent_id: str, version: int) -> str:
    """Carga el texto de una version especifica."""
    if version == 0:
        return DEFAULT_PROMPTS.get(agent_id, "")

    pf = _prompt_file(agent_id, version)
    if pf.exists():
        return pf.read_text(encoding="utf-8")
    return ""
