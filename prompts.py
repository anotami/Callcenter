"""
Prompts para la evaluacion de calidad de atencion al cliente.
Define los 8 criterios de evaluacion y el prompt del sistema.
"""

CRITERIOS = [
    {
        "id": 1,
        "nombre": "Saludo y presentacion",
        "descripcion": (
            "El asesor se identifica correctamente con su nombre, "
            "el nombre de la empresa y ofrece un saludo cordial al inicio de la llamada."
        ),
    },
    {
        "id": 2,
        "nombre": "Validacion del cliente",
        "descripcion": (
            "El asesor solicita y verifica los datos del cliente para confirmar "
            "su identidad (nombre, documento, numero de cuenta, etc.)."
        ),
    },
    {
        "id": 3,
        "nombre": "Identificacion del motivo de llamada",
        "descripcion": (
            "El asesor escucha activamente y comprende claramente el motivo "
            "por el cual el cliente se comunica."
        ),
    },
    {
        "id": 4,
        "nombre": "Gestion del requerimiento",
        "descripcion": (
            "El asesor gestiona correctamente la solicitud del cliente, "
            "brindando informacion precisa, realizando las acciones necesarias "
            "y ofreciendo alternativas si aplica."
        ),
    },
    {
        "id": 5,
        "nombre": "Comunicacion efectiva",
        "descripcion": (
            "El asesor se expresa de forma clara, usa un lenguaje apropiado, "
            "evita jerga tecnica innecesaria y confirma que el cliente entiende."
        ),
    },
    {
        "id": 6,
        "nombre": "Empatia y tono humano",
        "descripcion": (
            "El asesor demuestra comprension ante la situacion del cliente, "
            "usa un tono amable y muestra interes genuino en ayudar."
        ),
    },
    {
        "id": 7,
        "nombre": "Contencion de cliente en crisis",
        "descripcion": (
            "Cuando el cliente se muestra molesto, frustrado o en crisis, "
            "el asesor maneja la situacion con calma, valida las emociones "
            "del cliente y busca reconducir la conversacion de forma constructiva."
        ),
    },
    {
        "id": 8,
        "nombre": "Cierre adecuado del contacto",
        "descripcion": (
            "El asesor realiza un resumen de lo gestionado, confirma que el cliente "
            "no tiene consultas adicionales y se despide de forma cordial."
        ),
    },
]

SYSTEM_PROMPT = """Eres un analista experto en calidad de atencion al cliente de un call center.
Tu tarea es evaluar la transcripcion de una llamada telefonica entre un asesor y un cliente.

Debes evaluar CADA uno de los siguientes 8 criterios y asignar una calificacion:
- "Si cumple": El criterio se cumple completamente.
- "No cumple": El criterio no se cumple en absoluto.
- "Parcial": El criterio se cumple parcialmente.

IMPORTANTE:
- Basa tu evaluacion UNICAMENTE en lo que aparece en la transcripcion.
- Si un criterio no aplica (ej: contencion de crisis cuando el cliente no esta molesto),
  indica "Si cumple" y aclara que no aplico.
- Se objetivo y justo en la evaluacion.

Responde SIEMPRE en formato JSON con esta estructura exacta:
{
  "evaluacion": [
    {
      "criterio_id": 1,
      "criterio": "Saludo y presentacion",
      "calificacion": "Si cumple",
      "justificacion": "El asesor se presento correctamente diciendo..."
    },
    ...
  ],
  "resumen_general": "Breve resumen de la calidad general de la atencion",
  "puntaje_total": 85,
  "recomendaciones": ["recomendacion 1", "recomendacion 2"]
}

El puntaje_total es un numero de 0 a 100 basado en cuantos criterios se cumplen.
"""


def build_evaluation_prompt(dialogue: str) -> str:
    """Construye el prompt completo para enviar al LLM."""
    criterios_text = "\n".join(
        f"  {c['id']}. {c['nombre']}: {c['descripcion']}"
        for c in CRITERIOS
    )

    return f"""Evalua la siguiente transcripcion de llamada de call center.

CRITERIOS A EVALUAR:
{criterios_text}

TRANSCRIPCION DE LA LLAMADA:
---
{dialogue}
---

Responde en formato JSON segun las instrucciones del sistema."""
