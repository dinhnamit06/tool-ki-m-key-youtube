import math
import re
from typing import Dict, List

from core.video_to_text_formatter import auto_punctuate_transcript
from core.video_to_text_structure import extract_structure


SECTION_ALIASES = {
    "hook": "hook",
    "intro": "intro",
    "main points": "main_points",
    "main point": "main_points",
    "mainpoints": "main_points",
    "cta": "cta",
}


def _normalize_text(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    value = re.sub(r"\r\n?", "\n", value)
    value = re.sub(r"[ \t]+", " ", value)
    return value.strip()


def _split_sentences(text: str) -> List[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []
    if len(re.findall(r"[.!?]", normalized)) < 2:
        punctuated = auto_punctuate_transcript(normalized)
        if punctuated.strip():
            normalized = punctuated.strip()
    parts = re.split(r"(?<=[.!?])\s+|\n+", normalized)
    cleaned: List[str] = []
    for part in parts:
        sentence = re.sub(r"\s+", " ", str(part or "")).strip(" -")
        if sentence:
            cleaned.append(sentence)
    return cleaned


def _split_paragraphs(text: str) -> List[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []
    parts = re.split(r"\n\s*\n+", normalized)
    cleaned: List[str] = []
    for part in parts:
        block = re.sub(r"\s+", " ", str(part or "")).strip()
        if block:
            cleaned.append(block)
    return cleaned


def _parse_seconds(duration_text: str) -> int:
    match = re.search(r"(\d+)", str(duration_text or ""))
    value = int(match.group(1)) if match else 8
    return max(4, min(20, value))


def _format_seconds(seconds: int) -> str:
    return f"{max(4, int(seconds))} sec"


def _scene_title(prefix: str, text: str, index: int | None = None) -> str:
    snippet = re.sub(r"\s+", " ", str(text or "")).strip(" .")
    words = snippet.split()
    if index is not None:
        return f"{prefix} {index}"
    if not words:
        return prefix
    if len(words) <= 6:
        return snippet
    return f"{' '.join(words[:6])}..."


def _default_visual_goal(kind: str, index: int | None = None) -> str:
    if kind == "hook":
        return "Open with a pattern-interrupt visual that sells the main promise fast."
    if kind == "intro":
        return "Set context quickly and establish what the viewer is about to get."
    if kind == "cta":
        return "Close with a clean payoff or call to action visual."
    label = f"main point {index}" if index is not None else "main point"
    return f"Visualize {label} clearly with concrete supporting footage."


def _split_long_block(text: str, *, max_sentences: int = 2, max_words: int = 65) -> List[str]:
    sentences = _split_sentences(text)
    if not sentences:
        return []
    if len(sentences) <= max_sentences and len(" ".join(sentences).split()) <= max_words:
        return [" ".join(sentences).strip()]
    chunks: List[str] = []
    current: List[str] = []
    current_words = 0
    for sentence in sentences:
        sentence_words = len(sentence.split())
        if current and (len(current) >= max_sentences or current_words + sentence_words > max_words):
            chunks.append(" ".join(current).strip())
            current = []
            current_words = 0
        current.append(sentence)
        current_words += sentence_words
    if current:
        chunks.append(" ".join(current).strip())
    return chunks


def parse_structure_text(text: str) -> Dict[str, object]:
    lines = _normalize_text(text).splitlines()
    sections: Dict[str, List[str]] = {"hook": [], "intro": [], "main_points": [], "cta": []}
    current_section = None
    for raw_line in lines:
        line = str(raw_line or "").strip()
        if not line:
            continue
        heading_match = re.match(r"^([A-Za-z ]+):\s*(.*)$", line)
        if heading_match:
            key = SECTION_ALIASES.get(heading_match.group(1).strip().lower())
            if key:
                current_section = key
                tail = heading_match.group(2).strip()
                if tail and tail.lower() != "not-given":
                    if key == "main_points":
                        cleaned = re.sub(r"^\d+\.\s*", "", tail).strip()
                        if cleaned:
                            sections[key].append(cleaned)
                    else:
                        sections[key].append(tail)
                continue
        if current_section == "main_points":
            cleaned = re.sub(r"^[-*]\s*", "", line)
            cleaned = re.sub(r"^\d+\.\s*", "", cleaned).strip()
            if cleaned and cleaned.lower() != "not-given":
                sections[current_section].append(cleaned)
        elif current_section and line.lower() != "not-given":
            sections[current_section].append(line)
    return {
        "hook": " ".join(sections["hook"]).strip(),
        "intro": " ".join(sections["intro"]).strip(),
        "main_points": [item.strip() for item in sections["main_points"] if item.strip()],
        "cta": " ".join(sections["cta"]).strip(),
    }


def _has_structured_sections(structure: Dict[str, object]) -> bool:
    return any(
        [
            str(structure.get("hook", "")).strip(),
            str(structure.get("intro", "")).strip(),
            str(structure.get("cta", "")).strip(),
            any(str(item or "").strip() for item in (structure.get("main_points", []) or [])),
        ]
    )


def _scene_dict(title: str, duration: str, visual_goal: str, voiceover: str, status: str = "Draft", clip: str = "Not Generated") -> Dict[str, str]:
    return {
        "title": title.strip() or "New Scene",
        "duration": duration.strip() or "8 sec",
        "visual_goal": visual_goal.strip() or "Describe the scene goal clearly.",
        "voiceover": voiceover.strip(),
        "status": status,
        "clip": clip,
    }


def _build_structure_scenes(structure: Dict[str, object], default_duration: str) -> List[Dict[str, str]]:
    base_seconds = _parse_seconds(default_duration)
    short_duration = _format_seconds(max(4, base_seconds - 2))
    normal_duration = _format_seconds(base_seconds)

    scenes: List[Dict[str, str]] = []

    hook = str(structure.get("hook", "")).strip()
    if hook and hook.lower() != "not-given":
        for idx, chunk in enumerate(_split_long_block(hook, max_sentences=2, max_words=38), start=1):
            title = "Hook / Opening" if idx == 1 else f"Hook / Opening {idx}"
            scenes.append(
                _scene_dict(title, short_duration, _default_visual_goal("hook"), chunk)
            )

    intro = str(structure.get("intro", "")).strip()
    if intro and intro.lower() != "not-given":
        for idx, chunk in enumerate(_split_long_block(intro, max_sentences=2, max_words=48), start=1):
            title = "Intro / Setup" if idx == 1 else f"Intro / Setup {idx}"
            scenes.append(
                _scene_dict(title, normal_duration, _default_visual_goal("intro"), chunk)
            )

    main_points = [str(item).strip() for item in (structure.get("main_points", []) or []) if str(item).strip() and str(item).strip().lower() != "not-given"]
    point_counter = 1
    for point in main_points:
        chunks = _split_long_block(point, max_sentences=2, max_words=52)
        for chunk_index, chunk in enumerate(chunks, start=1):
            title = f"Main Point {point_counter}"
            if len(chunks) > 1:
                title = f"{title}.{chunk_index}"
            scenes.append(
                _scene_dict(title, normal_duration, _default_visual_goal("main", point_counter), chunk)
            )
        point_counter += 1

    cta = str(structure.get("cta", "")).strip()
    if cta and cta.lower() != "not-given":
        for idx, chunk in enumerate(_split_long_block(cta, max_sentences=2, max_words=36), start=1):
            title = "CTA / Closing" if idx == 1 else f"CTA / Closing {idx}"
            scenes.append(
                _scene_dict(title, short_duration, _default_visual_goal("cta"), chunk)
            )

    return scenes


def _build_paragraph_scenes(text: str, default_duration: str) -> List[Dict[str, str]]:
    paragraphs = _split_paragraphs(text)
    if len(paragraphs) < 3:
        return []
    scenes: List[Dict[str, str]] = []
    base_seconds = _parse_seconds(default_duration)
    short_duration = _format_seconds(max(4, base_seconds - 2))
    normal_duration = _format_seconds(base_seconds)

    for index, paragraph in enumerate(paragraphs, start=1):
        if index == 1:
            title = "Hook / Opening"
            visual_goal = _default_visual_goal("hook")
            duration = short_duration
        elif index == len(paragraphs):
            title = "CTA / Closing"
            visual_goal = _default_visual_goal("cta")
            duration = short_duration
        else:
            title = f"Main Point {index - 1}"
            visual_goal = _default_visual_goal("main", index - 1)
            duration = normal_duration
        scenes.append(_scene_dict(title, duration, visual_goal, paragraph))
    return scenes


def create_scene_plan(source_text: str, *, default_duration: str = "8 sec") -> List[Dict[str, str]]:
    text = _normalize_text(source_text)
    if not text:
        return []

    explicit_structure = parse_structure_text(text)
    if _has_structured_sections(explicit_structure):
        scenes = _build_structure_scenes(explicit_structure, default_duration)
        if scenes:
            return scenes

    paragraph_scenes = _build_paragraph_scenes(text, default_duration)
    if paragraph_scenes:
        return paragraph_scenes

    inferred_structure = extract_structure(text, mode="Detailed")
    scenes = _build_structure_scenes(inferred_structure, default_duration)
    if scenes:
        return scenes

    sentences = _split_sentences(text)
    if not sentences:
        return []

    group_size = 2 if len(sentences) > 4 else 1
    chunks: List[str] = []
    for index in range(0, len(sentences), group_size):
        chunks.append(" ".join(sentences[index:index + group_size]).strip())

    base_seconds = _parse_seconds(default_duration)
    duration = _format_seconds(base_seconds)
    scenes = []
    for index, chunk in enumerate(chunks, start=1):
        scenes.append(
            _scene_dict(
                f"Scene {index}",
                duration,
                _default_visual_goal("main", index),
                chunk,
            )
        )
    return scenes
