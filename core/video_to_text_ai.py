import json

from PyQt6.QtCore import QThread, pyqtSignal

from utils.config import GEMINI_HEADERS, GEMINI_MODEL, ensure_gemini_api_key, get_gemini_urls_for_model
from utils.constants import REQUESTS_INSTALLED

try:
    import requests
except ImportError:
    requests = None


def _extract_json_object_blob(text: str) -> str:
    source = str(text or "")
    start = source.find("{")
    if start < 0:
        return ""
    depth = 0
    in_string = False
    escaped = False
    for idx in range(start, len(source)):
        ch = source[idx]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
            continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                return source[start : idx + 1]
    return ""


def _normalize_structure_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {}
    main_points = payload.get("main_points", [])
    if not isinstance(main_points, list):
        main_points = []
    return {
        "hook": str(payload.get("hook", "")).strip(),
        "intro": str(payload.get("intro", "")).strip(),
        "main_points": [str(item).strip() for item in main_points if str(item).strip()],
        "cta": str(payload.get("cta", "")).strip(),
    }


def ai_enhanced_auto_punctuate(text: str, model_name: str = "") -> str:
    source = str(text or "").strip()
    if not source:
        return ""
    if not REQUESTS_INSTALLED or requests is None:
        raise ImportError("The 'requests' module is missing.")

    ensure_gemini_api_key()
    model = str(model_name or "").strip() or GEMINI_MODEL
    urls = get_gemini_urls_for_model(model)
    prompt = (
        "You are a transcript formatter.\n"
        "Rewrite the transcript into clean, readable text while preserving the original language.\n"
        "Rules:\n"
        "- Do not translate.\n"
        "- Do not summarize.\n"
        "- Do not add facts.\n"
        "- Keep all core meaning.\n"
        "- Add punctuation and capitalization.\n"
        "- Break into readable paragraphs.\n"
        "- Remove only obvious duplicate caption fragments and obvious caption noise.\n"
        "- Keep names, products, numbers, and important keywords.\n"
        "- Output plain text only. No markdown. No explanations.\n\n"
        "Transcript:\n"
        f"{source}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
        },
    }

    last_error = None
    for url in urls:
        try:
            response = requests.post(url, headers=GEMINI_HEADERS, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                continue
            parts = candidates[0].get("content", {}).get("parts", [])
            text_out = "".join(str(part.get("text", "")) for part in parts).strip()
            if text_out:
                return text_out
        except Exception as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    return ""


def ai_extract_structure(text: str, *, preserve_original_flow: bool = True, model_name: str = "") -> dict:
    source = str(text or "").strip()
    if not source:
        return {}
    if not REQUESTS_INSTALLED or requests is None:
        raise ImportError("The 'requests' module is missing.")

    ensure_gemini_api_key()
    model = str(model_name or "").strip() or GEMINI_MODEL
    urls = get_gemini_urls_for_model(model)
    ordering_rule = (
        "Keep main points in the same order they appear in the source transcript."
        if preserve_original_flow
        else "You may reorder main points so the strongest and most useful points appear first."
    )
    prompt = (
        "You are a transcript structure analyst.\n"
        "Analyze the transcript and extract the real content structure.\n"
        "Return strict JSON only.\n\n"
        "Goals:\n"
        "- Identify the best opening hook.\n"
        "- Identify the intro/setup that comes after the hook.\n"
        "- Extract the main content points as short, useful points.\n"
        "- Identify the CTA or closing takeaway.\n\n"
        "Rules:\n"
        "- Preserve the original language.\n"
        "- Do not translate.\n"
        "- Do not invent content that is not supported by the transcript.\n"
        "- Clean obvious caption noise only when needed for readability.\n"
        "- Keep names, numbers, products, and key topics.\n"
        f"- {ordering_rule}\n"
        "- If there is no explicit CTA, use the closing wrap-up sentence instead.\n"
        "- Keep hook and intro concise.\n"
        "- Return 3 to 6 main points when possible.\n"
        "- Main points should be short sentences or strong phrases, not long paragraphs.\n\n"
        "JSON schema:\n"
        "{\n"
        '  "hook": "string",\n'
        '  "intro": "string",\n'
        '  "main_points": ["string", "string"],\n'
        '  "cta": "string"\n'
        "}\n\n"
        "Transcript:\n"
        f"{source}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }

    last_error = None
    for url in urls:
        try:
            response = requests.post(url, headers=GEMINI_HEADERS, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                continue
            parts = candidates[0].get("content", {}).get("parts", [])
            text_out = "".join(str(part.get("text", "")) for part in parts).strip()
            if not text_out:
                continue
            blob = _extract_json_object_blob(text_out)
            if not blob:
                continue
            parsed = _normalize_structure_payload(json.loads(blob))
            if parsed:
                return parsed
        except Exception as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    return {}


class AIPunctuateWorker(QThread):
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    def __init__(self, text: str, model_name: str = ""):
        super().__init__()
        self.text = str(text or "")
        self.model_name = str(model_name or "")
        self._stop_requested = False

    def request_stop(self):
        self._stop_requested = True

    def run(self):
        if self._stop_requested:
            return
        try:
            self.status_signal.emit("AI Enhanced Auto Punctuate is running...")
            result = ai_enhanced_auto_punctuate(self.text, model_name=self.model_name)
            if self._stop_requested:
                return
            if not result.strip():
                self.error_signal.emit("AI Enhanced Auto Punctuate returned empty text.")
                return
            self.finished_signal.emit(result)
        except Exception as exc:
            if not self._stop_requested:
                self.error_signal.emit(str(exc))


class AIStructureWorker(QThread):
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(dict)

    def __init__(self, text: str, preserve_original_flow: bool = True, model_name: str = ""):
        super().__init__()
        self.text = str(text or "")
        self.preserve_original_flow = bool(preserve_original_flow)
        self.model_name = str(model_name or "")
        self._stop_requested = False

    def request_stop(self):
        self._stop_requested = True

    def run(self):
        if self._stop_requested:
            return
        try:
            self.status_signal.emit("AI Extract Structure is running...")
            result = ai_extract_structure(
                self.text,
                preserve_original_flow=self.preserve_original_flow,
                model_name=self.model_name,
            )
            if self._stop_requested:
                return
            if not isinstance(result, dict) or not any(str(result.get(key, "")).strip() for key in ("hook", "intro", "cta")):
                self.error_signal.emit("AI Extract Structure returned empty content.")
                return
            self.finished_signal.emit(result)
        except Exception as exc:
            if not self._stop_requested:
                self.error_signal.emit(str(exc))
