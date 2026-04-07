import json
from pathlib import Path


_SESSION_ROOT = Path(__file__).resolve().parent.parent / "generated" / "session"


def session_file_path(name):
    safe_name = str(name or "").strip() or "session"
    return _SESSION_ROOT / f"{safe_name}.json"


def load_session_json(name, default=None):
    path = session_file_path(name)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_session_json(name, payload):
    path = session_file_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)
    return path
