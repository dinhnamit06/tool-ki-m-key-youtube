import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DOTENV_PATH = _PROJECT_ROOT / ".env"

if load_dotenv is not None:
    load_dotenv(dotenv_path=_DOTENV_PATH, override=False)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_HEADERS = {"Content-Type": "application/json"}
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"


def ensure_gemini_api_key():
    if not _DOTENV_PATH.exists() and not os.getenv("GEMINI_API_KEY", "").strip():
        raise ValueError("Please create .env file with GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise ValueError("Please create .env file with GEMINI_API_KEY")


def ensure_openai_api_key():
    if not _DOTENV_PATH.exists() and not os.getenv("OPENAI_API_KEY", "").strip():
        raise ValueError("Please create .env file with OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        raise ValueError("Please create .env file with OPENAI_API_KEY")


def get_openai_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }
