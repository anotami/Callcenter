"""
Script de verificacion - Comprueba que todo este instalado correctamente.
Ejecutar: python verify_setup.py
"""

import sys


def check(name: str, test_fn) -> bool:
    try:
        result = test_fn()
        print(f"  [OK] {name}: {result}")
        return True
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        return False


def main():
    print("=" * 55)
    print("  VERIFICACION DE INSTALACION")
    print("=" * 55)
    results = []

    # 1. Python
    print("\n[1/7] Python")
    results.append(check("Version", lambda: sys.version.split()[0]))

    # 2. PyTorch + CUDA
    print("\n[2/7] PyTorch + CUDA")
    def check_torch():
        import torch
        cuda = torch.cuda.is_available()
        if cuda:
            gpu = torch.cuda.get_device_name(0)
            return f"v{torch.__version__} | CUDA OK | GPU: {gpu}"
        return f"v{torch.__version__} | Solo CPU (sin CUDA)"
    results.append(check("PyTorch", check_torch))

    # 3. faster-whisper
    print("\n[3/7] faster-whisper (Transcripcion)")
    def check_whisper():
        from faster_whisper import WhisperModel
        return "Instalado correctamente"
    results.append(check("faster-whisper", check_whisper))

    # 4. pyannote
    print("\n[4/7] pyannote.audio (Diarizacion)")
    def check_pyannote():
        from pyannote.audio import Pipeline
        return "Instalado correctamente"
    results.append(check("pyannote.audio", check_pyannote))

    # 5. HuggingFace Token
    print("\n[5/7] HuggingFace Token")
    def check_hf():
        from config import HF_TOKEN
        if not HF_TOKEN or HF_TOKEN.startswith("hf_xxx"):
            raise ValueError(
                "No configurado. Edita .env con tu token de "
                "https://huggingface.co/settings/tokens"
            )
        return f"Configurado ({HF_TOKEN[:10]}...)"
    results.append(check("HF_TOKEN", check_hf))

    # 6. LLM (LM Studio / Ollama)
    print("\n[6/7] LLM Local (LM Studio / Ollama)")
    def check_llm():
        from openai import OpenAI
        from config import LLM_BASE_URL, LLM_MODEL, LLM_API_KEY
        client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
        models = client.models.list()
        model_names = [m.id for m in models.data]
        if model_names:
            return f"Conectado | Modelos: {', '.join(model_names[:3])}"
        raise ValueError("Servidor respondio pero sin modelos cargados")
    results.append(check("LLM Server", check_llm))

    # 7. SQL Server (opcional)
    print("\n[7/7] SQL Server (opcional)")
    def check_sql():
        import pyodbc
        from config import SQL_SERVER, SQL_DATABASE
        from database import get_connection
        conn = get_connection()
        conn.close()
        return f"Conectado a {SQL_SERVER}/{SQL_DATABASE}"
    results.append(check("SQL Server", check_sql))

    # Resumen
    ok = sum(results)
    total = len(results)
    print(f"\n{'='*55}")
    print(f"  RESULTADO: {ok}/{total} componentes OK")

    if ok >= 6:
        print("  Estado: LISTO para procesar audios")
        print(f"\n  Ejecuta: python main.py")
        if not results[6]:  # SQL fallo
            print(f"  (Usa --no-db si no necesitas SQL Server)")
    elif ok >= 4:
        print("  Estado: CASI LISTO - revisa los componentes con [FAIL]")
    else:
        print("  Estado: Faltan componentes criticos")

    print(f"{'='*55}")


if __name__ == "__main__":
    main()
