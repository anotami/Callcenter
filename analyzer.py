"""
Proceso 3: Analisis de calidad de atencion usando LLM.
Compatible con Groq, LM Studio, Ollama, o cualquier API OpenAI-compatible.
Incluye fallback automatico entre multiples modelos.
"""

import hashlib
import json
import re
import time
import logging
from openai import OpenAI
import config as _cfg
from config import (
    LLM_FALLBACK_MODELS, LLM_MAX_RETRIES,
    GROQ_API_KEY, GROQ_BASE_URL, GROQ_FALLBACK_MODELS,
)
from prompts import SYSTEM_PROMPT, build_evaluation_prompt

logger = logging.getLogger("callcenter.analyzer")

RETRY_DELAY_SECONDS = 2

# ── Cache de respuestas LLM ──────────────────────────────────────────────
# Cache en memoria con TTL de 1 hora (key=hash de messages, value=(response, model, timestamp))
_llm_cache: dict[str, tuple[str, str, float]] = {}
_CACHE_TTL_SECONDS = 3600  # 1 hora
_CACHE_MAX_SIZE = 100


def _cache_key(messages: list[dict], temperature: float) -> str:
    """Genera una key de cache basada en el contenido del prompt."""
    content = json.dumps(messages, ensure_ascii=False, sort_keys=True) + f"|t={temperature}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _cache_get(key: str) -> tuple[str, str] | None:
    """Busca en cache. Retorna (response, model) o None si no existe/expirado."""
    entry = _llm_cache.get(key)
    if entry is None:
        return None
    response, model, ts = entry
    if time.time() - ts > _CACHE_TTL_SECONDS:
        del _llm_cache[key]
        return None
    logger.info("Cache HIT para key %s", key)
    return response, model


def _cache_set(key: str, response: str, model: str):
    """Guarda respuesta en cache."""
    # Evitar crecimiento ilimitado
    if len(_llm_cache) >= _CACHE_MAX_SIZE:
        # Eliminar la entrada mas antigua
        oldest_key = min(_llm_cache, key=lambda k: _llm_cache[k][2])
        del _llm_cache[oldest_key]
    _llm_cache[key] = (response, model, time.time())


def create_llm_client(base_url: str | None = None,
                      api_key: str | None = None) -> OpenAI:
    """Crea cliente OpenAI apuntando a Groq, LM Studio, Ollama, etc."""
    base_url = base_url or _cfg.LLM_BASE_URL
    api_key = api_key or _cfg.LLM_API_KEY
    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
    )
    logger.info("Cliente creado -> %s", base_url)
    return client


def _get_model_queue() -> list[tuple[str, str, str]]:
    """
    Construye la lista ordenada de (modelo, base_url, api_key) a intentar.
    Primero modelos locales, luego Groq si tiene API key configurada.
    """
    entries: list[tuple[str, str, str]] = []

    # Modelo principal (leido en runtime para reflejar seleccion del usuario)
    entries.append((_cfg.LLM_MODEL, _cfg.LLM_BASE_URL, _cfg.LLM_API_KEY))
    for m in LLM_FALLBACK_MODELS:
        if m != _cfg.LLM_MODEL:
            entries.append((m, _cfg.LLM_BASE_URL, _cfg.LLM_API_KEY))

    # Modelos Groq (solo si hay API key)
    if GROQ_API_KEY:
        for m in GROQ_FALLBACK_MODELS:
            entries.append((m, GROQ_BASE_URL, GROQ_API_KEY))

    return entries


def _try_streamlit_progress(message: str):
    """Intenta mostrar progreso en Streamlit si esta disponible."""
    try:
        import streamlit as st
        if hasattr(st, "_is_running_with_streamlit"):
            st.toast(message)
    except Exception:
        pass


def call_llm(
    messages: list[dict],
    temperature: float = 0.1,
    max_tokens: int = 2000,
    client: OpenAI | None = None,
    status_container=None,
) -> tuple[str, str]:
    """
    Llama al LLM con fallback automatico entre modelos y proveedores.
    Intenta modelos locales primero, luego Groq si esta configurado.

    Args:
        messages: Lista de mensajes [{role, content}]
        temperature: Temperatura de generacion
        max_tokens: Tokens maximos de respuesta
        client: Cliente OpenAI (si None, usa los configurados por proveedor)
        status_container: Contenedor de Streamlit para mostrar progreso (opcional)

    Returns:
        Tupla (respuesta_texto, modelo_usado)
    """
    # Verificar cache primero
    cache_k = _cache_key(messages, temperature)
    cached = _cache_get(cache_k)
    if cached is not None:
        raw, model_used = cached
        ok_msg = f"Respuesta desde cache (modelo original: {model_used})"
        if status_container is not None:
            try:
                status_container.update(label=ok_msg, state="complete")
            except Exception:
                pass
        return raw, model_used

    model_queue = _get_model_queue()
    max_retries = min(LLM_MAX_RETRIES, max(len(model_queue), 3))

    # Cache de clientes por base_url para no recrearlos
    _clients: dict[str, OpenAI] = {}
    if client is not None:
        _clients[_cfg.LLM_BASE_URL] = client

    last_error = None
    for attempt in range(1, max_retries + 1):
        idx = (attempt - 1) % len(model_queue)
        model, base_url, api_key = model_queue[idx]

        provider = "Groq" if "groq.com" in base_url else "Local"
        progress_msg = f"Intento {attempt}/{max_retries} - {provider}: {model}"
        logger.info(progress_msg)

        if status_container is not None:
            try:
                status_container.update(label=progress_msg, state="running")
            except Exception:
                pass
        else:
            _try_streamlit_progress(progress_msg)

        # Obtener o crear cliente para este proveedor
        if base_url not in _clients:
            _clients[base_url] = create_llm_client(base_url, api_key)
        current_client = _clients[base_url]

        try:
            response = current_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            raw = response.choices[0].message.content
            logger.info("OK con modelo '%s' [%s] (%d chars)", model, provider, len(raw))

            # Guardar en cache
            _cache_set(cache_k, raw, model)

            ok_msg = f"Respuesta recibida de {model} ({provider})"
            if status_container is not None:
                try:
                    status_container.update(label=ok_msg, state="complete")
                except Exception:
                    pass
            else:
                _try_streamlit_progress(ok_msg)

            return raw, model

        except Exception as e:
            last_error = e
            err_msg = f"Intento {attempt}/{max_retries} fallo ({provider}/{model}): {e}"
            logger.warning(err_msg)

            if status_container is not None:
                try:
                    status_container.update(label=err_msg, state="error")
                except Exception:
                    pass

            if attempt < max_retries:
                next_idx = attempt % len(model_queue)
                next_model = model_queue[next_idx][0]
                wait = min(RETRY_DELAY_SECONDS * attempt, 10)
                logger.info("Esperando %ds... siguiente: %s", wait, next_model)
                time.sleep(wait)

    error_msg = f"Fallo tras {max_retries} intentos. Ultimo error: {last_error}"
    logger.error(error_msg)
    raise RuntimeError(error_msg)


def _extract_json(text: str) -> dict | None:
    """
    Extrae JSON de una respuesta LLM que puede contener texto adicional
    o bloques de codigo markdown (```json ... ```).
    Incluye reparacion basica de JSON malformado.
    """
    if not text or not text.strip():
        return None

    # Intentar bloques ```json ... ``` primero
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            # Intentar reparar JSON comun
            repaired = _repair_json(match.group(1).strip())
            if repaired:
                return repaired

    # Fallback: buscar el objeto JSON mas externo
    json_start = text.find("{")
    json_end = text.rfind("}") + 1
    if json_start != -1 and json_end > json_start:
        candidate = text[json_start:json_end]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            repaired = _repair_json(candidate)
            if repaired:
                return repaired

    return None


def _repair_json(text: str) -> dict | None:
    """Intenta reparar JSON malformado comun en respuestas LLM."""
    if not text:
        return None
    fixed = text
    # Eliminar trailing commas antes de } o ]
    fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
    # Reemplazar comillas simples por dobles (cuidando escapados)
    # solo si no hay comillas dobles ya
    if '"' not in fixed and "'" in fixed:
        fixed = fixed.replace("'", '"')
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass
    # Intentar truncar en el ultimo } valido
    for end in range(len(fixed) - 1, 0, -1):
        if fixed[end] == '}':
            try:
                return json.loads(fixed[:end + 1])
            except json.JSONDecodeError:
                continue
    return None


def analyze_call(client: OpenAI, dialogue: str,
                 status_container=None) -> dict:
    """
    Envia el dialogo transcrito al LLM para evaluacion de calidad.
    Usa fallback automatico entre modelos.
    """
    user_prompt = build_evaluation_prompt(dialogue)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        raw_response, model_used = call_llm(
            messages=messages,
            temperature=0.1,
            max_tokens=2000,
            client=client,
            status_container=status_container,
        )
    except RuntimeError as e:
        return {"raw_response": "", "parse_error": str(e)}

    result = _extract_json(raw_response)
    if result is not None:
        result["_modelo_usado"] = model_used
        return result

    logger.warning("No se encontro JSON valido en la respuesta del LLM")
    return {"raw_response": raw_response, "parse_error": "No JSON found"}


def format_evaluation_report(evaluation: dict) -> str:
    """Formatea la evaluacion como texto legible para consola/archivo."""
    if "parse_error" in evaluation:
        return f"Error parseando respuesta LLM:\n{evaluation.get('raw_response', '')}"

    lines = ["=" * 60, "REPORTE DE EVALUACION DE CALIDAD", "=" * 60, ""]

    for item in evaluation.get("evaluacion", []):
        emoji_map = {"Si cumple": "[OK]", "No cumple": "[FAIL]", "Parcial": "[PARCIAL]"}
        status = emoji_map.get(item.get("calificacion", ""), "[?]")
        lines.append(f"{status} {item['criterio_id']}. {item['criterio']}: "
                      f"{item['calificacion']}")
        lines.append(f"    -> {item.get('justificacion', 'Sin justificacion')}")
        lines.append("")

    lines.append("-" * 60)
    lines.append(f"Puntaje Total: {evaluation.get('puntaje_total', 'N/A')}/100")
    lines.append(f"Resumen: {evaluation.get('resumen_general', 'N/A')}")

    recomendaciones = evaluation.get("recomendaciones", [])
    if recomendaciones:
        lines.append("\nRecomendaciones:")
        for r in recomendaciones:
            lines.append(f"  - {r}")

    lines.append("=" * 60)
    return "\n".join(lines)
