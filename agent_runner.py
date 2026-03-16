"""
Motor de ejecucion de habilidades de agentes.
Ejecuta skills, guarda resultados con versionado, y permite a ATLAS consumirlos.
"""

import json
import logging
import os
from datetime import datetime, date
from pathlib import Path

import numpy as np
import pandas as pd


class _SafeEncoder(json.JSONEncoder):
    """Encoder que convierte tipos numpy/pandas a tipos nativos de Python."""

    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, pd.Timedelta):
            return str(obj)
        if pd.isna(obj):
            return None
        return super().default(obj)

from config import BASE_DIR

logger = logging.getLogger("callcenter.agent_runner")

# Contenedor de progreso activo (se usa desde _llm_analyze y execute_skill)
_active_status_container = None
_active_agent_id = None

# Directorio donde se guardan los resultados versionados
RESULTS_DIR = BASE_DIR / "agent_results"
RESULTS_DIR.mkdir(exist_ok=True)


# ── Utilidades de versionado ───────────────────────────────────────────


def _result_path(agent_id: str, skill_id: str, version: int) -> Path:
    today = datetime.now().strftime("%Y-%m-%d")
    agent_dir = RESULTS_DIR / agent_id
    agent_dir.mkdir(exist_ok=True)
    return agent_dir / f"{skill_id}_{today}_v{version}.json"


def _next_version(agent_id: str, skill_id: str) -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    prefix = f"{skill_id}_{today}_v"
    agent_dir = RESULTS_DIR / agent_id
    if not agent_dir.exists():
        return 1
    max_v = 0
    for f in agent_dir.iterdir():
        if f.stem.startswith(prefix.rstrip("v")):
            try:
                v = int(f.stem.split("_v")[-1])
                max_v = max(max_v, v)
            except (ValueError, IndexError):
                pass
    return max_v + 1


def save_result(agent_id: str, skill_id: str, skill_name: str,
                result_data, input_summary: str = "",
                prompt_version: int | None = None) -> dict:
    version = _next_version(agent_id, skill_id)
    now = datetime.now()
    record = {
        "agent_id": agent_id,
        "agent_name": agent_id.upper(),
        "skill_id": skill_id,
        "skill_name": skill_name,
        "version": version,
        "fecha": now.strftime("%Y-%m-%d"),
        "hora": now.strftime("%H:%M:%S"),
        "timestamp": now.isoformat(),
        "input_summary": input_summary,
        "prompt_version": prompt_version,
        "resultado": result_data,
    }
    path = _result_path(agent_id, skill_id, version)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False, cls=_SafeEncoder), encoding="utf-8")
    logger.info("Resultado guardado: %s (v%d)", path.name, version)
    return record


def load_all_results(agent_id: str | None = None) -> list[dict]:
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
    try:
        return json.loads(Path(filepath).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return None


# ── Utilidades compartidas ─────────────────────────────────────────────


def _temp_save(audio_bytes: bytes, filename: str) -> str:
    import tempfile
    temp_path = os.path.join(tempfile.gettempdir(), filename)
    with open(temp_path, "wb") as f:
        f.write(audio_bytes)
    return temp_path


def _load_dataframe(file_bytes: bytes, filename: str):
    """Carga un archivo en un DataFrame de pandas."""
    import pandas as pd
    import io

    ext = os.path.splitext(filename)[1].lower()
    if ext == ".csv":
        return pd.read_csv(io.BytesIO(file_bytes))
    elif ext in (".xlsx", ".xls"):
        return pd.read_excel(io.BytesIO(file_bytes))
    elif ext == ".json":
        return pd.read_json(io.BytesIO(file_bytes))
    else:
        raise ValueError(f"Formato no soportado: {ext}")


def _df_summary(df, nombre_fuente: str = "datos") -> dict:
    """Genera resumen estadistico de un DataFrame."""
    summary = {
        "fuente": nombre_fuente,
        "filas": len(df),
        "columnas": list(df.columns),
        "tipos": {col: str(dtype) for col, dtype in df.dtypes.items()},
    }
    # Estadisticas para columnas numericas
    num_cols = df.select_dtypes(include=["number"]).columns.tolist()
    if num_cols:
        stats = {}
        for col in num_cols:
            stats[col] = {
                "min": float(df[col].min()) if not df[col].isna().all() else None,
                "max": float(df[col].max()) if not df[col].isna().all() else None,
                "promedio": round(float(df[col].mean()), 2) if not df[col].isna().all() else None,
                "total": round(float(df[col].sum()), 2) if not df[col].isna().all() else None,
            }
        summary["estadisticas"] = stats

    # Muestra de datos
    summary["muestra"] = df.head(5).to_dict(orient="records")

    # Datos faltantes
    nulos = df.isnull().sum()
    if nulos.any():
        summary["datos_faltantes"] = {col: int(n) for col, n in nulos.items() if n > 0}

    return summary


def _llm_analyze(prompt: str, system: str = "") -> dict:
    """Envia un prompt al LLM con fallback entre modelos y retorna JSON parseado."""
    global _active_status_container, _active_agent_id
    from analyzer import call_llm, _extract_json
    from prompt_manager import get_current_prompt

    if not system:
        # Usar prompt de especialista del agente si esta disponible
        agent_prompt = ""
        if _active_agent_id:
            agent_prompt = get_current_prompt(_active_agent_id)
        if agent_prompt:
            system = agent_prompt + "\n\nResponde SIEMPRE en formato JSON estructurado."
        else:
            system = "Eres un analista experto de operaciones de call center. Responde SIEMPRE en JSON."

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    try:
        raw, model_used = call_llm(
            messages=messages,
            temperature=0.1,
            max_tokens=3000,
            status_container=_active_status_container,
        )
    except RuntimeError as e:
        return {"error": str(e)}

    result = _extract_json(raw)
    if result:
        result["_modelo_usado"] = model_used
        return result
    return {"raw_response": raw}


# ══════════════════════════════════════════════════════════════════════
#  MODELOS - Deteccion y prueba de modelos LLM
# ══════════════════════════════════════════════════════════════════════


def run_listar_modelos() -> dict:
    """Conecta al servidor LLM y lista los modelos disponibles."""
    from openai import OpenAI
    import config as _cfg

    try:
        client = OpenAI(base_url=_cfg.LLM_BASE_URL, api_key=_cfg.LLM_API_KEY)
        models_response = client.models.list()
        modelos = [m.id for m in models_response.data]
        return {
            "servidor": _cfg.LLM_BASE_URL,
            "conectado": True,
            "modelos": modelos,
            "total": len(modelos),
        }
    except Exception as e:
        return {
            "servidor": _cfg.LLM_BASE_URL,
            "conectado": False,
            "error": str(e),
            "modelos": [],
            "total": 0,
        }


def run_probar_modelo(modelo: str, prompt: str = "") -> dict:
    """Prueba un modelo especifico enviandole un mensaje simple."""
    from openai import OpenAI
    import config as _cfg
    import time

    prompt = prompt or "Di 'Modelo listo' y tu nombre de modelo."
    client = OpenAI(base_url=_cfg.LLM_BASE_URL, api_key=_cfg.LLM_API_KEY)
    start = time.time()
    try:
        response = client.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": "Responde en una sola linea corta."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=50,
        )
        elapsed = round(time.time() - start, 2)
        return {
            "modelo": modelo,
            "ok": True,
            "respuesta": response.choices[0].message.content,
            "tiempo_seg": elapsed,
        }
    except Exception as e:
        elapsed = round(time.time() - start, 2)
        return {
            "modelo": modelo,
            "ok": False,
            "error": str(e),
            "tiempo_seg": elapsed,
        }


def _save_secrets_toml(secrets: dict[str, str]) -> None:
    """Guarda claves sensibles en .streamlit/secrets.toml."""
    secrets_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
    secrets_path.parent.mkdir(parents=True, exist_ok=True)

    # Leer existente
    existing: dict[str, str] = {}
    if secrets_path.exists():
        try:
            import tomllib
            with open(secrets_path, "rb") as f:
                existing = {k: str(v) for k, v in tomllib.load(f).items()}
        except Exception:
            pass

    existing.update(secrets)

    # Escribir TOML
    header = (
        "# Secrets - API Keys y credenciales sensibles\n"
        "# Este archivo NO se sube a git (esta en .gitignore)\n\n"
    )
    lines = [header]
    for k, v in existing.items():
        # Escapar comillas en el valor
        escaped = v.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{k} = "{escaped}"')
    secrets_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# Claves que se guardan en secrets.toml (sensibles)
_SECRET_KEYS = {"LLM_API_KEY", "GROQ_API_KEY", "HF_TOKEN", "SQL_PASSWORD"}


def save_env_config(values: dict[str, str]) -> None:
    """Guarda config en .env y secrets sensibles en .streamlit/secrets.toml."""
    import config as _cfg

    env_path = Path(__file__).parent / ".env"

    # Separar valores sensibles de no-sensibles
    secret_values = {k: v for k, v in values.items() if k in _SECRET_KEYS}
    env_values = {k: v for k, v in values.items() if k not in _SECRET_KEYS}

    # Guardar secrets en .streamlit/secrets.toml
    if secret_values:
        _save_secrets_toml(secret_values)

    # Guardar no-sensibles en .env
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    for key, val in env_values.items():
        found = False
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.startswith(f"{key}=") or stripped.startswith(f"# {key}="):
                lines[i] = f"{key}={val}"
                found = True
                break
        if not found:
            lines.append(f"{key}={val}")

    # Limpiar claves sensibles del .env si existen (moverlas a secrets)
    cleaned = []
    for line in lines:
        stripped = line.lstrip()
        is_secret_line = any(
            stripped.startswith(f"{sk}=") or stripped.startswith(f"# {sk}=")
            for sk in _SECRET_KEYS
        )
        if not is_secret_line:
            cleaned.append(line)
    lines = cleaned

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Actualizar config module en runtime
    for key, val in values.items():
        if hasattr(_cfg, key):
            setattr(_cfg, key, val)


def load_env_values() -> dict[str, str]:
    """Lee valores actuales del .env como diccionario."""
    env_path = Path(__file__).parent / ".env"
    values = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key, _, val = stripped.partition("=")
                values[key.strip()] = val.strip()
    return values


# ══════════════════════════════════════════════════════════════════════
#  CORTEX - Runners de Datos
# ══════════════════════════════════════════════════════════════════════


def run_ingesta_acd(file_bytes: bytes, filename: str) -> dict:
    df = _load_dataframe(file_bytes, filename)
    summary = _df_summary(df, "ACD")

    # Detectar columnas clave de ACD
    cols_lower = {c.lower(): c for c in df.columns}
    kpis_detectados = {}

    keywords_map = {
        "llamadas_recibidas": ["recibidas", "offered", "received", "entrantes", "inbound"],
        "llamadas_atendidas": ["atendidas", "answered", "handled", "contestadas"],
        "llamadas_abandonadas": ["abandonadas", "abandoned", "lost", "perdidas"],
        "tmo": ["tmo", "aht", "handle_time", "tiempo_medio"],
        "nivel_servicio": ["nivel_servicio", "service_level", "nds", "sl", "ans"],
        "tiempo_espera": ["espera", "wait", "asa", "speed_answer"],
    }

    for kpi, keywords in keywords_map.items():
        for kw in keywords:
            for col_lower, col_orig in cols_lower.items():
                if kw in col_lower:
                    kpis_detectados[kpi] = {
                        "columna": col_orig,
                        "promedio": round(float(df[col_orig].mean()), 2) if df[col_orig].dtype in ["float64", "int64"] else None,
                        "total": round(float(df[col_orig].sum()), 2) if df[col_orig].dtype in ["float64", "int64"] else None,
                    }
                    break
            if kpi in kpis_detectados:
                break

    summary["kpis_detectados"] = kpis_detectados
    summary["tipo_ingesta"] = "ACD"
    return summary


def run_ingesta_qa(file_bytes: bytes, filename: str) -> dict:
    df = _load_dataframe(file_bytes, filename)
    summary = _df_summary(df, "QA")

    # Detectar columnas de calidad
    cols_lower = {c.lower(): c for c in df.columns}
    for kw in ["puntaje", "score", "calificacion", "nota", "quality"]:
        for col_lower, col_orig in cols_lower.items():
            if kw in col_lower and df[col_orig].dtype in ["float64", "int64"]:
                summary["puntaje_columna"] = col_orig
                summary["puntaje_promedio"] = round(float(df[col_orig].mean()), 2)
                summary["puntaje_min"] = round(float(df[col_orig].min()), 2)
                summary["puntaje_max"] = round(float(df[col_orig].max()), 2)
                # Distribucion
                if df[col_orig].max() <= 100:
                    summary["distribucion"] = {
                        "excelente_90_100": int((df[col_orig] >= 90).sum()),
                        "bueno_80_89": int(((df[col_orig] >= 80) & (df[col_orig] < 90)).sum()),
                        "regular_70_79": int(((df[col_orig] >= 70) & (df[col_orig] < 80)).sum()),
                        "bajo_70": int((df[col_orig] < 70).sum()),
                    }
                break
        if "puntaje_promedio" in summary:
            break

    summary["tipo_ingesta"] = "QA"
    return summary


def run_ingesta_cx(file_bytes: bytes, filename: str) -> dict:
    df = _load_dataframe(file_bytes, filename)
    summary = _df_summary(df, "CX")

    cols_lower = {c.lower(): c for c in df.columns}

    # Detectar CSAT
    for kw in ["csat", "satisfaccion", "satisfaction"]:
        for col_lower, col_orig in cols_lower.items():
            if kw in col_lower and df[col_orig].dtype in ["float64", "int64"]:
                summary["csat_promedio"] = round(float(df[col_orig].mean()), 2)
                break

    # Detectar NPS
    for kw in ["nps", "promotor", "recommend"]:
        for col_lower, col_orig in cols_lower.items():
            if kw in col_lower and df[col_orig].dtype in ["float64", "int64"]:
                vals = df[col_orig].dropna()
                promotores = (vals >= 9).sum()
                detractores = (vals <= 6).sum()
                total = len(vals)
                if total > 0:
                    summary["nps"] = round(((promotores - detractores) / total) * 100, 1)
                break

    # Detectar verbatims
    for kw in ["comentario", "verbatim", "comment", "feedback", "observacion"]:
        for col_lower, col_orig in cols_lower.items():
            if kw in col_lower:
                verbatims = df[col_orig].dropna().tolist()
                summary["total_verbatims"] = len(verbatims)
                summary["muestra_verbatims"] = verbatims[:5]
                break

    summary["tipo_ingesta"] = "CX"
    return summary


def run_validar_fuentes(resultados: list[dict]) -> dict:
    fuentes = []
    for r in resultados:
        data = r.get("resultado", r)
        if isinstance(data, dict) and "tipo_ingesta" in data:
            fuentes.append(data)

    if len(fuentes) < 2:
        return {"error": "Se necesitan al menos 2 fuentes de datos para validar"}

    resumen = []
    for f in fuentes:
        resumen.append(f"Fuente {f.get('tipo_ingesta', '?')}: {f.get('filas', 0)} filas, columnas: {f.get('columnas', [])}")

    prompt = f"""Analiza estas {len(fuentes)} fuentes de datos de call center y genera un reporte de validacion:

{chr(10).join(resumen)}

Responde en JSON con:
- "consistencia": nivel general (alta/media/baja)
- "alertas": lista de inconsistencias detectadas
- "cruces_posibles": que datos se pueden cruzar entre fuentes
- "datos_faltantes": que informacion falta
- "recomendaciones": lista de acciones
"""
    return _llm_analyze(prompt)


def run_transcribir_audio(audio_bytes: bytes, filename: str) -> dict:
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


def run_generar_dialogo(audio_bytes: bytes, filename: str,
                        transcripcion_previa: dict | None = None) -> dict:
    from transcriber import load_whisper_model, transcribe
    from diarizer import (
        load_diarization_model, diarize,
        merge_transcription_diarization, format_dialogue,
    )
    temp_path = _temp_save(audio_bytes, filename)
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


# ══════════════════════════════════════════════════════════════════════
#  NEXUS - Runners de WFM / Capacidad
# ══════════════════════════════════════════════════════════════════════


def run_calcular_carga_trabajo(file_bytes: bytes | None, filename: str,
                                resultado_previo: dict | None = None) -> dict:
    if file_bytes:
        df = _load_dataframe(file_bytes, filename)
    elif resultado_previo and "muestra" in resultado_previo:
        import pandas as pd
        df = pd.DataFrame(resultado_previo["muestra"])
    else:
        return {"error": "Se requiere archivo de datos o resultado previo de CORTEX"}

    summary = _df_summary(df, "Carga de Trabajo")

    # Buscar columna de volumen
    cols_lower = {c.lower(): c for c in df.columns}
    vol_col = None
    for kw in ["llamadas", "calls", "recibidas", "offered", "volumen", "contactos"]:
        for cl, co in cols_lower.items():
            if kw in cl and df[co].dtype in ["float64", "int64"]:
                vol_col = co
                break
        if vol_col:
            break

    if vol_col:
        summary["columna_volumen"] = vol_col
        summary["total_llamadas"] = int(df[vol_col].sum())
        summary["promedio_diario"] = round(float(df[vol_col].mean()), 1)
        summary["pico"] = int(df[vol_col].max())
        summary["valle"] = int(df[vol_col].min())
        summary["desviacion"] = round(float(df[vol_col].std()), 1)

    summary["tipo_analisis"] = "carga_trabajo"
    return summary


def run_calcular_tmo(file_bytes: bytes | None, filename: str,
                     resultado_previo: dict | None = None) -> dict:
    if file_bytes:
        df = _load_dataframe(file_bytes, filename)
    elif resultado_previo and "muestra" in resultado_previo:
        import pandas as pd
        df = pd.DataFrame(resultado_previo["muestra"])
    else:
        return {"error": "Se requiere archivo de datos o resultado previo"}

    summary = _df_summary(df, "TMO")

    # Buscar columnas de tiempo
    cols_lower = {c.lower(): c for c in df.columns}
    tiempos = {}
    for kw, label in [("tmo", "tmo"), ("aht", "tmo"), ("talk", "talk_time"),
                       ("hold", "hold_time"), ("acw", "acw"), ("after_call", "acw"),
                       ("handle", "tmo")]:
        for cl, co in cols_lower.items():
            if kw in cl and df[co].dtype in ["float64", "int64"] and label not in tiempos:
                tiempos[label] = {
                    "columna": co,
                    "promedio": round(float(df[co].mean()), 1),
                    "mediana": round(float(df[co].median()), 1),
                    "p90": round(float(df[co].quantile(0.90)), 1),
                    "max": round(float(df[co].max()), 1),
                }
                break

    summary["tiempos_detectados"] = tiempos

    # Detectar outliers (> 2 desviaciones estandar)
    if "tmo" in tiempos:
        col = tiempos["tmo"]["columna"]
        mean = df[col].mean()
        std = df[col].std()
        outliers = int((df[col] > mean + 2 * std).sum())
        summary["outliers_tmo"] = outliers

    summary["tipo_analisis"] = "tmo"
    return summary


def run_calcular_staffing(file_bytes: bytes | None, filename: str,
                          texto: str = "",
                          resultados_previos: list[dict] | None = None) -> dict:
    import math

    # Intentar extraer parametros
    params = {}
    if texto:
        try:
            params = json.loads(texto)
        except json.JSONDecodeError:
            # Parsear texto libre con LLM
            prompt = f"""Extrae los parametros de staffing de este texto. Responde en JSON con:
- "llamadas_por_hora": numero
- "tmo_segundos": numero (tiempo medio de operacion en segundos)
- "nivel_servicio_pct": numero (ej: 80)
- "tiempo_respuesta_seg": numero (ej: 20)
- "shrinkage_pct": numero (ej: 30)

Texto: {texto}"""
            params = _llm_analyze(prompt)

    # Complementar con resultados previos
    if resultados_previos:
        for r in resultados_previos:
            data = r.get("resultado", {})
            if isinstance(data, dict):
                if "total_llamadas" in data and "llamadas_por_hora" not in params:
                    filas = data.get("filas", 1)
                    params["llamadas_por_hora"] = round(data["total_llamadas"] / max(filas, 1), 1)
                if "tiempos_detectados" in data and "tmo_segundos" not in params:
                    tmo = data["tiempos_detectados"].get("tmo", {})
                    if "promedio" in tmo:
                        params["tmo_segundos"] = tmo["promedio"]

    # Valores por defecto
    llamadas = params.get("llamadas_por_hora", 100)
    tmo = params.get("tmo_segundos", 360)
    nds_target = params.get("nivel_servicio_pct", 80) / 100
    t_respuesta = params.get("tiempo_respuesta_seg", 20)
    shrinkage = params.get("shrinkage_pct", 30) / 100

    # Erlang C simplificado
    intensidad = llamadas * (tmo / 3600)  # Erlangs
    agentes_base = math.ceil(intensidad)

    # Iterar para encontrar agentes necesarios
    mejor_nds = 0
    agentes_req = agentes_base
    for n in range(agentes_base, agentes_base + 100):
        if n <= intensidad:
            continue
        # Probabilidad de espera (Erlang C aproximado)
        rho = intensidad / n
        pw = (intensidad ** n / math.factorial(min(n, 170))) / (
            (intensidad ** n / math.factorial(min(n, 170))) +
            (1 - rho) * sum(intensidad ** k / math.factorial(k) for k in range(n))
        )
        nds = 1 - pw * math.exp(-(n - intensidad) * (t_respuesta / tmo))
        if nds >= nds_target:
            agentes_req = n
            mejor_nds = round(nds * 100, 1)
            break
        mejor_nds = round(nds * 100, 1)

    agentes_con_shrinkage = math.ceil(agentes_req / (1 - shrinkage))
    ocupacion = round((intensidad / agentes_req) * 100, 1) if agentes_req > 0 else 0

    return {
        "tipo_analisis": "staffing",
        "parametros": {
            "llamadas_por_hora": llamadas,
            "tmo_segundos": tmo,
            "nivel_servicio_target": f"{int(nds_target*100)}/{int(t_respuesta)}",
            "shrinkage_pct": round(shrinkage * 100, 1),
        },
        "resultado": {
            "erlangs": round(intensidad, 2),
            "agentes_minimos": agentes_req,
            "agentes_con_shrinkage": agentes_con_shrinkage,
            "nivel_servicio_proyectado": mejor_nds,
            "ocupacion_pct": ocupacion,
        },
    }


# ══════════════════════════════════════════════════════════════════════
#  SENTINEL - Runners de Calidad
# ══════════════════════════════════════════════════════════════════════


def run_evaluar_llamada(texto: str, resultado_previo: dict | None = None) -> dict:
    global _active_status_container
    from analyzer import create_llm_client, analyze_call

    dialogue = texto
    if resultado_previo:
        if "dialogo" in resultado_previo:
            dialogue = resultado_previo["dialogo"]
        elif "texto_completo" in resultado_previo:
            dialogue = resultado_previo["texto_completo"]

    if not dialogue or len(dialogue.strip()) < 20:
        return {"error": "Texto demasiado corto para evaluar"}

    client = create_llm_client()
    return analyze_call(client, dialogue, status_container=_active_status_container)


def run_monitoreo_kpis(file_bytes: bytes | None, filename: str,
                        resultados_previos: list[dict] | None = None) -> dict:
    datos = []
    if file_bytes:
        df = _load_dataframe(file_bytes, filename)
        datos.append(_df_summary(df, "KPIs"))

    if resultados_previos:
        for r in resultados_previos:
            data = r.get("resultado", {})
            if isinstance(data, dict):
                datos.append(data)

    if not datos:
        return {"error": "Se requieren datos de KPIs"}

    resumen = json.dumps(datos, ensure_ascii=False, default=str)[:3000]
    prompt = f"""Analiza estos datos de KPIs de calidad de call center:

{resumen}

Genera un monitoreo de KPIs en JSON con:
- "kpis": lista de objetos con "nombre", "valor", "target", "semaforo" (verde/amarillo/rojo), "tendencia" (sube/baja/estable)
- "alertas": lista de alertas criticas
- "resumen": texto breve del estado general
"""
    return _llm_analyze(prompt)


def run_detectar_rac(texto: str, resultados_previos: list[dict] | None = None) -> dict:
    contenido = texto
    if resultados_previos:
        partes = []
        for r in resultados_previos:
            data = r.get("resultado", {})
            if isinstance(data, dict):
                if "dialogo" in data:
                    partes.append(data["dialogo"])
                elif "texto_completo" in data:
                    partes.append(data["texto_completo"])
                elif "evaluacion" in data:
                    partes.append(json.dumps(data["evaluacion"], ensure_ascii=False))
        if partes:
            contenido = "\n---\n".join(partes)

    if not contenido or len(contenido.strip()) < 20:
        return {"error": "Se requiere contenido para analizar errores criticos"}

    prompt = f"""Analiza este contenido de call center y detecta errores criticos (RAC - Resolucion al Cliente):

{contenido[:3000]}

Busca:
1. Informacion incorrecta proporcionada al cliente
2. Procesos no seguidos segun protocolo
3. Compromisos hechos al cliente pero no registrados/cumplidos
4. Escalamientos necesarios que fueron omitidos
5. Datos del cliente no validados correctamente

Responde en JSON con:
- "errores_criticos": lista de objetos con "tipo", "descripcion", "severidad" (alta/media/baja), "evidencia"
- "total_errores": numero
- "riesgo_general": alto/medio/bajo
- "recomendaciones": lista de acciones correctivas
"""
    return _llm_analyze(prompt)


def run_generar_reporte_calidad(texto: str, resultado_previo: dict | None = None) -> dict:
    from analyzer import format_evaluation_report

    evaluation = resultado_previo if resultado_previo else {}
    if texto and not resultado_previo:
        try:
            evaluation = json.loads(texto)
        except json.JSONDecodeError:
            return {"error": "El texto no es un JSON de evaluacion valido"}
    if "evaluacion" not in evaluation and "resultado" in evaluation:
        evaluation = evaluation["resultado"]

    report = format_evaluation_report(evaluation)
    return {"reporte": report, "evaluacion_fuente": evaluation}


# ══════════════════════════════════════════════════════════════════════
#  LEDGER - Runners Financieros
# ══════════════════════════════════════════════════════════════════════


def run_calcular_facturacion(file_bytes: bytes | None, filename: str,
                              texto: str = "",
                              resultados_previos: list[dict] | None = None) -> dict:
    datos_volumen = {}
    if file_bytes:
        df = _load_dataframe(file_bytes, filename)
        summary = _df_summary(df, "Facturacion")
        datos_volumen = summary

    if resultados_previos:
        for r in resultados_previos:
            data = r.get("resultado", {})
            if isinstance(data, dict) and "total_llamadas" in data:
                datos_volumen["total_llamadas"] = data["total_llamadas"]

    parametros = texto if texto else "tarifa estandar por llamada"

    prompt = f"""Calcula la facturacion de un call center con estos datos:

Volumetria: {json.dumps(datos_volumen, ensure_ascii=False, default=str)[:2000]}

Parametros de tarifa: {parametros}

Si no hay tarifa especifica, usa tarifas tipicas del mercado colombiano.

Responde en JSON con:
- "lineas": lista de objetos con "concepto", "cantidad", "tarifa_unitaria", "subtotal"
- "total_facturacion": numero
- "moneda": "COP" o "USD"
- "periodo": periodo detectado o "mensual"
- "notas": observaciones
"""
    return _llm_analyze(prompt)


def run_calcular_bonos(file_bytes: bytes | None, filename: str,
                        texto: str = "",
                        resultados_previos: list[dict] | None = None) -> dict:
    kpis = {}
    if file_bytes:
        df = _load_dataframe(file_bytes, filename)
        kpis["datos_archivo"] = _df_summary(df, "Bonos")

    if resultados_previos:
        for r in resultados_previos:
            data = r.get("resultado", {})
            if isinstance(data, dict):
                kpis[r.get("agent_id", "unknown")] = data

    metas = texto if texto else "metas estandar de call center"

    prompt = f"""Calcula los bonos por desempeno de un call center:

KPIs alcanzados: {json.dumps(kpis, ensure_ascii=False, default=str)[:2500]}

Tabla de metas/bonos: {metas}

Responde en JSON con:
- "kpis_evaluados": lista de objetos con "kpi", "valor_alcanzado", "meta", "cumple" (si/no), "pct_cumplimiento"
- "bono_base": monto
- "ajuste_por_desempeno": porcentaje
- "bono_final": monto calculado
- "detalle": explicacion
"""
    return _llm_analyze(prompt)


def run_calcular_penalidades(file_bytes: bytes | None, filename: str,
                              texto: str = "",
                              resultados_previos: list[dict] | None = None) -> dict:
    kpis = {}
    if file_bytes:
        df = _load_dataframe(file_bytes, filename)
        kpis["datos_archivo"] = _df_summary(df, "Penalidades")

    if resultados_previos:
        for r in resultados_previos:
            data = r.get("resultado", {})
            if isinstance(data, dict):
                kpis[r.get("agent_id", "unknown")] = data

    slas = texto if texto else "SLAs estandar de call center"

    prompt = f"""Calcula las penalidades por incumplimiento de SLAs:

KPIs del periodo: {json.dumps(kpis, ensure_ascii=False, default=str)[:2500]}

SLAs contractuales: {slas}

Responde en JSON con:
- "slas_evaluados": lista de objetos con "sla", "target", "valor_real", "gap", "penalidad_aplica" (si/no)
- "penalidades": lista de objetos con "concepto", "monto", "justificacion"
- "total_penalidades": suma total
- "recomendaciones": acciones para evitar penalidades futuras
"""
    return _llm_analyze(prompt)


# ══════════════════════════════════════════════════════════════════════
#  ATLAS - Runners de Estrategia
# ══════════════════════════════════════════════════════════════════════


def _build_atlas_insumos(file_bytes, filename, resultados_previos):
    """Construye la lista de insumos con trazabilidad completa para Atlas."""
    insumos = []
    if file_bytes:
        df = _load_dataframe(file_bytes, filename)
        insumos.append({
            "fuente_tipo": "archivo",
            "fuente_archivo": filename,
            "agente_origen": "carga_directa",
            "datos": _df_summary(df, filename),
        })

    if resultados_previos:
        for r in resultados_previos:
            insumos.append({
                "fuente_tipo": "resultado_agente",
                "agente_origen": r.get("agent_name", "?"),
                "agente_id": r.get("agent_id", "?"),
                "skill_origen": r.get("skill_name", "?"),
                "skill_id": r.get("skill_id", "?"),
                "version_resultado": r.get("version", 1),
                "prompt_version": r.get("prompt_version", 0),
                "fecha_resultado": r.get("fecha", "?"),
                "hora_resultado": r.get("hora", "?"),
                "archivo_origen": r.get("input_summary", ""),
                "datos": r.get("resultado", {}),
            })
    return insumos


def _classify_insumos_by_module(insumos: list[dict]) -> dict:
    """Clasifica insumos por modulo/agente para reportes por seccion."""
    modules = {
        "datos": [],       # CORTEX
        "capacidad": [],   # NEXUS
        "calidad": [],     # SENTINEL
        "financiero": [],  # LEDGER
        "otros": [],
    }
    agent_map = {
        "CORTEX": "datos", "cortex": "datos",
        "NEXUS": "capacidad", "nexus": "capacidad",
        "SENTINEL": "calidad", "sentinel": "calidad",
        "LEDGER": "financiero", "ledger": "financiero",
    }
    for ins in insumos:
        agent = ins.get("agente_origen", ins.get("agente_id", ""))
        category = agent_map.get(agent, "otros")
        modules[category].append(ins)
    return {k: v for k, v in modules.items() if v}


_ATLAS_SOURCE_INSTRUCTIONS = """
IMPORTANTE - TRAZABILIDAD DE FUENTES:
Para CADA dato, metrica o KPI que menciones, DEBES indicar su origen con el formato:
  [Fuente: AGENTE / skill / archivo | fecha]
Ejemplo: "Nivel de servicio: 82% [Fuente: NEXUS / Calcular Staffing / datos_marzo.csv | 2026-03-15]"

Esto es CRITICO para la auditabilidad del informe.
"""


def run_consolidar_wbr(file_bytes: bytes | None, filename: str,
                        texto: str = "",
                        resultados_previos: list[dict] | None = None) -> dict:
    insumos = _build_atlas_insumos(file_bytes, filename, resultados_previos)

    if not insumos:
        return {"error": "Se necesitan datos de al menos 2 agentes para el WBR"}

    modules = _classify_insumos_by_module(insumos)
    contexto = texto if texto else "semana actual"

    prompt = f"""Genera un reporte WBR (Weekly Business Review) COMPLETO para comite ejecutivo de call center.

Periodo: {contexto}

{_ATLAS_SOURCE_INSTRUCTIONS}

Insumos del equipo (con trazabilidad):
{json.dumps(insumos, ensure_ascii=False, default=str)[:4000]}

Modulos con datos disponibles: {list(modules.keys())}

Estructura el WBR en JSON con:

- "periodo": semana evaluada
- "resumen_ejecutivo": 3-5 oraciones del estado general con CONCLUSION clara

- "fuentes_utilizadas": lista de objetos con "agente", "skill", "archivo", "fecha" (una entrada por cada insumo usado)

- "informe_por_modulo": objeto con una clave por modulo disponible, cada uno con:
  - "titulo": nombre del modulo (ej: "Datos e Ingesta", "Capacidad WFM", "Calidad", "Financiero")
  - "estado": "verde"/"amarillo"/"rojo"
  - "kpis": lista de objetos con "nombre", "valor", "target", "semaforo", "fuente" (agente+skill+archivo que lo genero)
  - "hallazgos": lista de hallazgos con fuente
  - "alertas": lista de alertas del modulo

- "dashboard_kpis": lista consolidada de los KPIs mas importantes con "kpi", "valor", "target", "semaforo" (verde/amarillo/rojo), "vs_semana_anterior", "fuente"

- "conclusiones": lista de 3-5 conclusiones clave del analisis
- "logros": lista de logros de la semana
- "riesgos": lista de riesgos con "riesgo", "impacto", "probabilidad", "fuente"
- "plan_accion": lista de objetos con "accion", "responsable", "fecha_limite", "prioridad"
- "outlook_proxima_semana": perspectiva con base en datos
"""
    return _llm_analyze(prompt)


def run_consolidar_mbr(file_bytes: bytes | None, filename: str,
                        texto: str = "",
                        resultados_previos: list[dict] | None = None) -> dict:
    insumos = _build_atlas_insumos(file_bytes, filename, resultados_previos)

    if not insumos:
        return {"error": "Se necesitan datos para el MBR"}

    modules = _classify_insumos_by_module(insumos)
    contexto = texto if texto else "mes actual"

    prompt = f"""Genera un reporte MBR (Monthly Business Review) COMPLETO para comite ejecutivo de call center.

Periodo: {contexto}

{_ATLAS_SOURCE_INSTRUCTIONS}

Insumos consolidados del equipo (con trazabilidad):
{json.dumps(insumos, ensure_ascii=False, default=str)[:4000]}

Modulos con datos disponibles: {list(modules.keys())}

Estructura el MBR en JSON con:

- "periodo": mes evaluado
- "resumen_ejecutivo": resumen de 5-8 oraciones con CONCLUSION estrategica

- "fuentes_utilizadas": lista de objetos con "agente", "skill", "archivo", "fecha"

- "informe_por_modulo": objeto con una clave por modulo, cada uno con:
  - "titulo": nombre descriptivo del modulo
  - "estado": "verde"/"amarillo"/"rojo"
  - "kpis": lista con "nombre", "valor", "target", "cumplimiento_pct", "tendencia", "fuente"
  - "analisis": texto de analisis detallado del modulo
  - "hallazgos": lista con fuente
  - "recomendaciones": lista de acciones especificas del modulo

- "dashboard_kpis": lista consolidada de KPIs principales con "kpi", "valor", "target", "cumplimiento_pct", "tendencia", "fuente"

- "financiero": resumen de facturacion, bonos y penalidades con fuentes
- "calidad": resumen de calidad y hallazgos con fuentes
- "operativo": resumen de staffing y capacidad con fuentes

- "conclusiones": lista de 5-7 conclusiones estrategicas del mes
- "top_3_logros": lista
- "top_3_riesgos": lista con "riesgo", "mitigacion", "fuente"
- "plan_estrategico": acciones para el proximo mes con prioridad
- "forecast_proximo_mes": proyeccion basada en tendencias
"""
    return _llm_analyze(prompt)


def run_analisis_cruzado(file_bytes: bytes | None, filename: str,
                          texto: str = "",
                          resultados_previos: list[dict] | None = None) -> dict:
    insumos = _build_atlas_insumos(file_bytes, filename, resultados_previos)

    if len(insumos) < 2:
        return {"error": "Se necesitan al menos 2 fuentes para analisis cruzado"}

    prompt = f"""Analiza estos datos de multiples fuentes de call center y genera correlaciones.

{_ATLAS_SOURCE_INSTRUCTIONS}

Datos con trazabilidad de origen:
{json.dumps(insumos, ensure_ascii=False, default=str)[:4000]}

{f"Contexto adicional: {texto}" if texto else ""}

Responde en JSON con:
- "fuentes_utilizadas": lista de objetos con "agente", "skill", "archivo", "fecha"
- "correlaciones": lista de objetos con "kpi_a", "kpi_b", "relacion", "fuente_a", "fuente_b"
- "patrones": lista de patrones detectados con "patron", "evidencia", "fuentes"
- "anomalias": lista con "anomalia", "valor_esperado", "valor_real", "fuente"
- "insights": hallazgos clave con fuente
- "conclusiones": lista de 3-5 conclusiones del analisis cruzado
- "recomendaciones": acciones basadas en el analisis con prioridad
"""
    return _llm_analyze(prompt)


def run_resumen_equipo(resultados_previos: list[dict] | None = None) -> dict:
    from collections import Counter
    all_results = resultados_previos if resultados_previos else load_all_results()

    agentes = Counter()
    skills = Counter()
    fechas = set()
    detalle_tareas = []

    for r in all_results:
        agent_name = r.get("agent_name", "?")
        skill_name = r.get("skill_name", "?")
        agentes[agent_name] += 1
        skills[skill_name] += 1
        fechas.add(r.get("fecha", ""))
        detalle_tareas.append({
            "agente": agent_name,
            "skill": skill_name,
            "archivo": r.get("input_summary", ""),
            "fecha": r.get("fecha", ""),
            "hora": r.get("hora", ""),
            "version": r.get("version", 1),
            "prompt_version": r.get("prompt_version", 0),
        })

    return {
        "total_tareas": len(all_results),
        "agentes_activos": dict(agentes),
        "habilidades_usadas": dict(skills),
        "dias_activos": len(fechas),
        "fechas": sorted(fechas),
        "agente_mas_activo": agentes.most_common(1)[0] if agentes else None,
        "skill_mas_usada": skills.most_common(1)[0] if skills else None,
        "detalle_tareas": detalle_tareas[-20:],  # Ultimas 20 tareas
    }


def run_informe_por_modulo(file_bytes: bytes | None, filename: str,
                            texto: str = "",
                            resultados_previos: list[dict] | None = None) -> dict:
    """Genera informes individuales por cada modulo/agente con datos disponibles."""
    insumos = _build_atlas_insumos(file_bytes, filename, resultados_previos)

    if not insumos:
        return {"error": "Se necesitan resultados de agentes para generar informes por modulo"}

    modules = _classify_insumos_by_module(insumos)
    contexto = texto if texto else "periodo actual"

    prompt = f"""Genera un INFORME DETALLADO POR MODULO del call center.

Periodo: {contexto}

{_ATLAS_SOURCE_INSTRUCTIONS}

Datos disponibles por modulo:
{json.dumps(modules, ensure_ascii=False, default=str)[:4000]}

Para CADA modulo que tenga datos, genera un informe individual completo.

Responde en JSON con:

- "periodo": periodo evaluado
- "fuentes_utilizadas": lista de objetos con "agente", "skill", "archivo", "fecha"

- "informes": lista de objetos, uno por modulo, cada uno con:
  - "modulo": nombre del modulo ("Datos e Ingesta" / "Capacidad WFM" / "Calidad" / "Financiero")
  - "agente_responsable": nombre del agente (CORTEX/NEXUS/SENTINEL/LEDGER)
  - "estado_general": "verde"/"amarillo"/"rojo"
  - "resumen": 2-3 oraciones del estado del modulo
  - "kpis": lista con "nombre", "valor", "target", "semaforo", "fuente"
  - "hallazgos": lista con "hallazgo" y "fuente"
  - "alertas": lista de alertas criticas
  - "fortalezas": lista de aspectos positivos
  - "oportunidades_mejora": lista de areas a mejorar
  - "recomendaciones": lista de acciones especificas

- "resumen_ejecutivo": vision general de todos los modulos
- "conclusiones": lista de conclusiones clave
"""
    return _llm_analyze(prompt)


def run_informe_consolidado(file_bytes: bytes | None, filename: str,
                             texto: str = "",
                             resultados_previos: list[dict] | None = None) -> dict:
    """Genera un informe consolidado que integra todos los modulos en una vision 360."""
    insumos = _build_atlas_insumos(file_bytes, filename, resultados_previos)

    if not insumos:
        return {"error": "Se necesitan resultados de multiples agentes para el informe consolidado"}

    modules = _classify_insumos_by_module(insumos)
    contexto = texto if texto else "periodo actual"

    prompt = f"""Genera un INFORME CONSOLIDADO 360 del call center que integre TODOS los modulos.

Periodo: {contexto}

{_ATLAS_SOURCE_INSTRUCTIONS}

Datos completos del equipo (con trazabilidad):
{json.dumps(insumos, ensure_ascii=False, default=str)[:4000]}

Modulos disponibles: {list(modules.keys())}

Este informe debe ser la vision COMPLETA y EJECUTIVA de la operacion. Responde en JSON con:

- "titulo": "Informe Consolidado 360 - Call Center"
- "periodo": periodo evaluado
- "fecha_generacion": fecha actual

- "fuentes_utilizadas": lista completa con "agente", "skill", "archivo", "fecha", "version"

- "dashboard_ejecutivo": objeto con:
  - "estado_general": "verde"/"amarillo"/"rojo"
  - "score_operacion": numero 0-100 representando salud general
  - "kpis_principales": lista de los 5-8 KPIs mas criticos con "nombre", "valor", "target", "semaforo", "tendencia", "fuente"

- "informe_por_modulo": objeto con clave por modulo:
  - "datos": resumen CORTEX con estado, kpis clave, hallazgos, fuentes
  - "capacidad": resumen NEXUS con estado, kpis clave, hallazgos, fuentes
  - "calidad": resumen SENTINEL con estado, kpis clave, hallazgos, fuentes
  - "financiero": resumen LEDGER con estado, kpis clave, hallazgos, fuentes

- "analisis_cruzado": objeto con:
  - "correlaciones": relaciones detectadas entre modulos
  - "dependencias": como un modulo afecta a otro
  - "cuellos_botella": donde estan los problemas principales

- "conclusiones": lista de 5-8 conclusiones estrategicas, cada una con:
  - "conclusion": texto
  - "impacto": alto/medio/bajo
  - "modulos_relacionados": lista de modulos afectados
  - "fuentes": de donde viene esta conclusion

- "plan_accion": lista priorizada con "accion", "responsable", "modulo", "prioridad" (1-5), "plazo"
- "riesgos": lista con "riesgo", "probabilidad", "impacto", "mitigacion", "fuente"
- "forecast": proyeccion para el proximo periodo
- "nota_metodologica": breve nota sobre las fuentes y limitaciones del analisis
"""
    return _llm_analyze(prompt)


# ══════════════════════════════════════════════════════════════════════
#  Dispatcher principal
# ══════════════════════════════════════════════════════════════════════


SKILL_RUNNERS = {
    # CORTEX
    "ingesta_acd": run_ingesta_acd,
    "ingesta_qa": run_ingesta_qa,
    "ingesta_cx": run_ingesta_cx,
    "validar_fuentes": run_validar_fuentes,
    "transcribir_audio": run_transcribir_audio,
    "generar_dialogo": run_generar_dialogo,
    # NEXUS
    "calcular_carga_trabajo": run_calcular_carga_trabajo,
    "calcular_tmo": run_calcular_tmo,
    "calcular_staffing": run_calcular_staffing,
    # SENTINEL
    "evaluar_llamada": run_evaluar_llamada,
    "monitoreo_kpis": run_monitoreo_kpis,
    "detectar_rac": run_detectar_rac,
    "generar_reporte_calidad": run_generar_reporte_calidad,
    # LEDGER
    "calcular_facturacion": run_calcular_facturacion,
    "calcular_bonos": run_calcular_bonos,
    "calcular_penalidades": run_calcular_penalidades,
    # ATLAS
    "consolidar_wbr": run_consolidar_wbr,
    "consolidar_mbr": run_consolidar_mbr,
    "analisis_cruzado": run_analisis_cruzado,
    "resumen_equipo": run_resumen_equipo,
    "informe_por_modulo": run_informe_por_modulo,
    "informe_consolidado": run_informe_consolidado,
}


def execute_skill(agent_id: str, skill_id: str, skill_name: str,
                  audio_bytes: bytes | None = None,
                  file_bytes: bytes | None = None,
                  filename: str = "",
                  texto: str = "",
                  resultado_previo: dict | None = None,
                  resultados_multiples: list[dict] | None = None,
                  status_container=None) -> dict:
    global _active_status_container, _active_agent_id
    _active_status_container = status_container
    _active_agent_id = agent_id

    runner = SKILL_RUNNERS.get(skill_id)
    if not runner:
        _active_status_container = None
        return {"error": f"Habilidad '{skill_id}' no implementada"}

    try:
        # ── CORTEX: audio ──
        if skill_id in ("transcribir_audio",):
            if not audio_bytes:
                return {"error": "Se requiere un archivo de audio"}
            result = runner(audio_bytes, filename)

        elif skill_id == "generar_dialogo":
            if not audio_bytes:
                return {"error": "Se requiere un archivo de audio"}
            result = runner(audio_bytes, filename, resultado_previo)

        # ── CORTEX: datos ──
        elif skill_id in ("ingesta_acd", "ingesta_qa", "ingesta_cx"):
            if not file_bytes:
                return {"error": "Se requiere un archivo de datos"}
            result = runner(file_bytes, filename)

        # ── Multi-resultado (validar, monitoreo, rac, atlas, etc) ──
        elif skill_id in ("validar_fuentes", "resumen_equipo"):
            items = resultados_multiples or []
            result = runner(items)

        elif skill_id in ("monitoreo_kpis", "detectar_rac"):
            result = runner(
                file_bytes, filename,
                resultados_previos=resultados_multiples,
            ) if file_bytes else runner(
                None, "",
                resultados_previos=resultados_multiples,
            )
            if skill_id == "detectar_rac":
                result = run_detectar_rac(texto, resultados_multiples)

        # ── NEXUS ──
        elif skill_id in ("calcular_carga_trabajo", "calcular_tmo"):
            result = runner(file_bytes, filename, resultado_previo)

        elif skill_id == "calcular_staffing":
            result = runner(file_bytes, filename, texto, resultados_multiples)

        # ── SENTINEL: evaluacion ──
        elif skill_id == "evaluar_llamada":
            result = runner(texto, resultado_previo)

        elif skill_id == "generar_reporte_calidad":
            result = runner(texto, resultado_previo)

        # ── LEDGER ──
        elif skill_id in ("calcular_facturacion", "calcular_bonos", "calcular_penalidades"):
            result = runner(file_bytes, filename, texto, resultados_multiples)

        # ── ATLAS ──
        elif skill_id in ("consolidar_wbr", "consolidar_mbr", "analisis_cruzado",
                           "informe_por_modulo", "informe_consolidado"):
            result = runner(file_bytes, filename, texto, resultados_multiples)

        else:
            return {"error": f"Skill '{skill_id}' sin dispatcher configurado"}

    except Exception as e:
        logger.error("Error ejecutando %s/%s: %s", agent_id, skill_id, e)
        result = {"error": str(e)}
    finally:
        _active_status_container = None
        _active_agent_id = None

    input_summary = filename if filename else (texto[:100] + "..." if len(texto) > 100 else texto)

    # Track which prompt version was used
    from prompt_manager import get_active_version
    prompt_ver = get_active_version(agent_id)

    record = save_result(agent_id, skill_id, skill_name, result, input_summary,
                         prompt_version=prompt_ver)
    return record
