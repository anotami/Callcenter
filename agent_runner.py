"""
Motor de ejecucion de habilidades de agentes.
Ejecuta skills, guarda resultados con versionado, y permite a Atlas consumirlos.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from config import BASE_DIR

logger = logging.getLogger("callcenter.agent_runner")

# Directorio donde se guardan los resultados versionados
RESULTS_DIR = BASE_DIR / "agent_results"
RESULTS_DIR.mkdir(exist_ok=True)


def _result_path(agent_id: str, skill_id: str, version: int) -> Path:
    """Genera la ruta del archivo de resultado versionado."""
    today = datetime.now().strftime("%Y-%m-%d")
    agent_dir = RESULTS_DIR / agent_id
    agent_dir.mkdir(exist_ok=True)
    return agent_dir / f"{skill_id}_{today}_v{version}.json"


def _next_version(agent_id: str, skill_id: str) -> int:
    """Encuentra la siguiente version disponible para hoy."""
    today = datetime.now().strftime("%Y-%m-%d")
    prefix = f"{skill_id}_{today}_v"
    agent_dir = RESULTS_DIR / agent_id
    if not agent_dir.exists():
        return 1
    existing = [
        f.stem for f in agent_dir.iterdir()
        if f.stem.startswith(prefix.rstrip("v"))  # match without 'v' for pattern
    ]
    max_v = 0
    for name in existing:
        try:
            v = int(name.split("_v")[-1])
            max_v = max(max_v, v)
        except (ValueError, IndexError):
            pass
    return max_v + 1


def save_result(agent_id: str, skill_id: str, skill_name: str,
                result_data: dict | str, input_summary: str = "") -> dict:
    """
    Guarda el resultado de una habilidad con versionado.
    Retorna metadata del resultado guardado.
    """
    version = _next_version(agent_id, skill_id)
    now = datetime.now()

    record = {
        "agent_id": agent_id,
        "agent_name": agent_id.capitalize(),
        "skill_id": skill_id,
        "skill_name": skill_name,
        "version": version,
        "fecha": now.strftime("%Y-%m-%d"),
        "hora": now.strftime("%H:%M:%S"),
        "timestamp": now.isoformat(),
        "input_summary": input_summary,
        "resultado": result_data,
    }

    path = _result_path(agent_id, skill_id, version)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Resultado guardado: %s (v%d)", path.name, version)
    return record


def load_all_results(agent_id: str | None = None) -> list[dict]:
    """
    Carga todos los resultados guardados.
    Si agent_id se especifica, filtra solo ese agente.
    """
    results = []
    if agent_id:
        agent_dirs = [RESULTS_DIR / agent_id]
    else:
        agent_dirs = [d for d in RESULTS_DIR.iterdir() if d.is_dir()]

    for agent_dir in agent_dirs:
        if not agent_dir.exists():
            continue
        for f in sorted(agent_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                data["_file"] = str(f)
                results.append(data)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Error leyendo %s: %s", f, e)
    return results


def load_result_by_file(filepath: str) -> dict | None:
    """Carga un resultado especifico por su ruta."""
    try:
        return json.loads(Path(filepath).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return None


# ── Ejecutores de habilidades ──────────────────────────────────────────


def _temp_save(audio_bytes: bytes, filename: str) -> str:
    """Guarda bytes de audio en archivo temporal y retorna la ruta."""
    import tempfile
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, filename)
    with open(temp_path, "wb") as f:
        f.write(audio_bytes)
    return temp_path


def run_transcribir_audio(audio_bytes: bytes, filename: str) -> dict:
    """Ejecuta la transcripcion de un audio."""
    from transcriber import load_whisper_model, transcribe
    temp_path = _temp_save(audio_bytes, filename)

    model = load_whisper_model()
    segments = transcribe(model, temp_path)

    if not segments:
        return {"error": "No se pudo transcribir el audio"}

    full_text = " ".join(s["text"] for s in segments)
    return {
        "segmentos": segments,
        "texto_completo": full_text,
        "total_segmentos": len(segments),
        "duracion_estimada": segments[-1]["end"] if segments else 0,
        "palabras": len(full_text.split()),
    }


def run_detectar_idioma(audio_bytes: bytes, filename: str) -> dict:
    """Detecta el idioma de un audio."""
    from faster_whisper import WhisperModel
    from config import WHISPER_MODEL, WHISPER_DEVICE

    temp_path = _temp_save(audio_bytes, filename)

    compute_type = "float16" if WHISPER_DEVICE == "cuda" else "int8"
    model = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=compute_type)
    _, info = model.transcribe(temp_path, beam_size=1)

    return {
        "idioma": info.language,
        "probabilidad": round(info.language_probability * 100, 1),
        "descripcion": f"Idioma detectado: {info.language.upper()} con {info.language_probability*100:.1f}% de confianza",
    }


def run_identificar_hablantes(audio_bytes: bytes, filename: str) -> dict:
    """Ejecuta diarizacion para identificar hablantes."""
    from diarizer import load_diarization_model, diarize

    temp_path = _temp_save(audio_bytes, filename)

    pipeline = load_diarization_model()
    segments = diarize(pipeline, temp_path)

    if not segments:
        return {"error": "No se pudo diarizar el audio"}

    speakers = list(set(s["speaker"] for s in segments))
    return {
        "segmentos": segments,
        "num_hablantes": len(speakers),
        "hablantes": speakers,
        "total_segmentos": len(segments),
    }


def run_generar_dialogo(audio_bytes: bytes, filename: str,
                        transcripcion_previa: dict | None = None) -> dict:
    """Genera dialogo completo combinando transcripcion + diarizacion."""
    from transcriber import load_whisper_model, transcribe
    from diarizer import (
        load_diarization_model, diarize,
        merge_transcription_diarization, format_dialogue,
    )

    temp_path = _temp_save(audio_bytes, filename)

    # Usar transcripcion previa si existe, sino transcribir
    if transcripcion_previa and "segmentos" in transcripcion_previa:
        transcription = transcripcion_previa["segmentos"]
    else:
        model = load_whisper_model()
        transcription = transcribe(model, temp_path)

    if not transcription:
        return {"error": "No se pudo transcribir el audio"}

    pipeline = load_diarization_model()
    diarization = diarize(pipeline, temp_path)
    merged = merge_transcription_diarization(transcription, diarization)
    dialogue = format_dialogue(merged)

    speakers = set(s["speaker"] for s in merged)
    return {
        "dialogo": dialogue,
        "segmentos": merged,
        "num_hablantes": len(speakers),
        "total_segmentos": len(merged),
    }


def run_evaluar_calidad(texto: str, resultado_previo: dict | None = None) -> dict:
    """Evalua calidad de atencion usando LLM."""
    from analyzer import create_llm_client, analyze_call

    # Determinar el texto a evaluar
    dialogue = texto
    if resultado_previo:
        if "dialogo" in resultado_previo:
            dialogue = resultado_previo["dialogo"]
        elif "texto_completo" in resultado_previo:
            dialogue = resultado_previo["texto_completo"]

    if not dialogue or len(dialogue.strip()) < 20:
        return {"error": "Texto demasiado corto para evaluar"}

    client = create_llm_client()
    evaluation = analyze_call(client, dialogue)
    return evaluation


def run_generar_reporte(texto: str, resultado_previo: dict | None = None) -> dict:
    """Genera reporte formateado desde una evaluacion."""
    from analyzer import format_evaluation_report

    evaluation = resultado_previo if resultado_previo else {}

    # Si recibimos texto JSON, intentar parsearlo
    if texto and not resultado_previo:
        try:
            evaluation = json.loads(texto)
        except json.JSONDecodeError:
            return {"error": "El texto no es un JSON de evaluacion valido"}

    if "evaluacion" not in evaluation and "resultado" in evaluation:
        evaluation = evaluation["resultado"]

    report = format_evaluation_report(evaluation)
    return {"reporte": report, "evaluacion_fuente": evaluation}


def run_analisis_cruzado(resultados: list[dict]) -> dict:
    """Analisis cruzado de multiples evaluaciones."""
    from analyzer import create_llm_client
    from config import LLM_MODEL

    evaluaciones = []
    for r in resultados:
        data = r.get("resultado", r)
        if isinstance(data, dict) and "evaluacion" in data:
            evaluaciones.append(data)

    if len(evaluaciones) < 2:
        return {"error": "Se necesitan al menos 2 evaluaciones para analisis cruzado"}

    resumen_inputs = []
    for i, ev in enumerate(evaluaciones, 1):
        puntaje = ev.get("puntaje_total", "N/A")
        resumen = ev.get("resumen_general", "Sin resumen")
        resumen_inputs.append(f"Evaluacion {i}: Puntaje={puntaje}/100. {resumen}")

    prompt = f"""Analiza estas {len(evaluaciones)} evaluaciones de calidad de call center y genera un analisis cruzado:

{chr(10).join(resumen_inputs)}

Responde en JSON con:
- "patrones_comunes": lista de patrones que se repiten
- "mejores_areas": areas donde el desempeno es consistentemente bueno
- "areas_mejora": areas con oportunidad de mejora
- "outliers": evaluaciones que se destacan positiva o negativamente
- "recomendaciones": lista de acciones concretas
- "puntaje_promedio": promedio numerico
"""
    client = create_llm_client()
    from analyzer import _extract_json
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "Eres un analista de calidad de call center. Responde en JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=2000,
        )
        raw = response.choices[0].message.content
        result = _extract_json(raw)
        return result if result else {"raw_response": raw}
    except Exception as e:
        return {"error": f"Error en analisis cruzado: {e}"}


def run_detectar_tendencias(resultados: list[dict]) -> dict:
    """Detecta tendencias en evaluaciones a lo largo del tiempo."""
    puntos = []
    for r in resultados:
        data = r.get("resultado", r)
        if isinstance(data, dict) and "puntaje_total" in data:
            puntos.append({
                "fecha": r.get("fecha", "desconocida"),
                "puntaje": data["puntaje_total"],
                "resumen": data.get("resumen_general", ""),
            })

    if len(puntos) < 2:
        return {"error": "Se necesitan al menos 2 evaluaciones con puntaje para detectar tendencias"}

    puntos.sort(key=lambda x: x["fecha"])
    puntajes = [p["puntaje"] for p in puntos if isinstance(p["puntaje"], (int, float))]

    tendencia = "estable"
    if len(puntajes) >= 2:
        diff = puntajes[-1] - puntajes[0]
        if diff > 5:
            tendencia = "mejorando"
        elif diff < -5:
            tendencia = "deteriorando"

    return {
        "tendencia": tendencia,
        "puntos": puntos,
        "puntaje_minimo": min(puntajes) if puntajes else None,
        "puntaje_maximo": max(puntajes) if puntajes else None,
        "puntaje_promedio": round(sum(puntajes) / len(puntajes), 1) if puntajes else None,
        "total_evaluaciones": len(puntos),
    }


def run_resumen_equipo(resultados: list[dict]) -> dict:
    """Genera resumen de actividad de todos los agentes."""
    from collections import Counter

    agentes_actividad = Counter()
    skills_actividad = Counter()
    fechas = set()

    for r in resultados:
        agentes_actividad[r.get("agent_name", "Desconocido")] += 1
        skills_actividad[r.get("skill_name", "Desconocida")] += 1
        fechas.add(r.get("fecha", ""))

    return {
        "total_tareas": len(resultados),
        "agentes_activos": dict(agentes_actividad),
        "habilidades_usadas": dict(skills_actividad),
        "dias_activos": len(fechas),
        "fechas": sorted(fechas),
        "agente_mas_activo": agentes_actividad.most_common(1)[0] if agentes_actividad else None,
        "skill_mas_usada": skills_actividad.most_common(1)[0] if skills_actividad else None,
    }


# ── Dispatcher principal ───────────────────────────────────────────────

SKILL_RUNNERS = {
    "transcribir_audio": run_transcribir_audio,
    "detectar_idioma": run_detectar_idioma,
    "identificar_hablantes": run_identificar_hablantes,
    "generar_dialogo": run_generar_dialogo,
    "evaluar_calidad": run_evaluar_calidad,
    "generar_reporte": run_generar_reporte,
    "analisis_cruzado": run_analisis_cruzado,
    "detectar_tendencias": run_detectar_tendencias,
    "resumen_equipo": run_resumen_equipo,
}


def execute_skill(agent_id: str, skill_id: str, skill_name: str,
                  audio_bytes: bytes | None = None,
                  filename: str = "",
                  texto: str = "",
                  resultado_previo: dict | None = None,
                  resultados_multiples: list[dict] | None = None) -> dict:
    """
    Ejecuta una habilidad y guarda el resultado con versionado.
    Retorna el record completo guardado.
    """
    runner = SKILL_RUNNERS.get(skill_id)
    if not runner:
        return {"error": f"Habilidad '{skill_id}' no implementada"}

    # Determinar argumentos segun el tipo de skill
    try:
        if skill_id in ("transcribir_audio", "detectar_idioma", "identificar_hablantes"):
            if not audio_bytes:
                return {"error": "Se requiere un archivo de audio"}
            result = runner(audio_bytes, filename)

        elif skill_id == "generar_dialogo":
            if not audio_bytes:
                return {"error": "Se requiere un archivo de audio"}
            result = runner(audio_bytes, filename, resultado_previo)

        elif skill_id in ("evaluar_calidad", "generar_reporte"):
            result = runner(texto, resultado_previo)

        elif skill_id in ("analisis_cruzado", "detectar_tendencias", "resumen_equipo"):
            items = resultados_multiples or []
            result = runner(items)

        else:
            return {"error": f"Skill '{skill_id}' sin dispatcher configurado"}

    except Exception as e:
        logger.error("Error ejecutando %s/%s: %s", agent_id, skill_id, e)
        result = {"error": str(e)}

    # Guardar resultado versionado
    input_summary = filename if filename else (texto[:100] + "..." if len(texto) > 100 else texto)
    record = save_result(agent_id, skill_id, skill_name, result, input_summary)
    return record
