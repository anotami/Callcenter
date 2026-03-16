import os
import logging
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv es opcional, usa variables de entorno directamente


def _secret(key: str, default: str = "") -> str:
    """Lee un valor de .streamlit/secrets.toml, luego env vars, luego default."""
    # 1) Streamlit secrets (archivo .streamlit/secrets.toml)
    try:
        import streamlit as st
        val = st.secrets.get(key)
        if val is not None and str(val).strip():
            return str(val)
    except Exception:
        # Fuera de contexto Streamlit o secrets no disponible
        # Intentar leer directamente del archivo TOML
        try:
            secrets_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
            if secrets_path.exists():
                import tomllib
                with open(secrets_path, "rb") as f:
                    data = tomllib.load(f)
                val = data.get(key)
                if val is not None and str(val).strip():
                    return str(val)
        except Exception:
            pass
    # 2) Variable de entorno / .env
    env_val = os.getenv(key)
    if env_val is not None:
        return env_val
    return default

# --- Logging centralizado ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("callcenter")

# Directorios
BASE_DIR = Path(__file__).parent
AUDIO_DIR = BASE_DIR / "audio"
OUTPUT_DIR = BASE_DIR / "output"
AUDIO_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Whisper / faster-whisper
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "large-v3")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cuda")  # "cuda" o "cpu"
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "es")

# HuggingFace (para pyannote)
HF_TOKEN = _secret("HF_TOKEN", "")

# LLM (Groq, LM Studio, Ollama, o cualquier API compatible con OpenAI)
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
LLM_API_KEY = _secret("LLM_API_KEY", "not-needed")

# Groq como proveedor cloud de fallback (opcional)
GROQ_API_KEY = _secret("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Lista de modelos fallback LOCALES (mismo servidor que LLM_BASE_URL)
_fallback_env = os.getenv("LLM_FALLBACK_MODELS", "")
LLM_FALLBACK_MODELS = (
    [m.strip() for m in _fallback_env.split(",") if m.strip()]
    if _fallback_env
    else []
)

# Modelos Groq (solo se usan si GROQ_API_KEY esta configurada)
GROQ_FALLBACK_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
    "mixtral-8x7b-32768",
]

LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "5"))

# SQL Server
SQL_SERVER = os.getenv("SQL_SERVER", "localhost")
SQL_DATABASE = os.getenv("SQL_DATABASE", "CallCenter")
SQL_USERNAME = os.getenv("SQL_USERNAME", "sa")
SQL_PASSWORD = _secret("SQL_PASSWORD", "")
SQL_DRIVER = os.getenv("SQL_DRIVER", "ODBC Driver 17 for SQL Server")

# Formatos de audio soportados
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".wma"}
