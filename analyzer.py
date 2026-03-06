"""
Proceso 3: Analisis de calidad de atencion usando LLM local.
Se conecta a LM Studio u Ollama via API compatible con OpenAI.
"""

import json
import re
import time
import logging
from openai import OpenAI
from config import LLM_BASE_URL, LLM_MODEL
from prompts import SYSTEM_PROMPT, build_evaluation_prompt

logger = logging.getLogger("callcenter.analyzer")

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2


def create_llm_client() -> OpenAI:
    """
    Crea cliente para LM Studio u Ollama.
    Ambos exponen una API compatible con el formato OpenAI.
    - LM Studio: puerto 1234 por defecto
    - Ollama: puerto 11434, URL = http://localhost:11434/v1
    """
    client = OpenAI(
        base_url=LLM_BASE_URL,
        api_key="not-needed",
    )
    logger.info("Cliente creado -> %s (modelo: %s)", LLM_BASE_URL, LLM_MODEL)
    return client


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


def analyze_call(client: OpenAI, dialogue: str) -> dict:
    """
    Envia el dialogo transcrito al LLM para evaluacion de calidad.
    Reintenta hasta MAX_RETRIES veces si la llamada falla.

    Args:
        client: Cliente OpenAI apuntando a LM Studio/Ollama
        dialogue: Texto del dialogo formateado (Asesor: ... / Cliente: ...)

    Returns:
        dict con la evaluacion estructurada
    """
    user_prompt = build_evaluation_prompt(dialogue)

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=2000,
            )

            raw_response = response.choices[0].message.content
            logger.info("Respuesta recibida (%d caracteres)", len(raw_response))

            result = _extract_json(raw_response)
            if result is not None:
                return result

            logger.warning("No se encontro JSON valido en la respuesta del LLM")
            return {"raw_response": raw_response, "parse_error": "No JSON found"}

        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                wait = RETRY_DELAY_SECONDS * attempt
                logger.warning(
                    "Error en intento %d/%d: %s. Reintentando en %ds...",
                    attempt, MAX_RETRIES, e, wait,
                )
                time.sleep(wait)
            else:
                logger.error("Fallo tras %d intentos: %s", MAX_RETRIES, e)

    return {"raw_response": "", "parse_error": str(last_error)}


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
