"""
Pipeline principal - Orquestador del sistema de evaluacion de Call Center.

Flujo:
  1. Busca archivos de audio en el directorio audio/
  2. Transcribe cada audio con faster-whisper
  3. Diariza para separar hablantes con pyannote
  4. Combina transcripcion + diarizacion en dialogo
  5. Envia a LLM (LM Studio/Ollama) para evaluar calidad
  6. Guarda resultados en SQL Server y/o CSV

Uso:
  python main.py                     # Procesa todos los audios en audio/
  python main.py audio/llamada.mp3   # Procesa un archivo especifico
  python main.py --no-db             # Sin guardar en SQL Server (solo CSV)
"""

import sys
import json
from pathlib import Path
from datetime import datetime

from config import AUDIO_DIR, OUTPUT_DIR, AUDIO_EXTENSIONS
from transcriber import load_whisper_model, transcribe
from diarizer import (
    load_diarization_model,
    diarize,
    merge_transcription_diarization,
    format_dialogue,
)
from analyzer import create_llm_client, analyze_call, format_evaluation_report


def find_audio_files(path: str | None = None) -> list[Path]:
    """Encuentra archivos de audio para procesar."""
    if path:
        p = Path(path)
        if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS:
            return [p]
        print(f"[Error] Archivo no valido: {path}")
        return []

    files = [
        f for f in AUDIO_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
    ]
    files.sort()
    return files


def process_single_audio(
    audio_path: Path,
    whisper_model,
    diarization_pipeline,
    llm_client,
    save_to_db: bool = True,
) -> dict | None:
    """Procesa un solo archivo de audio a traves del pipeline completo."""
    print(f"\n{'='*60}")
    print(f"Procesando: {audio_path.name}")
    print(f"{'='*60}")

    # Paso 1: Transcripcion
    print("\n[1/4] Transcribiendo audio...")
    transcription = transcribe(whisper_model, str(audio_path))
    if not transcription:
        print("[Error] No se pudo transcribir el audio")
        return None

    # Paso 2: Diarizacion
    print("\n[2/4] Diarizando (identificando hablantes)...")
    diarization = diarize(diarization_pipeline, str(audio_path))

    # Paso 3: Combinar transcripcion + diarizacion
    print("\n[3/4] Combinando transcripcion con diarizacion...")
    merged = merge_transcription_diarization(transcription, diarization)
    dialogue = format_dialogue(merged)

    # Guardar transcripcion en archivo
    transcript_path = OUTPUT_DIR / f"{audio_path.stem}_transcripcion.txt"
    transcript_path.write_text(dialogue, encoding="utf-8")
    print(f"  Transcripcion guardada: {transcript_path}")

    # Paso 4: Analisis con LLM
    print("\n[4/4] Analizando calidad con LLM...")
    evaluation = analyze_call(llm_client, dialogue)

    # Guardar evaluacion en JSON
    eval_path = OUTPUT_DIR / f"{audio_path.stem}_evaluacion.json"
    eval_path.write_text(json.dumps(evaluation, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Evaluacion guardada: {eval_path}")

    # Mostrar reporte
    report = format_evaluation_report(evaluation)
    print(f"\n{report}")

    # Guardar reporte en texto
    report_path = OUTPUT_DIR / f"{audio_path.stem}_reporte.txt"
    report_path.write_text(report, encoding="utf-8")

    # Guardar en base de datos
    if save_to_db:
        try:
            from database import get_connection, create_tables, save_evaluation
            conn = get_connection()
            create_tables(conn)
            num_speakers = len(set(s["speaker"] for s in merged))
            duration = transcription[-1]["end"] if transcription else 0
            save_evaluation(conn, audio_path.name, dialogue, evaluation,
                            num_speakers, duration)
            conn.close()
        except Exception as e:
            print(f"[DB] No se pudo guardar en base de datos: {e}")
            print("[DB] Los resultados se guardaron en archivos locales.")

    return evaluation


def main():
    # Parsear argumentos
    args = sys.argv[1:]
    save_to_db = "--no-db" not in args
    audio_path = None
    for arg in args:
        if arg != "--no-db":
            audio_path = arg
            break

    # Buscar audios
    audio_files = find_audio_files(audio_path)
    if not audio_files:
        print(f"No se encontraron archivos de audio en {AUDIO_DIR}/")
        print(f"Formatos soportados: {', '.join(AUDIO_EXTENSIONS)}")
        print(f"\nUso: python main.py [archivo_audio] [--no-db]")
        return

    print(f"Archivos a procesar: {len(audio_files)}")
    if not save_to_db:
        print("Modo: Sin base de datos (solo archivos locales)")

    # Cargar modelos (una sola vez para todos los audios)
    print("\nCargando modelos...")
    whisper_model = load_whisper_model()
    diarization_pipeline = load_diarization_model()
    llm_client = create_llm_client()
    print("Todos los modelos cargados.\n")

    # Procesar cada audio
    results = []
    for audio_file in audio_files:
        result = process_single_audio(
            audio_file, whisper_model, diarization_pipeline,
            llm_client, save_to_db,
        )
        if result:
            results.append({"file": audio_file.name, "evaluation": result})

    # Resumen final
    print(f"\n{'='*60}")
    print(f"PROCESAMIENTO COMPLETADO")
    print(f"{'='*60}")
    print(f"Archivos procesados: {len(results)}/{len(audio_files)}")
    print(f"Resultados en: {OUTPUT_DIR}/")

    if results:
        scores = [
            r["evaluation"].get("puntaje_total", 0)
            for r in results
            if isinstance(r["evaluation"].get("puntaje_total"), (int, float))
        ]
        if scores:
            print(f"Puntaje promedio: {sum(scores)/len(scores):.1f}/100")


if __name__ == "__main__":
    main()
