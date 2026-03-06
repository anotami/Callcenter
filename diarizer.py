"""
Proceso 2: Diarizacion - Identifica quien habla en cada momento.
Usa pyannote.audio para detectar y separar las intervenciones
de los diferentes hablantes (Asesor vs Cliente).
"""

from pyannote.audio import Pipeline as DiarizationPipeline
from config import HF_TOKEN, WHISPER_DEVICE


def load_diarization_model() -> DiarizationPipeline:
    """
    Carga el pipeline de diarizacion de pyannote.
    Requiere aceptar la licencia en HuggingFace y tener HF_TOKEN configurado.
    """
    if not HF_TOKEN:
        raise ValueError(
            "HF_TOKEN no configurado. Obtener en https://huggingface.co/settings/tokens "
            "y aceptar licencia en https://huggingface.co/pyannote/speaker-diarization-3.1"
        )

    pipeline = DiarizationPipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        token=HF_TOKEN,
    )

    if WHISPER_DEVICE == "cuda":
        import torch
        pipeline.to(torch.device("cuda"))

    print("[Diarizacion] Modelo pyannote cargado")
    return pipeline


def diarize(pipeline: DiarizationPipeline, audio_path: str) -> list[dict]:
    """
    Ejecuta diarizacion sobre un audio.

    Retorna lista de dicts:
        [{"start": 0.0, "end": 2.5, "speaker": "SPEAKER_00"}, ...]
    """
    diarization = pipeline(audio_path)

    segments = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        segments.append({
            "start": round(turn.start, 2),
            "end": round(turn.end, 2),
            "speaker": speaker,
        })

    print(f"[Diarizacion] {len(segments)} segmentos, "
          f"hablantes detectados: {len(set(s['speaker'] for s in segments))}")
    return segments


def merge_transcription_diarization(
    transcription: list[dict],
    diarization: list[dict],
) -> list[dict]:
    """
    Combina la transcripcion (texto + timestamps) con la diarizacion (hablante + timestamps)
    para generar un dialogo estructurado con quien dice que.

    Asigna cada segmento de transcripcion al hablante que mas se solapa temporalmente.
    """
    merged = []

    for t_seg in transcription:
        t_start, t_end = t_seg["start"], t_seg["end"]
        best_speaker = "DESCONOCIDO"
        best_overlap = 0.0

        for d_seg in diarization:
            # Calcular solapamiento temporal
            overlap_start = max(t_start, d_seg["start"])
            overlap_end = min(t_end, d_seg["end"])
            overlap = max(0.0, overlap_end - overlap_start)

            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = d_seg["speaker"]

        merged.append({
            "start": t_start,
            "end": t_end,
            "speaker": best_speaker,
            "text": t_seg["text"],
        })

    return merged


def format_dialogue(merged_segments: list[dict]) -> str:
    """
    Convierte los segmentos combinados en un dialogo legible.
    El primer hablante se asume como Asesor (quien inicia la llamada).
    """
    if not merged_segments:
        return ""

    # Mapear speakers a roles (el primero que habla = Asesor)
    speaker_map = {}
    role_names = ["Asesor", "Cliente", "Hablante_3", "Hablante_4"]
    role_idx = 0

    lines = []
    for seg in merged_segments:
        speaker = seg["speaker"]
        if speaker not in speaker_map:
            speaker_map[speaker] = role_names[min(role_idx, len(role_names) - 1)]
            role_idx += 1

        role = speaker_map[speaker]
        timestamp = f"[{seg['start']:.1f}s - {seg['end']:.1f}s]"
        lines.append(f"{timestamp} {role}: {seg['text']}")

    return "\n".join(lines)
