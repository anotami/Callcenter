"""
Proceso 3: Analisis de calidad de atencion usando LLM.
Compatible con Groq, LM Studio, Ollama, o cualquier API OpenAI-compatible.
Incluye fallback automatico entre multiples modelos.
"""

import json
import re
import time
import logging
from openai import OpenAI
from config import (
    LLM_BASE_URL, LLM_MODEL, LLM_API_KEY,
    LLM_FALLBACK_MODELS, LLM_MAX_RETRIES,
)
from prompts import SYSTEM_PROMPT, build_evaluation_prompt

logger = logging.getLogger("callcenter.analyzer")

RETRY_DELAY_SECONDS = 2


def create_llm_client() -> OpenAI:
    """Crea cliente OpenAI apuntando a Groq, LM Studio, Ollama, etc."""
    client = OpenAI(
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
    )
    logger.info("Cliente creado -> %s", LLM_BASE_URL)
    return client


def _get_model_queue() -> list[str]:
    """Construye la lista ordenada de modelos a intentar (principal + fallbacks)."""
    models = [LLM_MODEL]
    for m in LLM_FALLBACK_MODELS:
        if m != LLM_MODEL and m not in models:
            models.append(m)
    return models


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
    Llama al LLM con fallback automatico entre modelos.
    Intenta hasta LLM_MAX_RETRIES veces rotando modelos.

    Args:
        messages: Lista de mensajes [{role, content}]
        temperature: Temperatura de generacion
        max_tokens: Tokens maximos de respuesta
        client: Cliente OpenAI (si None, crea uno nuevo)
        status_container: Contenedor de Streamlit para mostrar progreso (opcional)

    Returns:
        Tupla (respuesta_texto, modelo_usado)
    """
    if client is None:
        client = create_llm_client()

    models = _get_model_queue()
    max_retries = min(LLM_MAX_RETRIES, max(len(models), 5))

    last_error = None
    for attempt in range(1, max_retries + 1):
        model_idx = (attempt - 1) % len(models)
        model = models[model_idx]

        progress_msg = f"Intento {attempt}/{max_retries} - Modelo: {model}"
        logger.info(progress_msg)

        # Mostrar progreso en Streamlit si hay contenedor
        if status_container is not None:
            try:
                status_container.update(label=progress_msg, state="running")
            except Exception:
                pass
        else:
            _try_streamlit_progress(progress_msg)

        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            raw = response.choices[0].message.content
            logger.info("OK con modelo '%s' (%d chars)", model, len(raw))

            # Exito - mostrar en UI
            ok_msg = f"Respuesta recibida de {model}"
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
            err_msg = f"Intento {attempt}/{max_retries} fallo ({model}): {e}"
            logger.warning(err_msg)

            if status_container is not None:
                try:
                    status_container.update(label=err_msg, state="error")
                except Exception:
                    pass

            if attempt < max_retries:
                next_model = models[attempt % len(models)]
                wait = min(RETRY_DELAY_SECONDS * attempt, 10)
                logger.info("Esperando %ds... siguiente modelo: %s", wait, next_model)
                time.sleep(wait)

    error_msg = f"Fallo tras {max_retries} intentos. Ultimo error: {last_error}"
    logger.error(error_msg)
    raise RuntimeError(error_msg)


def _extract_json(text: str) -> dict | None:
    """
    Extrae JSON de una respuesta LLM que puede contener texto adicional
    o bloques de codigo markdown (```json ... ```).
    """
    # Intentar bloques ```json ... ``` primero
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Fallback: buscar el objeto JSON mas externo
    json_start = text.find("{")
    json_end = text.rfind("}") + 1
    if json_start != -1 and json_end > json_start:
        try:
            return json.loads(text[json_start:json_end])
        except json.JSONDecodeError:
            pass

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
