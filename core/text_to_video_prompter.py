import json
from typing import Dict, List

from PyQt6.QtCore import QThread, pyqtSignal

from utils.config import GEMINI_HEADERS, GEMINI_MODEL, ensure_gemini_api_key, get_gemini_urls_for_model
from utils.constants import REQUESTS_INSTALLED

try:
    import requests
except ImportError:
    requests = None


def build_scene_prompt_template(scene: dict, settings: dict, format_name: str = "Scene Prompt") -> str:
    scene_no = str(scene.get("scene_no", "")).strip() or "S01"
    title = str(scene.get("title", "")).strip() or "Untitled Scene"
    duration = str(scene.get("duration", "")).strip() or "8 sec"
    visual_goal = str(scene.get("visual_goal", "")).strip() or "Deliver the main visual payoff clearly."
    voiceover = str(scene.get("voiceover", "")).strip() or "Keep narration aligned with the scene goal."
    shot_type = str(scene.get("shot_type", "")).strip() or "Talking Head"
    scene_notes = str(scene.get("scene_notes", "")).strip()

    prompt_style = str(settings.get("prompt_style", "")).strip() or "Balanced"
    aspect_ratio = str(settings.get("aspect_ratio", "")).strip() or "16:9"
    output_goal = str(settings.get("output_goal", "")).strip() or "Veo Clips"
    format_value = str(format_name or "Scene Prompt").strip() or "Scene Prompt"

    if format_value == "Detailed Prompt":
        lines = [
            f"Scene ID: {scene_no}",
            f"Scene Title: {title}",
            f"Prompt Style: {prompt_style}",
            f"Aspect Ratio: {aspect_ratio}",
            f"Output Goal: {output_goal}",
            f"Shot Type: {shot_type}",
            f"Target Duration: {duration}",
            "",
            f"Visual Goal:\n{visual_goal}",
            "",
            f"Voiceover Reference:\n{voiceover}",
        ]
        if scene_notes:
            lines.extend(["", f"Scene Notes:\n{scene_notes}"])
        lines.extend(
            [
                "",
                "Prompt Draft:",
                "Describe the setting, subject, motion, framing, lighting, and mood in one coherent cinematic prompt.",
            ]
        )
        return "\n".join(lines).strip()

    if format_value == "Veo Prompt":
        parts = [
            f"Create a {duration} video shot in {aspect_ratio}.",
            f"Scene: {title}.",
            f"Shot type: {shot_type}.",
            f"Visual objective: {visual_goal}",
            f"Voiceover guidance: {voiceover}",
            f"Style: {prompt_style}.",
        ]
        if scene_notes:
            parts.append(f"Notes: {scene_notes}")
        parts.append("Keep the shot visually clear, cinematic, concrete, and easy to render as a single scene.")
        return " ".join(part.strip() for part in parts if part.strip()).strip()

    parts = [
        f"Scene {scene_no}: {title}",
        f"Duration: {duration}",
        f"Style: {prompt_style}",
        f"Output Goal: {output_goal}",
        f"Shot Type: {shot_type}",
        f"Goal: {visual_goal}",
        f"Voiceover: {voiceover}",
    ]
    if scene_notes:
        parts.append(f"Notes: {scene_notes}")
    return "\n".join(parts).strip()


def generate_local_scene_prompts(scenes: List[dict], settings: dict, format_name: str = "Scene Prompt") -> List[dict]:
    prompts: List[dict] = []
    for scene in scenes:
        prompts.append(
            {
                "scene": str(scene.get("scene_no", "")).strip(),
                "prompt": build_scene_prompt_template(scene, settings, format_name=format_name),
            }
        )
    return prompts


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


def _normalize_prompt_payload(payload: dict) -> List[dict]:
    if not isinstance(payload, dict):
        return []
    items = payload.get("prompts", [])
    if not isinstance(items, list):
        return []
    cleaned: List[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        scene = str(item.get("scene", "")).strip()
        prompt = str(item.get("prompt", "")).strip()
        if scene and prompt:
            cleaned.append({"scene": scene, "prompt": prompt})
    return cleaned


def ai_generate_scene_prompts(
    source_script: str,
    scenes: List[dict],
    settings: dict,
    *,
    format_name: str = "Scene Prompt",
    model_name: str = "",
) -> List[dict]:
    source = str(source_script or "").strip()
    if not source or not scenes:
        return []
    if not REQUESTS_INSTALLED or requests is None:
        raise ImportError("The 'requests' module is missing.")

    ensure_gemini_api_key()
    model = str(model_name or "").strip() or GEMINI_MODEL
    urls = get_gemini_urls_for_model(model)

    prompt_style = str(settings.get("prompt_style", "")).strip() or "Balanced"
    aspect_ratio = str(settings.get("aspect_ratio", "")).strip() or "16:9"
    output_goal = str(settings.get("output_goal", "")).strip() or "Veo Clips"
    format_value = str(format_name or "Scene Prompt").strip() or "Scene Prompt"

    scene_lines = []
    for scene in scenes:
        line = {
            "scene": str(scene.get("scene_no", "")).strip(),
            "title": str(scene.get("title", "")).strip(),
            "duration": str(scene.get("duration", "")).strip(),
            "shot_type": str(scene.get("shot_type", "")).strip(),
            "visual_goal": str(scene.get("visual_goal", "")).strip(),
            "voiceover": str(scene.get("voiceover", "")).strip(),
            "scene_notes": str(scene.get("scene_notes", "")).strip(),
        }
        scene_lines.append(line)

    style_rule = {
        "Scene Prompt": "Write clear scene prompts that are short and direct.",
        "Detailed Prompt": "Write fuller cinematic prompts with framing, motion, lighting, mood, and subject detail.",
        "Veo Prompt": "Write production-ready English prompts optimized for Gemini Veo video generation.",
    }.get(format_value, "Write clear scene prompts.")

    prompt = (
        "You are a scene prompt writer for text-to-video generation.\n"
        "Generate one prompt for each scene in the same order.\n"
        "Return strict JSON only.\n\n"
        "Rules:\n"
        "- Return prompts in English for best video generation compatibility.\n"
        "- Keep one prompt per scene.\n"
        "- Preserve scene order exactly.\n"
        "- Use the scene title, visual goal, voiceover, and notes as guidance.\n"
        "- Do not copy the voiceover literally unless it helps the visual prompt.\n"
        "- Keep prompts visual, concrete, and production-usable.\n"
        "- Do not add markdown or explanations.\n"
        f"- {style_rule}\n"
        f"- Prompt style preference: {prompt_style}.\n"
        f"- Aspect ratio: {aspect_ratio}.\n"
        f"- Output goal: {output_goal}.\n\n"
        "Return JSON in this schema:\n"
        "{\n"
        '  "prompts": [\n'
        '    {"scene": "S01", "prompt": "string"}\n'
        "  ]\n"
        "}\n\n"
        f"Source script:\n{source}\n\n"
        f"Scenes:\n{json.dumps(scene_lines, ensure_ascii=False, indent=2)}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.45,
            "responseMimeType": "application/json",
        },
    }

    last_error = None
    for url in urls:
        try:
            response = requests.post(url, headers=GEMINI_HEADERS, json=payload, timeout=90)
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
            parsed = _normalize_prompt_payload(json.loads(blob))
            if parsed:
                return parsed
        except Exception as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    return []


class AIGenerateScenePromptsWorker(QThread):
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(list)

    def __init__(self, source_script: str, scenes: List[dict], settings: dict, format_name: str = "Scene Prompt", model_name: str = ""):
        super().__init__()
        self.source_script = str(source_script or "")
        self.scenes = list(scenes or [])
        self.settings = dict(settings or {})
        self.format_name = str(format_name or "Scene Prompt")
        self.model_name = str(model_name or "")
        self._stop_requested = False

    def request_stop(self):
        self._stop_requested = True

    def run(self):
        if self._stop_requested:
            return
        try:
            self.status_signal.emit("Generating scene prompts with Gemini...")
            result = ai_generate_scene_prompts(
                self.source_script,
                self.scenes,
                self.settings,
                format_name=self.format_name,
                model_name=self.model_name,
            )
            if self._stop_requested:
                return
            if not result:
                self.error_signal.emit("Gemini returned empty scene prompts.")
                return
            self.finished_signal.emit(result)
        except Exception as exc:
            if not self._stop_requested:
                self.error_signal.emit(str(exc))
