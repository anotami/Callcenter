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
    """Genera resumen estadistico de un DataFrame con metricas extendidas."""
    summary = {
        "fuente": nombre_fuente,
        "filas": len(df),
        "columnas": list(df.columns),
        "tipos": {col: str(dtype) for col, dtype in df.dtypes.items()},
    }
    # Estadisticas extendidas para columnas numericas
    num_cols = df.select_dtypes(include=["number"]).columns.tolist()
    if num_cols:
        stats = {}
        for col in num_cols:
            s = df[col].dropna()
            if s.empty:
                stats[col] = {"min": None, "max": None, "promedio": None, "total": None}
                continue
            stats[col] = {
                "min": round(float(s.min()), 2),
                "max": round(float(s.max()), 2),
                "promedio": round(float(s.mean()), 2),
                "mediana": round(float(s.median()), 2),
                "total": round(float(s.sum()), 2),
                "std": round(float(s.std()), 2) if len(s) > 1 else 0,
                "p25": round(float(s.quantile(0.25)), 2),
                "p75": round(float(s.quantile(0.75)), 2),
                "nulos": int(df[col].isna().sum()),
            }
        summary["estadisticas"] = stats

    # Distribucion de columnas categoricas
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    if cat_cols:
        cat_dist = {}
        for col in cat_cols[:5]:
            nunique = df[col].nunique()
            if 1 <= nunique <= 30:
                cat_dist[col] = {
                    "valores_unicos": nunique,
                    "top_5": {str(k): int(v) for k, v in df[col].value_counts().head(5).items()},
                }
        if cat_dist:
            summary["categoricas"] = cat_dist

    # Muestra de datos
    summary["muestra"] = df.head(5).to_dict(orient="records")

    # Datos faltantes con porcentaje
    nulos = df.isnull().sum()
    if nulos.any():
        total = len(df)
        summary["datos_faltantes"] = {
            col: {"cantidad": int(n), "porcentaje": round(n / total * 100, 1)}
            for col, n in nulos.items() if n > 0
        }

    # Calidad de datos (score 0-100)
    total_cells = len(df) * len(df.columns)
    total_nulls = int(nulos.sum())
    completitud = round((1 - total_nulls / max(total_cells, 1)) * 100, 1)
    summary["calidad_datos"] = {
        "completitud_pct": completitud,
        "total_nulos": total_nulls,
        "filas_duplicadas": int(df.duplicated().sum()),
    }

    return summary


def _llm_analyze(prompt: str, system: str = "",
                  temperature: float = 0.1, max_tokens: int = 3000) -> dict:
    """Envia un prompt al LLM con fallback entre modelos y retorna JSON parseado.

    Args:
        prompt: Prompt de usuario
        system: System prompt (si vacio, usa el del agente activo)
        temperature: Temperatura para generacion (0.1 para datos, 0.3 para narrativas)
        max_tokens: Tokens maximos de respuesta
    """
    global _active_status_container, _active_agent_id
    from analyzer import call_llm, _extract_json
    from prompt_manager import get_current_prompt

    if not system:
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
            temperature=temperature,
            max_tokens=max_tokens,
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


def _save_secrets_toml(secrets: dict[str, str]) -> bool:
    """Guarda claves sensibles en .streamlit/secrets.toml.

    Returns True si se pudo escribir, False si el filesystem es de solo lectura
    (ej. Streamlit Cloud).
    """
    secrets_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
    try:
        secrets_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False

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
    try:
        secrets_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        return False
    return True


# Claves que se guardan en secrets.toml (sensibles)
_SECRET_KEYS = {"LLM_API_KEY", "GROQ_API_KEY", "HF_TOKEN", "SQL_PASSWORD"}


def save_env_config(values: dict[str, str]) -> None:
    """Guarda config en .env y secrets sensibles en .streamlit/secrets.toml.

    Si secrets.toml no es escribible (ej. Streamlit Cloud con filesystem
    de solo lectura), los secrets se guardan tambien en .env como fallback.
    """
    import config as _cfg

    env_path = Path(__file__).parent / ".env"

    # Separar valores sensibles de no-sensibles
    secret_values = {k: v for k, v in values.items() if k in _SECRET_KEYS}
    env_values = {k: v for k, v in values.items() if k not in _SECRET_KEYS}

    # Intentar guardar secrets en .streamlit/secrets.toml
    secrets_saved = False
    if secret_values:
        secrets_saved = _save_secrets_toml(secret_values)

    # Si no se pudieron guardar en secrets.toml, incluir en .env
    if not secrets_saved and secret_values:
        env_values.update(secret_values)

    # Guardar en .env
    lines = []
    if env_path.exists():
        try:
            lines = env_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []

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

    # Solo limpiar claves sensibles del .env si se guardaron en secrets.toml
    if secrets_saved:
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

    try:
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        # Ultimo recurso: al menos actualizar variables en runtime
        pass

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


def _fuzzy_match_column(col_lower: str, keywords: list[str]) -> bool:
    """Busca coincidencia fuzzy entre nombre de columna y keywords."""
    # Exact substring match
    for kw in keywords:
        if kw in col_lower:
            return True
    # Normalized match (remove underscores, spaces)
    normalized = col_lower.replace("_", "").replace(" ", "").replace("-", "")
    for kw in keywords:
        kw_norm = kw.replace("_", "").replace(" ", "").replace("-", "")
        if kw_norm in normalized:
            return True
    return False


def _detect_kpis(df, keywords_map: dict) -> dict:
    """Detecta KPIs en un DataFrame usando fuzzy matching."""
    cols_lower = {c.lower(): c for c in df.columns}
    kpis_detectados = {}

    for kpi, keywords in keywords_map.items():
        for col_lower, col_orig in cols_lower.items():
            if _fuzzy_match_column(col_lower, keywords):
                is_numeric = df[col_orig].dtype in ["float64", "int64", "float32", "int32"]
                if not is_numeric:
                    s = pd.to_numeric(df[col_orig], errors="coerce")
                    is_numeric = s.notna().sum() > 0
                    if is_numeric:
                        col_data = s
                    else:
                        continue
                else:
                    col_data = df[col_orig]

                kpis_detectados[kpi] = {
                    "columna": col_orig,
                    "promedio": round(float(col_data.mean()), 2),
                    "mediana": round(float(col_data.median()), 2),
                    "total": round(float(col_data.sum()), 2),
                    "min": round(float(col_data.min()), 2),
                    "max": round(float(col_data.max()), 2),
                }
                break
        # Already found this KPI
        if kpi in kpis_detectados:
            continue

    return kpis_detectados


def run_ingesta_acd(file_bytes: bytes, filename: str) -> dict:
    df = _load_dataframe(file_bytes, filename)
    summary = _df_summary(df, "ACD")

    keywords_map = {
        "llamadas_recibidas": ["recibidas", "offered", "received", "entrantes", "inbound", "incoming", "total_calls"],
        "llamadas_atendidas": ["atendidas", "answered", "handled", "contestadas", "connected"],
        "llamadas_abandonadas": ["abandonadas", "abandoned", "lost", "perdidas", "dropped"],
        "tmo": ["tmo", "aht", "handle_time", "tiempo_medio", "avg_handle", "duracion_promedio"],
        "nivel_servicio": ["nivel_servicio", "service_level", "nds", "sl_pct", "ans_pct", "service_pct"],
        "tiempo_espera": ["espera", "wait", "asa", "speed_answer", "avg_wait", "tiempo_cola"],
        "abandono_pct": ["abandono", "abandon_rate", "pct_abandonadas", "tasa_abandono"],
    }

    summary["kpis_detectados"] = _detect_kpis(df, keywords_map)
    summary["tipo_ingesta"] = "ACD"
    return summary


def run_ingesta_cubo_trafico(file_bytes: bytes, filename: str, texto: str = "") -> dict:
    """Ingesta del Cubo de Trafico historico desde INTEGRATEL."""
    df = _load_dataframe(file_bytes, filename)
    summary = _df_summary(df, "Cubo de Trafico")

    keywords_map = {
        "fecha": ["fecha", "date", "dia", "day"],
        "intervalo": ["intervalo", "interval", "franja", "media_hora", "half_hour", "time_slot"],
        "skill_cola": ["skill", "cola", "queue", "grupo", "campaign", "linea"],
        "llamadas_recibidas": ["recibidas", "offered", "received", "entrantes", "inbound", "total_calls", "volumen"],
        "llamadas_atendidas": ["atendidas", "answered", "handled", "contestadas"],
        "llamadas_abandonadas": ["abandonadas", "abandoned", "lost", "perdidas"],
        "tmo": ["tmo", "aht", "handle_time", "tiempo_medio", "avg_handle"],
        "asa": ["asa", "speed_answer", "avg_wait", "espera_promedio"],
        "nivel_servicio": ["nivel_servicio", "service_level", "nds", "sl_pct"],
    }
    summary["kpis_detectados"] = _detect_kpis(df, keywords_map)
    summary["tipo_ingesta"] = "cubo_trafico"

    # Detectar rango de fechas
    for col in df.columns:
        cl = col.lower().strip()
        if cl in ("fecha", "date", "dia"):
            try:
                fechas = pd.to_datetime(df[col], errors="coerce").dropna()
                if not fechas.empty:
                    summary["rango_fechas"] = {
                        "desde": str(fechas.min().date()),
                        "hasta": str(fechas.max().date()),
                        "dias": int((fechas.max() - fechas.min()).days) + 1,
                    }
            except Exception:
                pass
            break

    # Detectar intervalos unicos
    for col in df.columns:
        cl = col.lower().strip()
        if cl in ("intervalo", "interval", "franja", "media_hora", "half_hour"):
            n_int = df[col].nunique()
            summary["intervalos_unicos"] = n_int
            break

    if texto:
        summary["contexto_usuario"] = texto

    return summary


def run_ingesta_malla(file_bytes: bytes, filename: str, texto: str = "") -> dict:
    """Ingesta de la Malla de Proveedor desde Kipu."""
    df = _load_dataframe(file_bytes, filename)
    summary = _df_summary(df, "Malla Proveedor")

    keywords_map = {
        "fecha": ["fecha", "date", "dia"],
        "intervalo": ["intervalo", "interval", "franja", "media_hora"],
        "proveedor": ["proveedor", "provider", "outsourcer", "vendor", "bpo"],
        "planificado": ["planificado", "planned", "plan", "requerido_plan"],
        "disponible": ["disponible", "available", "avail_plan"],
        "pronostico": ["pronostico", "forecast", "volumen_forecast", "llamadas_pronostico"],
        "tmo_plan": ["tmo", "aht", "tmo_plan", "tmo_pronostico"],
        "nivel_intervalo": ["nivel_intervalo", "nivel_servicio", "nds", "service_level"],
    }
    summary["kpis_detectados"] = _detect_kpis(df, keywords_map)
    summary["tipo_ingesta"] = "malla_proveedor"

    # Detectar proveedores
    for col in df.columns:
        cl = col.lower().strip()
        if cl in ("proveedor", "provider", "outsourcer", "vendor", "bpo"):
            proveedores = df[col].dropna().unique().tolist()
            summary["proveedores"] = [str(p) for p in proveedores[:20]]
            summary["total_proveedores"] = len(proveedores)
            break

    if texto:
        summary["contexto_usuario"] = texto

    return summary


def run_ingesta_gtr(file_bytes: bytes, filename: str, texto: str = "") -> dict:
    """Ingesta de datos GTR (Gestion en Tiempo Real)."""
    df = _load_dataframe(file_bytes, filename)
    summary = _df_summary(df, "GTR Datos Reales")

    keywords_map = {
        "fecha": ["fecha", "date", "dia"],
        "intervalo": ["intervalo", "interval", "franja"],
        "logueados_real": ["logueado", "logged", "login", "conectados", "logueados_real", "rac_logueado"],
        "disponibles_real": ["disponible", "available", "avail", "disponibles_real", "rac_disponible"],
        "aux_break": ["break", "descanso", "pausa", "aux_break"],
        "aux_coaching": ["coaching", "coach", "aux_coaching"],
        "aux_capacitacion": ["capacitacion", "training", "formacion", "aux_capacitacion"],
        "atendidas_real": ["atendidas", "answered", "handled", "atendidas_real"],
        "llamadas_real": ["llamadas", "calls", "volumen_real", "recibidas_real"],
        "tmo_real": ["tmo", "aht", "tmo_real", "handle_time_real"],
        "avail_tiempo": ["avail_seg", "avail_time", "tiempo_avail", "available_time"],
    }
    summary["kpis_detectados"] = _detect_kpis(df, keywords_map)
    summary["tipo_ingesta"] = "gtr_datos_reales"

    if texto:
        summary["contexto_usuario"] = texto

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

    # Validacion automatica pre-LLM
    validacion_auto = {
        "fuentes_analizadas": len(fuentes),
        "calidad_por_fuente": [],
        "alertas_automaticas": [],
    }

    for f in fuentes:
        tipo = f.get("tipo_ingesta", "?")
        filas = f.get("filas", 0)
        calidad = f.get("calidad_datos", {})
        completitud = calidad.get("completitud_pct", 100)
        duplicados = calidad.get("filas_duplicadas", 0)

        validacion_auto["calidad_por_fuente"].append({
            "fuente": tipo,
            "filas": filas,
            "completitud_pct": completitud,
            "duplicados": duplicados,
        })

        if completitud < 90:
            validacion_auto["alertas_automaticas"].append(
                f"Fuente {tipo}: completitud baja ({completitud}%)")
        if duplicados > 0:
            validacion_auto["alertas_automaticas"].append(
                f"Fuente {tipo}: {duplicados} filas duplicadas")
        if filas == 0:
            validacion_auto["alertas_automaticas"].append(
                f"Fuente {tipo}: sin datos (0 filas)")

    resumen = []
    for f in fuentes:
        resumen.append(
            f"Fuente {f.get('tipo_ingesta', '?')}: {f.get('filas', 0)} filas, "
            f"columnas: {f.get('columnas', [])}, "
            f"calidad: {f.get('calidad_datos', {})}"
        )

    prompt = f"""Analiza estas {len(fuentes)} fuentes de datos de call center y genera un reporte de validacion:

{chr(10).join(resumen)}

Validacion automatica previa:
{json.dumps(validacion_auto, ensure_ascii=False)}

Responde en JSON con:
- "consistencia": nivel general (alta/media/baja)
- "score_calidad": numero 0-100 representando calidad general de los datos
- "alertas": lista de inconsistencias detectadas (incluir las automaticas + nuevas)
- "cruces_posibles": que datos se pueden cruzar entre fuentes
- "datos_faltantes": que informacion falta
- "recomendaciones": lista de acciones para mejorar calidad
"""
    result = _llm_analyze(prompt)
    # Incluir validacion automatica en resultado
    if isinstance(result, dict) and "error" not in result:
        result["validacion_automatica"] = validacion_auto
    return result


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


_WFM_COLUMNS = {
    # ── Dimensiones / identificadores ──
    "PERIODO", "PROVEEDOR", "PLATAFORMA", "AGENTE",
    "ANTIGUEDAD_AGENTE", "ANTIGUEDAD_AGENTE_AGRUPA",
    "ANTIGUEDAD_PLATAFORMA", "ANTIGUEDAD_PLATAFORMA_AGRUPADO",
    "PLATAFORMA_MAYOR", "GRUPO_PLATAFORMA",
    "DIAS_LABORADOS_MES", "DIAS_LABORADOS_PLATAFORMA_TOTAL",
    # ── Volumen ──
    "ATENDIDAS",
    # ── Reiteradas ──
    "CANTIDAD_REITERADAS", "REITERADAS_DENOMINADOR",
    "%_REITERADAS", "CUARTIL_REITERADAS",
    # ── Transferencias ──
    "CANTIDAD_TRANSFERENCIAS", "TRANSFERENCIAS_DENOMINADOR",
    "%_TRANSFERENCIAS", "CUARTIL_TRANSFERENCIAS",
    # ── TMO ──
    "NUMERADOR_TMO", "TMO", "CUARTIL_TMO",
    # ── Llamadas cortas ──
    "LLAMADAS_CORTAS", "%_LLAMADAS_CORTAS",
    # ── Tiempos de estado ──
    "TIEMPO_LOGIN_SEGUNDOS",
    "AVAIL_SEGUNDOS", "%_AVAIL", "CUARTIL_AVAIL",
    "NO_READY_SEGUNDOS", "%_NO_READY", "CUARTIL_NO_READY",
    "OCUPADO_SEGUNDOS", "%_OCUPACION", "CUARTIL_OCUPACION",
    "HOLD_SEGUNDOS", "%_HOLD", "CUARTIL_HOLD",
    # ── Encuestas / Calidad ──
    "TOTAL_ENCUESTAS_OUT", "CALIDAD_DENOMINADOR",
    "SOLUCION_NUMERADOR", "%_SOLUCION_OUT", "CUARTIL_SOLUCION_OUT",
    "NPS_NUMERADOR", "NPS_OUT", "CUARTIL_NPS",
    # ── Errores campo ──
    "ERROR_ENVIO_A_CAMPO", "CUARTIL_ERROR_ENVIO_A_CAMPO",
    # ── Cuartil resumen ──
    "PEOR_CUARTIL",
    # ── Filtros ──
    "FILTRO_ATENDIDAS_EN_EL_MES", "MESA_ANTIGUEDAD_AGENTE_AGRUPA",
    "FILTRO_TRANSFERENCIAS", "FILTRO_REITERADAS",
    "TRANSFERIDAS_RETEN",
    # ── Comercial ──
    "RECLAMOS", "SAR", "TC", "OPINIONES",
    "PREVENTAS", "CUARTIL_PREVENTAS",
    "OLI_POTENCIAL", "EFECT",
    # ── Conexion ──
    "FECHA_ULTIMA_CONEXION",
}

# Columnas que contienen porcentajes (0-100 o 0-1)
_WFM_PCT_COLS = {
    "%_REITERADAS", "%_TRANSFERENCIAS", "%_LLAMADAS_CORTAS",
    "%_AVAIL", "%_NO_READY", "%_OCUPACION", "%_HOLD",
    "%_SOLUCION_OUT",
}

# Columnas de cuartil (1-4)
_WFM_CUARTIL_COLS = {
    "CUARTIL_REITERADAS", "CUARTIL_TRANSFERENCIAS", "CUARTIL_TMO",
    "CUARTIL_AVAIL", "CUARTIL_NO_READY", "CUARTIL_OCUPACION",
    "CUARTIL_HOLD", "CUARTIL_SOLUCION_OUT", "CUARTIL_NPS",
    "CUARTIL_ERROR_ENVIO_A_CAMPO", "CUARTIL_PREVENTAS",
    "PEOR_CUARTIL",
}

# Columnas numericas clave para estadisticas
_WFM_KPI_COLS = {
    "ATENDIDAS", "TMO", "%_REITERADAS", "%_TRANSFERENCIAS",
    "%_AVAIL", "%_NO_READY", "%_OCUPACION", "%_HOLD",
    "NPS_OUT", "%_SOLUCION_OUT", "PREVENTAS", "RECLAMOS",
}


def _normalize_wfm_columns(df) -> tuple:
    """Normaliza nombres de columnas de la base WFM.

    Devuelve (df_normalizado, mapa_de_alias).
    """
    alias_map = {}
    rename = {}
    for col in df.columns:
        upper = col.strip().upper().replace(" ", "_")
        if upper != col:
            rename[col] = upper
            alias_map[upper] = col
    if rename:
        df = df.rename(columns=rename)
    return df, alias_map


def _wfm_dimension_summary(df, col_name: str) -> dict | None:
    """Resumen de cardinalidad para una columna de dimension."""
    if col_name not in df.columns:
        return None
    series = df[col_name].dropna()
    if series.empty:
        return None
    unique = series.nunique()
    top = series.value_counts().head(10)
    return {
        "valores_unicos": unique,
        "top_10": {str(k): int(v) for k, v in top.items()},
    }


def _wfm_kpi_stats(df, cols: list[str]) -> dict:
    """Estadisticas detalladas para columnas KPI numericas."""
    stats = {}
    for col in cols:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        if s.isna().all():
            continue
        stats[col] = {
            "min": round(float(s.min()), 2),
            "max": round(float(s.max()), 2),
            "promedio": round(float(s.mean()), 2),
            "mediana": round(float(s.median()), 2),
            "std": round(float(s.std()), 2),
            "p10": round(float(s.quantile(0.10)), 2),
            "p90": round(float(s.quantile(0.90)), 2),
            "nulos": int(s.isna().sum()),
        }
    return stats


def _wfm_cuartil_distribution(df, cols: list[str]) -> dict:
    """Distribucion de cuartiles."""
    dist = {}
    for col in cols:
        if col not in df.columns:
            continue
        s = df[col].dropna()
        if s.empty:
            continue
        counts = s.value_counts().sort_index()
        dist[col] = {str(k): int(v) for k, v in counts.items()}
    return dist


def run_ingesta_wfm(file_bytes: bytes | None, filename: str,
                    texto: str = "") -> dict:
    """Ingesta de la base de datos maestra WFM con 60+ columnas por agente/periodo."""
    if not file_bytes:
        return {"error": "Se requiere un archivo de datos (.csv o .xlsx)"}

    df = _load_dataframe(file_bytes, filename)
    df, alias_map = _normalize_wfm_columns(df)

    # ── Columnas reconocidas vs desconocidas ──
    col_set = set(df.columns)
    reconocidas = col_set & _WFM_COLUMNS
    no_reconocidas = col_set - _WFM_COLUMNS

    # ── Resumen basico ──
    summary = _df_summary(df, filename)
    summary["tipo_analisis"] = "ingesta_wfm"
    summary["columnas_reconocidas"] = sorted(reconocidas)
    summary["columnas_no_reconocidas"] = sorted(no_reconocidas)
    summary["cobertura_columnas_pct"] = round(
        len(reconocidas) / max(len(col_set), 1) * 100, 1
    )

    # ── Dimensiones ──
    dimensiones = {}
    for dim_col in ["PERIODO", "PROVEEDOR", "PLATAFORMA", "GRUPO_PLATAFORMA",
                    "ANTIGUEDAD_AGENTE_AGRUPA", "ANTIGUEDAD_PLATAFORMA_AGRUPADO",
                    "PLATAFORMA_MAYOR"]:
        res = _wfm_dimension_summary(df, dim_col)
        if res:
            dimensiones[dim_col] = res
    summary["dimensiones"] = dimensiones

    # ── Total agentes unicos ──
    if "AGENTE" in df.columns:
        summary["total_agentes"] = int(df["AGENTE"].nunique())

    # ── Periodos detectados ──
    if "PERIODO" in df.columns:
        periodos = sorted(df["PERIODO"].dropna().unique().tolist())
        summary["periodos"] = [str(p) for p in periodos]
        summary["total_periodos"] = len(periodos)

    # ── KPIs numericos ──
    kpi_cols_present = [c for c in _WFM_KPI_COLS if c in df.columns]
    summary["kpis"] = _wfm_kpi_stats(df, kpi_cols_present)

    # ── Cuartiles ──
    cuartil_cols_present = [c for c in _WFM_CUARTIL_COLS if c in df.columns]
    summary["distribucion_cuartiles"] = _wfm_cuartil_distribution(df, cuartil_cols_present)

    # ── Tiempos de estado ──
    tiempos_cols = ["TIEMPO_LOGIN_SEGUNDOS", "AVAIL_SEGUNDOS", "NO_READY_SEGUNDOS",
                    "OCUPADO_SEGUNDOS", "HOLD_SEGUNDOS"]
    tiempos_present = [c for c in tiempos_cols if c in df.columns]
    if tiempos_present:
        summary["tiempos_estado"] = _wfm_kpi_stats(df, tiempos_present)

    # ── Deteccion de alertas automaticas ──
    alertas = []

    # Agentes con PEOR_CUARTIL == 4 (o el peor)
    if "PEOR_CUARTIL" in df.columns:
        peor = pd.to_numeric(df["PEOR_CUARTIL"], errors="coerce")
        n_cuartil4 = int((peor >= 4).sum())
        if n_cuartil4 > 0:
            alertas.append({
                "tipo": "cuartil_critico",
                "mensaje": f"{n_cuartil4} registros con PEOR_CUARTIL >= 4",
                "cantidad": n_cuartil4,
            })

    # TMO fuera de rango (> p90)
    if "TMO" in df.columns:
        tmo = pd.to_numeric(df["TMO"], errors="coerce").dropna()
        if not tmo.empty:
            p90 = tmo.quantile(0.90)
            n_alto = int((tmo > p90).sum())
            if n_alto > 0:
                alertas.append({
                    "tipo": "tmo_alto",
                    "mensaje": f"{n_alto} registros con TMO > p90 ({round(float(p90), 0)}s)",
                    "cantidad": n_alto,
                    "umbral_p90": round(float(p90), 0),
                })

    # NPS negativo
    if "NPS_OUT" in df.columns:
        nps = pd.to_numeric(df["NPS_OUT"], errors="coerce").dropna()
        if not nps.empty:
            n_neg = int((nps < 0).sum())
            if n_neg > 0:
                alertas.append({
                    "tipo": "nps_negativo",
                    "mensaje": f"{n_neg} registros con NPS negativo",
                    "cantidad": n_neg,
                })

    # Ocupacion extrema (> 95%)
    if "%_OCUPACION" in df.columns:
        ocu = pd.to_numeric(df["%_OCUPACION"], errors="coerce").dropna()
        if not ocu.empty:
            # Determinar si esta en 0-1 o 0-100
            max_val = ocu.max()
            umbral = 95 if max_val > 1 else 0.95
            n_extrema = int((ocu > umbral).sum())
            if n_extrema > 0:
                alertas.append({
                    "tipo": "ocupacion_extrema",
                    "mensaje": f"{n_extrema} registros con ocupacion > 95%",
                    "cantidad": n_extrema,
                })

    # Datos faltantes criticos
    criticas = ["ATENDIDAS", "TMO", "AGENTE", "PERIODO"]
    for col in criticas:
        if col in df.columns:
            nulos = int(df[col].isna().sum())
            if nulos > 0:
                alertas.append({
                    "tipo": "datos_faltantes",
                    "mensaje": f"{col} tiene {nulos} valores nulos ({round(nulos/len(df)*100,1)}%)",
                    "columna": col,
                    "cantidad": nulos,
                })

    summary["alertas"] = alertas

    # ── Resumen por proveedor (si existe) ──
    if "PROVEEDOR" in df.columns and "ATENDIDAS" in df.columns:
        agg_cols = {}
        if "ATENDIDAS" in df.columns:
            agg_cols["ATENDIDAS"] = "sum"
        if "TMO" in df.columns:
            agg_cols["TMO"] = "mean"
        if "AGENTE" in df.columns:
            agg_cols["AGENTE"] = "nunique"
        if agg_cols:
            resumen_prov = df.groupby("PROVEEDOR").agg(agg_cols)
            resumen_prov = resumen_prov.round(1)
            if "AGENTE" in resumen_prov.columns:
                resumen_prov = resumen_prov.rename(columns={"AGENTE": "agentes_unicos"})
            summary["resumen_por_proveedor"] = resumen_prov.to_dict(orient="index")

    # ── Resumen por plataforma (si existe) ──
    if "PLATAFORMA" in df.columns and "ATENDIDAS" in df.columns:
        agg_cols = {"ATENDIDAS": "sum"}
        if "TMO" in df.columns:
            agg_cols["TMO"] = "mean"
        if "AGENTE" in df.columns:
            agg_cols["AGENTE"] = "nunique"
        resumen_plat = df.groupby("PLATAFORMA").agg(agg_cols)
        resumen_plat = resumen_plat.round(1)
        if "AGENTE" in resumen_plat.columns:
            resumen_plat = resumen_plat.rename(columns={"AGENTE": "agentes_unicos"})
        summary["resumen_por_plataforma"] = resumen_plat.to_dict(orient="index")

    # ── Muestra ampliada para LLM (10 filas) ──
    summary["muestra"] = df.head(10).to_dict(orient="records")

    # ── Enviar a LLM para analisis contextual si hay texto del usuario ──
    if texto and texto.strip():
        resumen_json = json.dumps(summary, ensure_ascii=False, cls=_SafeEncoder)
        # Truncar para el prompt
        resumen_truncado = resumen_json[:12000]
        prompt = f"""Analiza esta base de datos WFM de call center.

Contexto del usuario: {texto}

Datos cargados:
{resumen_truncado}

Responde en JSON con:
- "analisis": texto con hallazgos principales sobre los datos
- "kpis_destacados": lista de los 5 KPIs mas relevantes con "nombre", "valor", "interpretacion"
- "segmentos_criticos": proveedores, plataformas o agentes que requieren atencion
- "recomendaciones": lista de acciones sugeridas
"""
        llm_result = _llm_analyze(prompt)
        summary["analisis_llm"] = llm_result

    return summary


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
#  NEXUS - Runners WFM Ciclo Completo (OUTPUTs I-VI)
# ══════════════════════════════════════════════════════════════════════


def _erlang_c_calc(llamadas: float, tmo: float, nds_target: float = 0.8,
                   t_respuesta: float = 20) -> dict:
    """Calculo Erlang C reutilizable. Retorna agentes_req, nds, erlangs, ocupacion."""
    import math
    intensidad = llamadas * (tmo / 3600)
    agentes_base = max(math.ceil(intensidad), 1)
    mejor_nds = 0
    agentes_req = agentes_base
    for n in range(agentes_base, agentes_base + 100):
        if n <= intensidad:
            continue
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
    ocupacion = round((intensidad / agentes_req) * 100, 1) if agentes_req > 0 else 0
    return {
        "erlangs": round(intensidad, 2),
        "agentes_req": agentes_req,
        "nivel_servicio": mejor_nds,
        "ocupacion_pct": ocupacion,
    }


def run_pronostico_erlang(file_bytes: bytes | None, filename: str,
                          texto: str = "",
                          resultados_previos: list[dict] | None = None) -> dict:
    """OUTPUT I: Rac Requerido Disponible - Erlang C con cubo de trafico/pronostico."""
    import math

    intervalos = []

    # Intentar cargar datos de archivo
    if file_bytes:
        df = _load_dataframe(file_bytes, filename)
        cols_lower = {c.lower(): c for c in df.columns}
        # Buscar columnas de volumen y TMO
        vol_col = tmo_col = intervalo_col = None
        for kw in ["llamadas", "calls", "volumen", "offered", "forecast", "pronostico"]:
            for cl, co in cols_lower.items():
                if kw in cl and df[co].dtype in ["float64", "int64"]:
                    vol_col = co
                    break
            if vol_col:
                break
        for kw in ["tmo", "aht", "duracion"]:
            for cl, co in cols_lower.items():
                if kw in cl and df[co].dtype in ["float64", "int64"]:
                    tmo_col = co
                    break
            if tmo_col:
                break
        for kw in ["intervalo", "interval", "hora", "time", "periodo"]:
            for cl, co in cols_lower.items():
                if kw in cl:
                    intervalo_col = co
                    break
            if intervalo_col:
                break

        if vol_col:
            for _, row in df.iterrows():
                llamadas = float(row[vol_col]) if pd.notna(row[vol_col]) else 0
                tmo_val = float(row[tmo_col]) if tmo_col and pd.notna(row[tmo_col]) else 360
                intervalo = str(row[intervalo_col]) if intervalo_col and pd.notna(row[intervalo_col]) else "N/A"
                if llamadas > 0:
                    ec = _erlang_c_calc(llamadas, tmo_val)
                    intervalos.append({
                        "intervalo": intervalo,
                        "llamadas_forecast": round(llamadas, 1),
                        "tmo_forecast": round(tmo_val, 1),
                        "rac_requerido_disponible": ec["agentes_req"],
                        "erlangs": ec["erlangs"],
                        "nds_proyectado": ec["nivel_servicio"],
                        "ocupacion_pct": ec["ocupacion_pct"],
                    })

    # Complementar con resultados previos (ej. cubo de trafico de CORTEX)
    if not intervalos and resultados_previos:
        for r in resultados_previos:
            data = r.get("resultado", {})
            if isinstance(data, dict):
                if "total_llamadas" in data:
                    llamadas = data.get("total_llamadas", 100)
                    filas = data.get("filas", 1)
                    llamadas_h = round(llamadas / max(filas, 1), 1)
                    tmo_val = 360
                    if "tiempos_detectados" in data:
                        tmo_val = data["tiempos_detectados"].get("tmo", {}).get("promedio", 360)
                    ec = _erlang_c_calc(llamadas_h, tmo_val)
                    intervalos.append({
                        "intervalo": "Promedio global",
                        "llamadas_forecast": llamadas_h,
                        "tmo_forecast": tmo_val,
                        "rac_requerido_disponible": ec["agentes_req"],
                        "erlangs": ec["erlangs"],
                        "nds_proyectado": ec["nivel_servicio"],
                        "ocupacion_pct": ec["ocupacion_pct"],
                    })

    # Parametros manuales via texto
    if not intervalos and texto:
        params = {}
        try:
            params = json.loads(texto)
        except json.JSONDecodeError:
            prompt = f"""Extrae parametros de pronostico WFM del texto. Responde JSON con:
- "llamadas_por_hora": numero
- "tmo_segundos": numero
Texto: {texto}"""
            params = _llm_analyze(prompt)
        llamadas = params.get("llamadas_por_hora", 100)
        tmo_val = params.get("tmo_segundos", 360)
        ec = _erlang_c_calc(llamadas, tmo_val)
        intervalos.append({
            "intervalo": "Manual",
            "llamadas_forecast": llamadas,
            "tmo_forecast": tmo_val,
            "rac_requerido_disponible": ec["agentes_req"],
            "erlangs": ec["erlangs"],
            "nds_proyectado": ec["nivel_servicio"],
            "ocupacion_pct": ec["ocupacion_pct"],
        })

    if not intervalos:
        return {"error": "Se requiere cubo de trafico, datos de forecast o parametros manuales"}

    total_rac = sum(i["rac_requerido_disponible"] for i in intervalos)
    return {
        "tipo_analisis": "pronostico_erlang",
        "output": "OUTPUT_I",
        "descripcion": "Rac Requerido Disponible (Erlang C con pronostico)",
        "intervalos": intervalos,
        "resumen": {
            "total_intervalos": len(intervalos),
            "rac_requerido_total": total_rac,
            "rac_requerido_promedio": round(total_rac / len(intervalos), 1),
            "nds_promedio": round(sum(i["nds_proyectado"] for i in intervalos) / len(intervalos), 1),
        },
    }


def run_planificacion_proveedor(file_bytes: bytes | None, filename: str,
                                texto: str = "",
                                resultados_previos: list[dict] | None = None) -> dict:
    """OUTPUT II: Rac Planificado Disponible - Erlang + 10% volumen + reductores."""
    import math

    # Parametros de reductores por defecto
    params = {"volumen_extra_pct": 10, "shrinkage_pct": 30, "ausentismo_pct": 5,
              "rotacion_pct": 3, "capacitacion_pct": 2}
    if texto:
        try:
            user_params = json.loads(texto)
            params.update(user_params)
        except json.JSONDecodeError:
            pass

    intervalos_base = []

    # Usar OUTPUT I previo
    if resultados_previos:
        for r in resultados_previos:
            data = r.get("resultado", {})
            if isinstance(data, dict) and data.get("output") == "OUTPUT_I":
                intervalos_base = data.get("intervalos", [])
                break
            # Tambien aceptar cubo de trafico
            if isinstance(data, dict) and "total_llamadas" in data:
                llamadas_h = data["total_llamadas"] / max(data.get("filas", 1), 1)
                tmo_val = 360
                if "tiempos_detectados" in data:
                    tmo_val = data["tiempos_detectados"].get("tmo", {}).get("promedio", 360)
                ec = _erlang_c_calc(llamadas_h, tmo_val)
                intervalos_base.append({
                    "intervalo": "Promedio",
                    "llamadas_forecast": llamadas_h,
                    "tmo_forecast": tmo_val,
                    "rac_requerido_disponible": ec["agentes_req"],
                })

    # Archivo directo
    if not intervalos_base and file_bytes:
        pronostico = run_pronostico_erlang(file_bytes, filename, "", None)
        if "intervalos" in pronostico:
            intervalos_base = pronostico["intervalos"]

    if not intervalos_base:
        return {"error": "Se requiere OUTPUT I (pronostico) o cubo de trafico como insumo"}

    vol_extra = params["volumen_extra_pct"] / 100
    shrinkage = params["shrinkage_pct"] / 100
    ausentismo = params["ausentismo_pct"] / 100
    rotacion = params["rotacion_pct"] / 100
    capacitacion = params["capacitacion_pct"] / 100
    reductor_total = shrinkage + ausentismo + rotacion + capacitacion

    intervalos_plan = []
    for base in intervalos_base:
        llamadas_plan = base["llamadas_forecast"] * (1 + vol_extra)
        tmo_plan = base.get("tmo_forecast", 360)
        ec = _erlang_c_calc(llamadas_plan, tmo_plan)
        rac_con_reductores = math.ceil(ec["agentes_req"] / (1 - reductor_total))
        intervalos_plan.append({
            "intervalo": base["intervalo"],
            "llamadas_plan": round(llamadas_plan, 1),
            "tmo_plan": round(tmo_plan, 1),
            "rac_requerido_base": ec["agentes_req"],
            "rac_planificado_disponible": rac_con_reductores,
            "reductores_aplicados_pct": round(reductor_total * 100, 1),
            "nds_proyectado": ec["nivel_servicio"],
        })

    total_plan = sum(i["rac_planificado_disponible"] for i in intervalos_plan)
    return {
        "tipo_analisis": "planificacion_proveedor",
        "output": "OUTPUT_II",
        "descripcion": "Rac Planificado Disponible (Erlang + 10% + reductores)",
        "parametros_reductores": params,
        "intervalos": intervalos_plan,
        "resumen": {
            "total_intervalos": len(intervalos_plan),
            "rac_planificado_total": total_plan,
            "rac_planificado_promedio": round(total_plan / len(intervalos_plan), 1),
        },
    }


def run_programacion_turnos(file_bytes: bytes | None, filename: str,
                            texto: str = "",
                            resultados_previos: list[dict] | None = None) -> dict:
    """OUTPUTs III/IV/V: Programado Logueado, -Break, Disponible."""
    import math

    # Parametros TNP por defecto (minutos por turno de 8h)
    params = {"break_min": 45, "coach_min": 15, "capacitacion_min": 10,
              "dotacion_real": None}
    if texto:
        try:
            user_params = json.loads(texto)
            params.update(user_params)
        except json.JSONDecodeError:
            pass

    intervalos_plan = []

    # Usar OUTPUT II previo o archivo de malla
    if resultados_previos:
        for r in resultados_previos:
            data = r.get("resultado", {})
            if isinstance(data, dict) and data.get("output") == "OUTPUT_II":
                intervalos_plan = data.get("intervalos", [])
                break

    if not intervalos_plan and file_bytes:
        df = _load_dataframe(file_bytes, filename)
        cols_lower = {c.lower(): c for c in df.columns}
        plan_col = intervalo_col = None
        for kw in ["planificado", "programado", "dotacion", "agentes", "headcount"]:
            for cl, co in cols_lower.items():
                if kw in cl and df[co].dtype in ["float64", "int64"]:
                    plan_col = co
                    break
            if plan_col:
                break
        for kw in ["intervalo", "interval", "hora", "time"]:
            for cl, co in cols_lower.items():
                if kw in cl:
                    intervalo_col = co
                    break
            if intervalo_col:
                break

        if plan_col:
            for _, row in df.iterrows():
                agentes = int(row[plan_col]) if pd.notna(row[plan_col]) else 0
                intervalo = str(row[intervalo_col]) if intervalo_col and pd.notna(row[intervalo_col]) else "N/A"
                intervalos_plan.append({
                    "intervalo": intervalo,
                    "rac_planificado_disponible": agentes,
                })

    if not intervalos_plan:
        return {"error": "Se requiere OUTPUT II (planificacion) o malla de turnos"}

    tnp_total_min = params["break_min"] + params["coach_min"] + params["capacitacion_min"]
    # Factor TNP: proporcion del turno dedicada a TNPs (base 480 min = 8h)
    factor_tnp = tnp_total_min / 480

    intervalos_prog = []
    for plan in intervalos_plan:
        rac_plan = plan.get("rac_planificado_disponible", plan.get("rac_requerido_base", 0))
        dotacion = params["dotacion_real"] if params["dotacion_real"] else rac_plan

        # OUTPUT III: Rac Programado Logueado (agentes citados en horario)
        output_iii = dotacion
        # OUTPUT IV: Programado Logueado - Break Programado
        breaks_simultaneos = max(1, math.ceil(dotacion * (params["break_min"] / 480)))
        output_iv = dotacion - breaks_simultaneos
        # OUTPUT V: Rac Programado Disponible (sin ningún TNP)
        tnp_simultaneos = max(1, math.ceil(dotacion * factor_tnp))
        output_v = dotacion - tnp_simultaneos

        intervalos_prog.append({
            "intervalo": plan.get("intervalo", "N/A"),
            "rac_planificado": rac_plan,
            "output_iii_programado_logueado": output_iii,
            "output_iv_logueado_menos_break": output_iv,
            "output_v_programado_disponible": output_v,
            "breaks_simultaneos": breaks_simultaneos,
            "tnp_simultaneos": tnp_simultaneos,
        })

    return {
        "tipo_analisis": "programacion_turnos",
        "output": "OUTPUT_III_IV_V",
        "descripcion": "Rac Programado Logueado (III), -Break (IV), Disponible (V)",
        "parametros_tnp": {
            "break_min": params["break_min"],
            "coach_min": params["coach_min"],
            "capacitacion_min": params["capacitacion_min"],
            "tnp_total_min": tnp_total_min,
            "factor_tnp": round(factor_tnp, 3),
        },
        "intervalos": intervalos_prog,
        "resumen": {
            "total_intervalos": len(intervalos_prog),
            "promedio_logueado": round(sum(i["output_iii_programado_logueado"] for i in intervalos_prog) / len(intervalos_prog), 1),
            "promedio_disponible": round(sum(i["output_v_programado_disponible"] for i in intervalos_prog) / len(intervalos_prog), 1),
        },
    }


def run_analisis_gtr(file_bytes: bytes | None, filename: str,
                     texto: str = "",
                     resultados_previos: list[dict] | None = None) -> dict:
    """Analisis GTR: Real vs Planificado con desviaciones."""

    datos_gtr = []
    datos_plan = []

    # Cargar datos GTR de archivo
    if file_bytes:
        df = _load_dataframe(file_bytes, filename)
        cols_lower = {c.lower(): c for c in df.columns}

        log_real_col = disp_real_col = atend_col = tmo_real_col = intervalo_col = None
        for kw in ["logueado", "logged", "login"]:
            for cl, co in cols_lower.items():
                if kw in cl and "real" in cl and df[co].dtype in ["float64", "int64"]:
                    log_real_col = co
                    break
            if log_real_col:
                break
        for kw in ["disponible", "available", "avail"]:
            for cl, co in cols_lower.items():
                if kw in cl and "real" in cl and df[co].dtype in ["float64", "int64"]:
                    disp_real_col = co
                    break
            if disp_real_col:
                break
        for kw in ["atendidas", "answered", "handled"]:
            for cl, co in cols_lower.items():
                if kw in cl and df[co].dtype in ["float64", "int64"]:
                    atend_col = co
                    break
            if atend_col:
                break
        for kw in ["tmo", "aht"]:
            for cl, co in cols_lower.items():
                if kw in cl and "real" in cl and df[co].dtype in ["float64", "int64"]:
                    tmo_real_col = co
                    break
            if tmo_real_col:
                break
        for kw in ["intervalo", "interval", "hora", "time"]:
            for cl, co in cols_lower.items():
                if kw in cl:
                    intervalo_col = co
                    break
            if intervalo_col:
                break

        if log_real_col or disp_real_col or atend_col:
            for _, row in df.iterrows():
                intervalo = str(row[intervalo_col]) if intervalo_col and pd.notna(row[intervalo_col]) else "N/A"
                gtr_row = {"intervalo": intervalo}
                if log_real_col and pd.notna(row[log_real_col]):
                    gtr_row["logueados_real"] = int(row[log_real_col])
                if disp_real_col and pd.notna(row[disp_real_col]):
                    gtr_row["disponibles_real"] = int(row[disp_real_col])
                if atend_col and pd.notna(row[atend_col]):
                    gtr_row["atendidas_real"] = int(row[atend_col])
                if tmo_real_col and pd.notna(row[tmo_real_col]):
                    gtr_row["tmo_real"] = float(row[tmo_real_col])
                datos_gtr.append(gtr_row)

    # Cargar datos de resultados previos (GTR de CORTEX y programacion de NEXUS)
    if resultados_previos:
        for r in resultados_previos:
            data = r.get("resultado", {})
            if isinstance(data, dict):
                if data.get("output") in ("OUTPUT_III_IV_V",):
                    datos_plan = data.get("intervalos", [])
                elif data.get("tipo_analisis") == "ingesta_gtr":
                    # Datos GTR de CORTEX
                    if "muestra" in data:
                        for row in data["muestra"][:50]:
                            gtr_row = {"intervalo": str(row.get("intervalo", "N/A"))}
                            for k in ["logueados_real", "disponibles_real", "atendidas_real", "tmo_real"]:
                                if k in row:
                                    gtr_row[k] = row[k]
                            datos_gtr.append(gtr_row)

    if not datos_gtr:
        return {"error": "Se requieren datos GTR reales (archivo o resultado de CORTEX)"}

    # Comparar real vs plan
    comparativo = []
    for i, gtr in enumerate(datos_gtr):
        comp = {"intervalo": gtr["intervalo"]}
        comp["logueados_real"] = gtr.get("logueados_real", 0)
        comp["disponibles_real"] = gtr.get("disponibles_real", 0)
        comp["atendidas_real"] = gtr.get("atendidas_real", 0)
        comp["tmo_real"] = gtr.get("tmo_real", 0)

        # Si hay plan correspondiente
        if i < len(datos_plan):
            plan = datos_plan[i]
            comp["logueados_plan"] = plan.get("output_iii_programado_logueado", 0)
            comp["disponibles_plan"] = plan.get("output_v_programado_disponible", 0)
            if comp["logueados_plan"] > 0:
                comp["desviacion_logueados_pct"] = round(
                    ((comp["logueados_real"] - comp["logueados_plan"]) / comp["logueados_plan"]) * 100, 1)
            if comp["disponibles_plan"] > 0:
                comp["desviacion_disponibles_pct"] = round(
                    ((comp["disponibles_real"] - comp["disponibles_plan"]) / comp["disponibles_plan"]) * 100, 1)

        # Erlang con datos reales
        if comp["atendidas_real"] > 0 and comp["tmo_real"] > 0:
            ec_real = _erlang_c_calc(comp["atendidas_real"], comp["tmo_real"])
            comp["rac_requerido_real"] = ec_real["agentes_req"]

        # Alertas
        alertas = []
        if comp.get("desviacion_logueados_pct", 0) < -10:
            alertas.append("DEFICIT: logueados reales muy por debajo del plan")
        if comp.get("desviacion_disponibles_pct", 0) < -15:
            alertas.append("CRITICO: disponibles reales muy por debajo del plan")
        comp["alertas"] = alertas

        comparativo.append(comp)

    alertas_totales = sum(len(c["alertas"]) for c in comparativo)
    return {
        "tipo_analisis": "analisis_gtr",
        "descripcion": "Comparativo GTR Real vs Programacion Planificada",
        "comparativo": comparativo,
        "resumen": {
            "total_intervalos": len(comparativo),
            "total_alertas": alertas_totales,
            "promedio_logueados_real": round(sum(c["logueados_real"] for c in comparativo) / len(comparativo), 1),
            "promedio_disponibles_real": round(sum(c["disponibles_real"] for c in comparativo) / len(comparativo), 1),
        },
    }


def run_calcular_cop_cor(file_bytes: bytes | None, filename: str,
                         texto: str = "",
                         resultados_previos: list[dict] | None = None) -> dict:
    """OUTPUT VI: COP (Capacidad Operativa Planificada) y COR (Capacidad Operativa Real)."""

    intervalos_plan = []
    intervalos_gtr = []

    # Recolectar datos de resultados previos
    if resultados_previos:
        for r in resultados_previos:
            data = r.get("resultado", {})
            if isinstance(data, dict):
                if data.get("output") == "OUTPUT_I":
                    intervalos_plan = data.get("intervalos", [])
                elif data.get("output") == "OUTPUT_II":
                    intervalos_plan = data.get("intervalos", [])
                elif data.get("tipo_analisis") == "analisis_gtr":
                    intervalos_gtr = data.get("comparativo", [])
                elif data.get("tipo_analisis") == "ingesta_gtr":
                    if "muestra" in data:
                        for row in data["muestra"][:50]:
                            intervalos_gtr.append({
                                "atendidas_real": row.get("atendidas_real", 0),
                                "tmo_real": row.get("tmo_real", 0),
                                "intervalo": str(row.get("intervalo", "N/A")),
                            })

    # Archivo directo con datos reales
    if not intervalos_gtr and file_bytes:
        df = _load_dataframe(file_bytes, filename)
        cols_lower = {c.lower(): c for c in df.columns}
        atend_col = tmo_col = avail_col = intervalo_col = None
        for kw in ["atendidas", "answered", "handled"]:
            for cl, co in cols_lower.items():
                if kw in cl and df[co].dtype in ["float64", "int64"]:
                    atend_col = co
                    break
            if atend_col:
                break
        for kw in ["tmo", "aht"]:
            for cl, co in cols_lower.items():
                if kw in cl and df[co].dtype in ["float64", "int64"]:
                    tmo_col = co
                    break
            if tmo_col:
                break
        for kw in ["avail", "disponib"]:
            for cl, co in cols_lower.items():
                if kw in cl and df[co].dtype in ["float64", "int64"]:
                    avail_col = co
                    break
            if avail_col:
                break
        for kw in ["intervalo", "interval", "hora", "time"]:
            for cl, co in cols_lower.items():
                if kw in cl:
                    intervalo_col = co
                    break
            if intervalo_col:
                break

        if atend_col:
            for _, row in df.iterrows():
                intervalo = str(row[intervalo_col]) if intervalo_col and pd.notna(row[intervalo_col]) else "N/A"
                gtr_row = {"intervalo": intervalo, "atendidas_real": 0, "tmo_real": 0}
                if pd.notna(row[atend_col]):
                    gtr_row["atendidas_real"] = float(row[atend_col])
                if tmo_col and pd.notna(row[tmo_col]):
                    gtr_row["tmo_real"] = float(row[tmo_col])
                if avail_col and pd.notna(row[avail_col]):
                    gtr_row["avail_tiempo"] = float(row[avail_col])
                intervalos_gtr.append(gtr_row)

    if not intervalos_plan and not intervalos_gtr:
        return {"error": "Se requieren datos de pronostico (OUTPUT I/II) y/o datos GTR reales"}

    # Calcular COP y COR por intervalo
    resultados = []
    max_len = max(len(intervalos_plan), len(intervalos_gtr))
    for i in range(max_len):
        row = {"intervalo": "N/A"}

        # COP: Erlang aplicado al pronostico
        cop = 0
        if i < len(intervalos_plan):
            plan = intervalos_plan[i]
            row["intervalo"] = plan.get("intervalo", "N/A")
            llamadas_plan = plan.get("llamadas_forecast", plan.get("llamadas_plan", 0))
            tmo_plan = plan.get("tmo_forecast", plan.get("tmo_plan", 360))
            if llamadas_plan > 0:
                ec = _erlang_c_calc(llamadas_plan, tmo_plan)
                cop = ec["agentes_req"]
            row["cop_agentes"] = cop
            row["llamadas_plan"] = round(llamadas_plan, 1)
            row["tmo_plan"] = round(tmo_plan, 1)

        # COR: Atendidas Real x TMO + Avail
        cor = 0
        if i < len(intervalos_gtr):
            gtr = intervalos_gtr[i]
            if row["intervalo"] == "N/A":
                row["intervalo"] = gtr.get("intervalo", "N/A")
            atendidas = gtr.get("atendidas_real", 0)
            tmo_real = gtr.get("tmo_real", 0)
            avail = gtr.get("avail_tiempo", 0)
            # COR en horas-agente: (atendidas * tmo_real / 3600) + (avail / 3600)
            cor_horas = (atendidas * tmo_real / 3600) + (avail / 3600)
            cor = round(cor_horas, 2)
            row["cor_horas_agente"] = cor
            row["atendidas_real"] = round(atendidas, 1)
            row["tmo_real"] = round(tmo_real, 1)
            row["avail_tiempo"] = round(avail, 1)

        # Diferencia y eficiencia
        if cop > 0 and cor > 0:
            row["diferencia_cop_cor"] = round(cop - cor, 2)
            row["eficiencia_pct"] = round((cor / cop) * 100, 1)

        resultados.append(row)

    cop_total = sum(r.get("cop_agentes", 0) for r in resultados)
    cor_total = sum(r.get("cor_horas_agente", 0) for r in resultados)
    return {
        "tipo_analisis": "cop_cor",
        "output": "OUTPUT_VI",
        "descripcion": "COP (Capacidad Operativa Planificada) y COR (Capacidad Operativa Real)",
        "intervalos": resultados,
        "resumen": {
            "total_intervalos": len(resultados),
            "cop_total": cop_total,
            "cor_total": round(cor_total, 2),
            "eficiencia_global_pct": round((cor_total / cop_total) * 100, 1) if cop_total > 0 else 0,
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

    resumen = json.dumps(datos, ensure_ascii=False, default=str, cls=_SafeEncoder)[:8000]
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

{contenido[:6000]}

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

Volumetria: {json.dumps(datos_volumen, ensure_ascii=False, default=str, cls=_SafeEncoder)[:6000]}

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

KPIs alcanzados: {json.dumps(kpis, ensure_ascii=False, default=str, cls=_SafeEncoder)[:6000]}

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

KPIs del periodo: {json.dumps(kpis, ensure_ascii=False, default=str, cls=_SafeEncoder)[:6000]}

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

# Limite de caracteres para insumos en prompts de ATLAS.
# Valor anterior era 4000 que causaba perdida de datos silenciosa.
_ATLAS_INSUMOS_LIMIT = 16000


def _smart_truncate_insumos(insumos, max_chars: int = _ATLAS_INSUMOS_LIMIT) -> str:
    """Serializa insumos con truncacion inteligente que preserva datos clave.

    En lugar de truncar el JSON completo (perdiendo insumos enteros),
    reduce los datos de cada insumo progresivamente si excede el limite.
    """
    full = json.dumps(insumos, ensure_ascii=False, default=str, cls=_SafeEncoder)
    if len(full) <= max_chars:
        return full

    # Fase 1: Eliminar muestra de datos (lo mas pesado y menos util para LLM)
    trimmed = []
    for ins in insumos:
        ins_copy = dict(ins)
        datos = ins_copy.get("datos", {})
        if isinstance(datos, dict):
            datos_copy = dict(datos)
            datos_copy.pop("muestra", None)
            datos_copy.pop("muestra_verbatims", None)
            # Reducir estadisticas a solo promedio si existen
            stats = datos_copy.get("estadisticas", {})
            if isinstance(stats, dict) and len(stats) > 10:
                datos_copy["estadisticas"] = {
                    k: {"promedio": v.get("promedio"), "total": v.get("total")}
                    for k, v in list(stats.items())[:15]
                }
            ins_copy["datos"] = datos_copy
        trimmed.append(ins_copy)

    result = json.dumps(trimmed, ensure_ascii=False, default=str, cls=_SafeEncoder)
    if len(result) <= max_chars:
        return result

    # Fase 2: Truncar con indicador
    return result[:max_chars - 50] + '\n... [DATOS TRUNCADOS - usar resultados originales para detalle]'


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
{_smart_truncate_insumos(insumos)}

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
    return _llm_analyze(prompt, temperature=0.3, max_tokens=4000)


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
{_smart_truncate_insumos(insumos)}

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
    return _llm_analyze(prompt, temperature=0.3, max_tokens=4000)


def run_analisis_cruzado(file_bytes: bytes | None, filename: str,
                          texto: str = "",
                          resultados_previos: list[dict] | None = None) -> dict:
    insumos = _build_atlas_insumos(file_bytes, filename, resultados_previos)

    if len(insumos) < 2:
        return {"error": "Se necesitan al menos 2 fuentes para analisis cruzado"}

    prompt = f"""Analiza estos datos de multiples fuentes de call center y genera correlaciones.

{_ATLAS_SOURCE_INSTRUCTIONS}

Datos con trazabilidad de origen:
{_smart_truncate_insumos(insumos)}

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
    return _llm_analyze(prompt, temperature=0.2, max_tokens=4000)


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
{_smart_truncate_insumos(list(modules.values()), _ATLAS_INSUMOS_LIMIT)}

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
    return _llm_analyze(prompt, temperature=0.3, max_tokens=4000)


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
{_smart_truncate_insumos(insumos)}

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
    return _llm_analyze(prompt, temperature=0.3, max_tokens=4000)


# ══════════════════════════════════════════════════════════════════════
#  VISUALIZAR DATOS - Compartido por todos los agentes
# ══════════════════════════════════════════════════════════════════════


def run_visualizar_datos(file_bytes: bytes | None, filename: str,
                         resultados_previos: list[dict] | None = None) -> dict:
    """Genera graficos interactivos a partir de datos o resultados previos.

    Retorna un dict con metadatos; los graficos (figuras Plotly) se almacenan
    en ``st.session_state`` para ser renderizados por la UI.
    """
    from chart_builder import auto_charts_from_result, auto_charts_from_dataframe

    all_figures = []

    # 1. Si hay archivo, generar graficos del DataFrame
    if file_bytes:
        df = _load_dataframe(file_bytes, filename)
        figs = auto_charts_from_dataframe(df, f"{filename}: ")
        all_figures.extend(figs)

    # 2. Si hay resultados previos, generar graficos de cada uno
    if resultados_previos:
        for r in resultados_previos:
            data = r.get("resultado", {})
            if isinstance(data, dict):
                agent = r.get("agent_name", "")
                figs = auto_charts_from_result(data, agent)
                all_figures.extend(figs)

    if not all_figures:
        return {"error": "No se pudieron generar graficos. Verifique que los datos tengan columnas numericas."}

    # Guardar figuras en variable global para que la UI las renderice
    # (las figuras Plotly no son serializables a JSON)
    global _last_chart_figures
    _last_chart_figures = all_figures

    return {
        "tipo_analisis": "visualizacion",
        "total_graficos": len(all_figures),
        "graficos_generados": [
            fig.layout.title.text if fig.layout.title and fig.layout.title.text else f"Grafico {i+1}"
            for i, fig in enumerate(all_figures)
        ],
        "exportable_pdf": True,
    }


# Variable global para pasar figuras Plotly a la UI
_last_chart_figures: list = []


def get_last_chart_figures() -> list:
    """Retorna las ultimas figuras generadas por visualizar_datos."""
    return _last_chart_figures


# ══════════════════════════════════════════════════════════════════════
#  Dispatcher principal
# ══════════════════════════════════════════════════════════════════════


SKILL_RUNNERS = {
    # CORTEX
    "ingesta_acd": run_ingesta_acd,
    "ingesta_qa": run_ingesta_qa,
    "ingesta_cx": run_ingesta_cx,
    "ingesta_cubo_trafico": run_ingesta_cubo_trafico,
    "ingesta_malla": run_ingesta_malla,
    "ingesta_gtr": run_ingesta_gtr,
    "validar_fuentes": run_validar_fuentes,
    "transcribir_audio": run_transcribir_audio,
    "generar_dialogo": run_generar_dialogo,
    # NEXUS - WFM Ciclo Completo
    "pronostico_erlang": run_pronostico_erlang,
    "planificacion_proveedor": run_planificacion_proveedor,
    "programacion_turnos": run_programacion_turnos,
    "analisis_gtr": run_analisis_gtr,
    "calcular_cop_cor": run_calcular_cop_cor,
    "ingesta_wfm": run_ingesta_wfm,
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
    # COMPARTIDO
    "visualizar_datos": run_visualizar_datos,
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
        elif skill_id in ("ingesta_acd", "ingesta_qa", "ingesta_cx",
                           "ingesta_cubo_trafico", "ingesta_malla", "ingesta_gtr"):
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
        elif skill_id == "ingesta_wfm":
            if not file_bytes:
                return {"error": "Se requiere un archivo de datos"}
            result = runner(file_bytes, filename, texto)

        elif skill_id in ("calcular_carga_trabajo", "calcular_tmo"):
            result = runner(file_bytes, filename, resultado_previo)

        elif skill_id == "calcular_staffing":
            result = runner(file_bytes, filename, texto, resultados_multiples)

        # ── NEXUS: WFM Ciclo Completo ──
        elif skill_id in ("pronostico_erlang", "planificacion_proveedor",
                           "programacion_turnos", "analisis_gtr", "calcular_cop_cor"):
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

        # ── COMPARTIDO: Visualizar ──
        elif skill_id == "visualizar_datos":
            result = runner(file_bytes, filename, resultados_multiples)

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
