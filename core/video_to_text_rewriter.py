import re
from typing import List

from PyQt6.QtCore import QThread, pyqtSignal

from core.video_to_text_cleaner import clean_script_text
from core.video_to_text_spinner import spin_content
from utils.config import GEMINI_HEADERS, GEMINI_MODEL, ensure_gemini_api_key, get_gemini_urls_for_model
from utils.constants import REQUESTS_INSTALLED

try:
    import requests
except ImportError:
    requests = None


def _normalize_paragraphs(text: str) -> List[str]:
    source = str(text or "").strip()
    if not source:
        return []
    source = re.sub(r"\r\n?", "\n", source)
    blocks = re.split(r"\n{2,}", source)
    items = [re.sub(r"\s+", " ", block).strip() for block in blocks if block and block.strip()]
    if items:
        return items
    return [re.sub(r"\s+", " ", source).strip()]


def _to_style(text: str, output_style: str) -> str:
    source = str(text or "").strip()
    if not source:
        return ""
    paragraphs = _normalize_paragraphs(source)
    style = str(output_style or "Paragraph Script").strip()

    if style == "Voiceover Script":
        return "\n\n".join(paragraphs).strip()

    if style == "Simple Script":
        lines: List[str] = []
        for idx, block in enumerate(paragraphs, start=1):
            lines.append(f"Part {idx}: {block}")
        return "\n".join(lines).strip()

    return "\n\n".join(paragraphs).strip()


def local_rewrite_similar_script(
    text: str,
    *,
    mode: str = "Close Match",
    output_style: str = "Paragraph Script",
    preserve_original_meaning: bool = True,
    keep_original_structure: bool = True,
    avoid_copied_phrasing: bool = True,
) -> str:
    source = str(text or "").strip()
    if not source:
        return ""

    mode_name = str(mode or "Close Match").strip()
    if mode_name == "Fresh Rewrite":
        cleaned = clean_script_text(
            source,
            mode="Strong Cleanup",
            output_style="Clean Script",
            remove_filler_words=True,
            remove_repeated_lines=True,
            fix_spacing_and_noise=True,
            preserve_original_meaning=preserve_original_meaning,
        )
        rewritten = spin_content(
            cleaned,
            mode="Paragraph Spin",
            strength="Strong",
            preserve_meaning=preserve_original_meaning,
            avoid_repetition=avoid_copied_phrasing,
            keep_keywords=True,
        )
    elif mode_name == "Hook-First Rewrite":
        cleaned = clean_script_text(
            source,
            mode="Basic",
            output_style="Clean Script",
            remove_filler_words=True,
            remove_repeated_lines=True,
            fix_spacing_and_noise=True,
            preserve_original_meaning=preserve_original_meaning,
        )
        parts = _normalize_paragraphs(cleaned)
        if parts:
            hook = spin_content(
                parts[0],
                mode="Sentence Spin",
                strength="Strong",
                preserve_meaning=True,
                avoid_repetition=avoid_copied_phrasing,
                keep_keywords=True,
            )
            rest = "\n\n".join(parts[1:]).strip()
            rest_spun = spin_content(
                rest,
                mode="Paragraph Spin",
                strength="Medium",
                preserve_meaning=preserve_original_meaning,
                avoid_repetition=avoid_copied_phrasing,
                keep_keywords=True,
            ) if rest else ""
            rewritten = "\n\n".join(part for part in [hook, rest_spun] if part.strip()).strip()
        else:
            rewritten = cleaned
    elif mode_name == "Cleaner Script":
        rewritten = clean_script_text(
            source,
            mode="Strong Cleanup",
            output_style="Clean Script",
            remove_filler_words=True,
            remove_repeated_lines=True,
            fix_spacing_and_noise=True,
            preserve_original_meaning=preserve_original_meaning,
        )
    else:
        cleaned = clean_script_text(
            source,
            mode="Basic",
            output_style="Readable Transcript",
            remove_filler_words=True,
            remove_repeated_lines=True,
            fix_spacing_and_noise=True,
            preserve_original_meaning=preserve_original_meaning,
        )
        rewritten = spin_content(
            cleaned,
            mode="Sentence Spin" if keep_original_structure else "Paragraph Spin",
            strength="Medium" if avoid_copied_phrasing else "Light",
            preserve_meaning=preserve_original_meaning,
            avoid_repetition=avoid_copied_phrasing,
            keep_keywords=True,
        )

    rewritten = _to_style(rewritten, output_style)
    if re.sub(r"\s+", " ", rewritten).strip().lower() == re.sub(r"\s+", " ", source).strip().lower():
        stronger = spin_content(
            source,
            mode="Paragraph Spin" if not keep_original_structure else "Sentence Spin",
            strength="Strong",
            preserve_meaning=preserve_original_meaning,
            avoid_repetition=True,
            keep_keywords=True,
        )
        rewritten = _to_style(stronger or source, output_style)
    return rewritten


def ai_rewrite_similar_script(
    text: str,
    *,
    mode: str = "Close Match",
    output_style: str = "Paragraph Script",
    preserve_original_meaning: bool = True,
    keep_original_structure: bool = True,
    avoid_copied_phrasing: bool = True,
    model_name: str = "",
) -> str:
    source = str(text or "").strip()
    if not source:
        return ""
    if not REQUESTS_INSTALLED or requests is None:
        raise ImportError("The 'requests' module is missing.")

    ensure_gemini_api_key()
    model = str(model_name or "").strip() or GEMINI_MODEL
    urls = get_gemini_urls_for_model(model)

    mode_rule_map = {
        "Close Match": "Keep the same overall message and pacing, but refresh the wording so it reads as a new script.",
        "Fresh Rewrite": "Rewrite more aggressively so the script feels new, while preserving the same core topic and useful points.",
        "Hook-First Rewrite": "Make the opening hook stronger and more attention-grabbing, while preserving the rest of the message.",
        "Cleaner Script": "Focus on clarity, flow, and readability more than novelty.",
    }
    style_rule_map = {
        "Paragraph Script": "Output as normal readable paragraphs.",
        "Voiceover Script": "Output as a clean voiceover script with readable paragraph breaks.",
        "Simple Script": "Output as simple short blocks that are easy to read aloud.",
    }

    meaning_rule = (
        "Preserve the original meaning closely."
        if preserve_original_meaning
        else "You may simplify and tighten the message while keeping the main idea."
    )
    structure_rule = (
        "Keep the original structure and order of ideas."
        if keep_original_structure
        else "You may lightly restructure the flow to improve readability."
    )
    copy_rule = (
        "Avoid copied phrasing and reduce sentence-level overlap with the source."
        if avoid_copied_phrasing
        else "You may stay close to the source wording when useful."
    )

    prompt = (
        "You are a script rewriter for video content.\n"
        "Rewrite the source script into a new script in the same language.\n\n"
        "Rules:\n"
        "- Do not translate.\n"
        "- Do not summarize.\n"
        "- Do not add new facts that are not supported by the source.\n"
        "- Keep names, numbers, products, and important keywords when they matter.\n"
        "- Make the text read naturally and clearly.\n"
        f"- {mode_rule_map.get(mode, mode_rule_map['Close Match'])}\n"
        f"- {style_rule_map.get(output_style, style_rule_map['Paragraph Script'])}\n"
        f"- {meaning_rule}\n"
        f"- {structure_rule}\n"
        f"- {copy_rule}\n"
        "- Output plain text only. No markdown. No explanations.\n\n"
        "Source script:\n"
        f"{source}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.55,
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
            if text_out:
                return _to_style(text_out, output_style)
        except Exception as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    return ""


class AIRewriteWorker(QThread):
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    def __init__(
        self,
        text: str,
        *,
        mode: str = "Close Match",
        output_style: str = "Paragraph Script",
        preserve_original_meaning: bool = True,
        keep_original_structure: bool = True,
        avoid_copied_phrasing: bool = True,
        model_name: str = "",
    ):
        super().__init__()
        self.text = str(text or "")
        self.mode = str(mode or "Close Match")
        self.output_style = str(output_style or "Paragraph Script")
        self.preserve_original_meaning = bool(preserve_original_meaning)
        self.keep_original_structure = bool(keep_original_structure)
        self.avoid_copied_phrasing = bool(avoid_copied_phrasing)
        self.model_name = str(model_name or "")
        self._stop_requested = False

    def request_stop(self):
        self._stop_requested = True

    def run(self):
        if self._stop_requested:
            return
        try:
            self.status_signal.emit("AI Rewrite Similar Script is running...")
            result = ai_rewrite_similar_script(
                self.text,
                mode=self.mode,
                output_style=self.output_style,
                preserve_original_meaning=self.preserve_original_meaning,
                keep_original_structure=self.keep_original_structure,
                avoid_copied_phrasing=self.avoid_copied_phrasing,
                model_name=self.model_name,
            )
            if self._stop_requested:
                return
            if not str(result or "").strip():
                self.error_signal.emit("AI Rewrite Similar Script returned empty text.")
                return
            self.finished_signal.emit(str(result))
        except Exception as exc:
            if not self._stop_requested:
                self.error_signal.emit(str(exc))
