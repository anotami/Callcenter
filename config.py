import os
import logging
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv es opcional, usa variables de entorno directamente

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
HF_TOKEN = os.getenv("HF_TOKEN", "")

# LLM (Groq, LM Studio, Ollama, o cualquier API compatible con OpenAI)
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:1234/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.1-8b-instruct")
LLM_API_KEY = os.getenv("LLM_API_KEY", "not-needed")

# Lista de modelos fallback (se intentan en orden si el principal falla)
# Configurable via variable de entorno separada por comas
_fallback_env = os.getenv("LLM_FALLBACK_MODELS", "")
LLM_FALLBACK_MODELS = (
    [m.strip() for m in _fallback_env.split(",") if m.strip()]
    if _fallback_env
    else [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "gemma2-9b-it",
        "mixtral-8x7b-32768",
        "llama3-70b-8192",
    ]
)
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "5"))

# SQL Server
SQL_SERVER = os.getenv("SQL_SERVER", "localhost")
SQL_DATABASE = os.getenv("SQL_DATABASE", "CallCenter")
SQL_USERNAME = os.getenv("SQL_USERNAME", "sa")
SQL_PASSWORD = os.getenv("SQL_PASSWORD", "")
SQL_DRIVER = os.getenv("SQL_DRIVER", "ODBC Driver 17 for SQL Server")

# Formatos de audio soportados
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".wma"}
