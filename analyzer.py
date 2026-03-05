"""
Proceso 3: Analisis de calidad de atencion usando LLM local.
Se conecta a LM Studio u Ollama via API compatible con OpenAI.
"""

import json
from openai import OpenAI
from config import LLM_BASE_URL, LLM_MODEL
from prompts import SYSTEM_PROMPT, build_evaluation_prompt


def create_llm_client() -> OpenAI:
    """
    Crea cliente para LM Studio u Ollama.
    Ambos exponen una API compatible con el formato OpenAI.
    - LM Studio: puerto 1234 por defecto
    - Ollama: puerto 11434, URL = http://localhost:11434/v1
    """
    client = OpenAI(
        base_url=LLM_BASE_URL,
        api_key="not-needed",  # LM Studio/Ollama no requieren API key
    )
    print(f"[LLM] Cliente creado -> {LLM_BASE_URL} (modelo: {LLM_MODEL})")
    return client


def analyze_call(client: OpenAI, dialogue: str) -> dict:
    """
    Envia el dialogo transcrito al LLM para evaluacion de calidad.

    Args:
        client: Cliente OpenAI apuntando a LM Studio/Ollama
        dialogue: Texto del dialogo formateado (Asesor: ... / Cliente: ...)

    Returns:
        dict con la evaluacion estructurada
    """
    user_prompt = build_evaluation_prompt(dialogue)

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,  # Baja temperatura para respuestas consistentes
        max_tokens=2000,
    )

    raw_response = response.choices[0].message.content
    print(f"[LLM] Respuesta recibida ({len(raw_response)} caracteres)")

    # Intentar parsear JSON de la respuesta
    try:
        # Buscar JSON en la respuesta (puede venir con texto adicional)
        json_start = raw_response.find("{")
        json_end = raw_response.rfind("}") + 1
        if json_start != -1 and json_end > json_start:
            result = json.loads(raw_response[json_start:json_end])
        else:
            result = {"raw_response": raw_response, "parse_error": "No JSON found"}
    except json.JSONDecodeError as e:
        result = {"raw_response": raw_response, "parse_error": str(e)}

    return result


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
