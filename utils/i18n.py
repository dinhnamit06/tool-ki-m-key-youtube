import json
from functools import lru_cache
from pathlib import Path


DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = {
    "en": "English",
    "vi": "Tiếng Việt",
}

_LOCALES_ROOT = Path(__file__).resolve().parent.parent / "locales"


@lru_cache(maxsize=None)
def _load_locale(language):
    lang = str(language or DEFAULT_LANGUAGE).strip().lower() or DEFAULT_LANGUAGE
    path = _LOCALES_ROOT / f"{lang}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def translate(language, key, default=None, **kwargs):
    lang = str(language or DEFAULT_LANGUAGE).strip().lower() or DEFAULT_LANGUAGE
    primary = _load_locale(lang)
    fallback = _load_locale(DEFAULT_LANGUAGE)
    text = primary.get(key, fallback.get(key, default if default is not None else key))
    if kwargs:
        try:
            return str(text).format(**kwargs)
        except Exception:
            return str(text)
    return str(text)
