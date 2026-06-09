"""
Proceso 1: Transcripcion de audio a texto usando faster-whisper.
faster-whisper es ~4x mas rapido que el whisper original de OpenAI
y consume menos memoria GPU/RAM.
"""

import logging

logger = logging.getLogger("callcenter.transcriber")

from config import WHISPER_MODEL, WHISPER_DEVICE, WHISPER_LANGUAGE


def _get_whisper_model_class():
    """Importa WhisperModel de forma lazy para evitar cache de importacion fallida."""
    try:
        from faster_whisper import WhisperModel
        return WhisperModel
    except ImportError:
        return None


def load_whisper_model():
    """Carga el modelo faster-whisper. Se recomienda llamar una sola vez."""
    WhisperModel = _get_whisper_model_class()
    if WhisperModel is None:
        raise ImportError(
            "faster_whisper no esta instalado. "
            "Instala con: pip install faster-whisper"
        )
    compute_type = "float16" if WHISPER_DEVICE == "cuda" else "int8"
    model = WhisperModel(
        WHISPER_MODEL,
        device=WHISPER_DEVICE,
        compute_type=compute_type,
    )
    logger.info("Modelo '%s' cargado en %s", WHISPER_MODEL, WHISPER_DEVICE)
    return model


def transcribe(model, audio_path: str) -> list[dict]:
    """
    Transcribe un archivo de audio y devuelve segmentos con timestamps.

    Retorna lista de dicts:
        [{"start": 0.0, "end": 2.5, "text": "Hola buenos dias..."}, ...]
    Retorna lista vacia si hay un error de transcripcion.
    """
    if _get_whisper_model_class() is None:
        logger.error("faster_whisper no esta instalado. No se puede transcribir.")
        return []

    try:
        segments, info = model.transcribe(
            audio_path,
            language=WHISPER_LANGUAGE,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        logger.info(
            "Idioma detectado: %s (probabilidad: %.2f)",
            info.language,
            info.language_probability,
        )

        results = []
        for seg in segments:
            results.append({
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": seg.text.strip(),
            })

        logger.info("%d segmentos transcritos", len(results))
        return results

    except Exception as e:
        logger.error("Error al transcribir '%s': %s", audio_path, e)
        return []
