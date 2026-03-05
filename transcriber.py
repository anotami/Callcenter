"""
Proceso 1: Transcripcion de audio a texto usando faster-whisper.
faster-whisper es ~4x mas rapido que el whisper original de OpenAI
y consume menos memoria GPU/RAM.
"""

from faster_whisper import WhisperModel
from config import WHISPER_MODEL, WHISPER_DEVICE, WHISPER_LANGUAGE


def load_whisper_model() -> WhisperModel:
    """Carga el modelo faster-whisper. Se recomienda llamar una sola vez."""
    compute_type = "float16" if WHISPER_DEVICE == "cuda" else "int8"
    model = WhisperModel(
        WHISPER_MODEL,
        device=WHISPER_DEVICE,
        compute_type=compute_type,
    )
    print(f"[Whisper] Modelo '{WHISPER_MODEL}' cargado en {WHISPER_DEVICE}")
    return model


def transcribe(model: WhisperModel, audio_path: str) -> list[dict]:
    """
    Transcribe un archivo de audio y devuelve segmentos con timestamps.

    Retorna lista de dicts:
        [{"start": 0.0, "end": 2.5, "text": "Hola buenos dias..."}, ...]
    """
    segments, info = model.transcribe(
        audio_path,
        language=WHISPER_LANGUAGE,
        beam_size=5,
        vad_filter=True,  # Filtra silencios para mayor velocidad
        vad_parameters=dict(min_silence_duration_ms=500),
    )

    print(f"[Whisper] Idioma detectado: {info.language} "
          f"(probabilidad: {info.language_probability:.2f})")

    results = []
    for seg in segments:
        results.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        })

    print(f"[Whisper] {len(results)} segmentos transcritos")
    return results
