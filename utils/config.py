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
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
GEMINI_API_KEY_BACKUP = os.getenv("GEMINI_API_KEY_BACKUP", "").strip()
_GEMINI_API_KEYS_RAW = os.getenv("GEMINI_API_KEYS", "").strip()
GEMINI_API_KEYS = [
    k.strip()
    for k in _GEMINI_API_KEYS_RAW.split(",")
    if k and k.strip()
]
if GEMINI_API_KEY:
    GEMINI_API_KEYS.insert(0, GEMINI_API_KEY)
if GEMINI_API_KEY_BACKUP:
    GEMINI_API_KEYS.append(GEMINI_API_KEY_BACKUP)

# Keep unique order.
_seen_keys = set()
_unique_keys = []
for _key in GEMINI_API_KEYS:
    if _key in _seen_keys:
        continue
    _seen_keys.add(_key)
    _unique_keys.append(_key)
GEMINI_API_KEYS = _unique_keys
GEMINI_URL = ""
if GEMINI_API_KEYS:
    GEMINI_URL = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={GEMINI_API_KEYS[0]}"
    )

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"


def ensure_gemini_api_key():
    has_any_runtime_key = (
        bool(os.getenv("GEMINI_API_KEY", "").strip())
        or bool(os.getenv("GEMINI_API_KEY_BACKUP", "").strip())
        or bool(os.getenv("GEMINI_API_KEYS", "").strip())
    )
    if not _DOTENV_PATH.exists() and not has_any_runtime_key:
        raise ValueError("Please create .env file with GEMINI_API_KEY")
    if not GEMINI_API_KEYS:
        raise ValueError("Please create .env file with GEMINI_API_KEY")


def get_gemini_urls():
    base = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key="
    return [f"{base}{key}" for key in GEMINI_API_KEYS]


def get_gemini_urls_for_model(model_name=""):
    model = str(model_name or "").strip() or GEMINI_MODEL
    base = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key="
    return [f"{base}{key}" for key in GEMINI_API_KEYS]


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
