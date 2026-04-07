import re
import time
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from utils.config import GEMINI_API_KEYS, ensure_gemini_api_key
from utils.constants import REQUESTS_INSTALLED

try:
    import requests
except ImportError:
    requests = None


_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def _sanitize_filename(text: str, fallback: str = "scene") -> str:
    name = re.sub(r"[^\w\-\. ]+", "", str(text or "").strip(), flags=re.UNICODE).strip()
    name = re.sub(r"\s+", "_", name)
    return name[:80] or fallback


def _coerce_duration_for_model(duration_value: str, model_name: str, resolution: str) -> tuple[str, str]:
    digits = re.findall(r"\d+", str(duration_value or ""))
    requested = digits[0] if digits else "8"
    model = str(model_name or "").strip().lower()
    resolution_value = str(resolution or "").strip().lower()

    allowed = {"4", "6", "8"}
    if requested not in allowed:
        requested = "8" if requested == "10" else "6"
    if resolution_value in {"1080p", "4k"}:
        requested = "8"
    if "veo-3" in model and requested not in allowed:
        requested = "8"
    return requested, f"{requested} sec"


def _normalize_variants(value: str) -> int:
    digits = re.findall(r"\d+", str(value or ""))
    count = int(digits[0]) if digits else 1
    return max(1, min(count, 4))


def _extract_operation_name(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("name", "")).strip()


def _extract_operation_error(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""
    error = payload.get("error")
    if not isinstance(error, dict):
        return ""
    message = str(error.get("message", "")).strip()
    code = error.get("code")
    if message and code is not None:
        return f"{message} (code {code})"
    return message


def _extract_video_uri(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""
    response = payload.get("response", {})
    if not isinstance(response, dict):
        return ""
    generate_response = response.get("generateVideoResponse", {})
    if not isinstance(generate_response, dict):
        return ""
    samples = generate_response.get("generatedSamples", [])
    if not isinstance(samples, list) or not samples:
        return ""
    video_info = samples[0].get("video", {})
    if not isinstance(video_info, dict):
        return ""
    return str(video_info.get("uri", "")).strip()


def _response_error_message(response) -> str:
    status_code = getattr(response, "status_code", "")
    body_text = ""
    try:
        data = response.json()
        if isinstance(data, dict):
            error = data.get("error", {})
            if isinstance(error, dict):
                message = str(error.get("message", "")).strip()
                details = error.get("details")
                if message and details:
                    return f"HTTP {status_code}: {message}"
                if message:
                    return f"HTTP {status_code}: {message}"
        body_text = response.text.strip()
    except Exception:
        try:
            body_text = response.text.strip()
        except Exception:
            body_text = ""
    if body_text:
        return f"HTTP {status_code}: {body_text[:800]}"
    return f"HTTP {status_code}: Request failed."


def generate_single_scene_video(
    *,
    scene: dict,
    prompt: str,
    settings: dict,
    project_name: str = "",
    output_root: str | Path = "",
    progress_callback=None,
    stop_callback=None,
) -> dict:
    if not REQUESTS_INSTALLED or requests is None:
        raise ImportError("The 'requests' module is missing.")

    ensure_gemini_api_key()

    scene_no = str(scene.get("scene_no", "")).strip() or "S01"
    scene_title = str(scene.get("title", "")).strip() or "Untitled Scene"
    prompt_text = str(prompt or "").strip()
    if not prompt_text:
        raise ValueError("Prompt draft is empty for the selected scene.")

    model = str(settings.get("model", "")).strip() or "veo-3.0-generate-001"
    resolution = str(settings.get("resolution", "")).strip() or "720p"
    aspect_ratio = str(settings.get("aspect_ratio", "")).strip() or "16:9"
    duration_seconds, duration_label = _coerce_duration_for_model(
        str(settings.get("duration", "")),
        model,
        resolution,
    )
    number_of_videos = _normalize_variants(settings.get("variants", "1"))
    negative_prompt = str(settings.get("negative_prompt", "")).strip()

    parameters = {}
    # Keep the request conservative for text-to-video. The API works with prompt-only requests,
    # so only include settings that are necessary or explicitly non-default.
    if aspect_ratio and aspect_ratio != "16:9":
        parameters["aspectRatio"] = aspect_ratio
    if resolution and resolution != "720p":
        parameters["resolution"] = resolution
    if duration_seconds and duration_seconds != "8":
        parameters["durationSeconds"] = duration_seconds
    if number_of_videos > 1:
        parameters["numberOfVideos"] = number_of_videos
    if negative_prompt:
        parameters["negativePrompt"] = negative_prompt

    payload = {"instances": [{"prompt": prompt_text}]}
    if parameters:
        payload["parameters"] = parameters

    project_folder = _sanitize_filename(project_name or "veo_project", fallback="veo_project")
    output_dir = Path(output_root or Path(__file__).resolve().parent.parent / "generated" / "text_to_video" / project_folder)
    output_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{_sanitize_filename(scene_no, 'scene')}_{_sanitize_filename(scene_title, 'clip')}.mp4"
    output_path = output_dir / file_name

    last_error = None
    for api_key in GEMINI_API_KEYS:
        if stop_callback and stop_callback():
            return {}
        headers = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        }
        try:
            if progress_callback:
                progress_callback(f"Submitting {scene_no} to Veo ({model})...")
            response = requests.post(
                f"{_BASE_URL}/models/{model}:predictLongRunning",
                headers=headers,
                json=payload,
                timeout=120,
            )
            if response.status_code >= 400:
                raise ValueError(_response_error_message(response))
            operation_data = response.json()
            operation_name = _extract_operation_name(operation_data)
            if not operation_name:
                raise ValueError("Veo did not return an operation name.")

            while True:
                if stop_callback and stop_callback():
                    return {}
                if progress_callback:
                    progress_callback(f"Waiting for Veo output for {scene_no}...")
                status_response = requests.get(
                    f"{_BASE_URL}/{operation_name}",
                    headers={"x-goog-api-key": api_key},
                    timeout=120,
                )
                if status_response.status_code >= 400:
                    raise ValueError(_response_error_message(status_response))
                status_data = status_response.json()
                if status_data.get("done") is True:
                    operation_error = _extract_operation_error(status_data)
                    if operation_error:
                        raise ValueError(operation_error)
                    video_uri = _extract_video_uri(status_data)
                    if not video_uri:
                        raise ValueError("Veo finished but no video URI was returned.")
                    if progress_callback:
                        progress_callback(f"Downloading generated clip for {scene_no}...")
                    download_response = requests.get(
                        video_uri,
                        headers={"x-goog-api-key": api_key},
                        timeout=300,
                        stream=True,
                        allow_redirects=True,
                    )
                    if download_response.status_code >= 400:
                        raise ValueError(_response_error_message(download_response))
                    with open(output_path, "wb") as handle:
                        for chunk in download_response.iter_content(chunk_size=1024 * 256):
                            if stop_callback and stop_callback():
                                return {}
                            if chunk:
                                handle.write(chunk)
                    return {
                        "scene_no": scene_no,
                        "scene_title": scene_title,
                        "model": model,
                        "duration": duration_label,
                        "aspect_ratio": aspect_ratio,
                        "resolution": resolution,
                        "variants": number_of_videos,
                        "operation_name": operation_name,
                        "video_uri": video_uri,
                        "file_path": str(output_path),
                        "file_name": output_path.name,
                    }
                time.sleep(10)
        except Exception as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    return {}


class GenerateSingleSceneWorker(QThread):
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(dict)

    def __init__(self, *, scene: dict, prompt: str, settings: dict, project_name: str = "", output_root: str = ""):
        super().__init__()
        self.scene = dict(scene or {})
        self.prompt = str(prompt or "")
        self.settings = dict(settings or {})
        self.project_name = str(project_name or "")
        self.output_root = str(output_root or "")
        self._stop_requested = False

    def request_stop(self):
        self._stop_requested = True

    def run(self):
        if self._stop_requested:
            return
        try:
            result = generate_single_scene_video(
                scene=self.scene,
                prompt=self.prompt,
                settings=self.settings,
                project_name=self.project_name,
                output_root=self.output_root,
                progress_callback=self.status_signal.emit,
                stop_callback=lambda: self._stop_requested,
            )
            if self._stop_requested:
                return
            if not result:
                self.error_signal.emit("Scene generation was stopped or returned no output.")
                return
            self.finished_signal.emit(result)
        except Exception as exc:
            if not self._stop_requested:
                self.error_signal.emit(str(exc))
