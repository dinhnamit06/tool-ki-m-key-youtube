import re
from typing import Dict, List

from core.video_to_text_formatter import auto_punctuate_transcript


CTA_HINT_RE = re.compile(
    r"\b(subscribe|comment|like|share|follow|watch next|check out|visit|download|click|let me know|thanks for watching|see you|"
    r"đăng ký|bình luận|chia sẻ|theo dõi|xem thêm|đừng quên|cảm ơn)\b",
    re.IGNORECASE,
)


def _normalize_text(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    if len(re.findall(r"[.!?]", raw)) < 2:
        punctuated = auto_punctuate_transcript(raw)
        if punctuated.strip():
            return punctuated.strip()
    return raw


def _split_sentences(text: str) -> List[str]:
    source = _normalize_text(text)
    if not source:
        return []
    parts = re.split(r"(?<=[.!?])\s+|\n+", source)
    cleaned: List[str] = []
    seen = set()
    for part in parts:
        sentence = re.sub(r"\s+", " ", str(part or "")).strip()
        if not sentence:
            continue
        sig = re.sub(r"[^a-z0-9]+", "", sentence.lower())
        if not sig or sig in seen:
            continue
        seen.add(sig)
        cleaned.append(sentence)
    return cleaned


def _sentence_score(sentence: str) -> float:
    text = str(sentence or "")
    score = 0.0
    if "?" in text or "!" in text:
        score += 1.6
    if re.search(r"\d", text):
        score += 0.8
    if len(text) > 45:
        score += 0.6
    if re.search(r"\b(why|how|what|best|secret|biggest|important|must|need)\b", text, re.IGNORECASE):
        score += 0.9
    return score


def extract_structure(text: str, *, mode: str = "Basic", prefer_cleaned: bool = True) -> Dict[str, object]:
    sentences = _split_sentences(text)
    if not sentences:
        return {"hook": "", "intro": "", "main_points": [], "cta": ""}

    mode_name = str(mode or "Basic").strip()
    if mode_name == "AI Enhanced (Later)":
        mode_name = "Detailed"

    cta_index = None
    for idx in range(len(sentences) - 1, -1, -1):
        if CTA_HINT_RE.search(sentences[idx]):
            cta_index = idx
            break
    if cta_index is None and len(sentences) >= 4:
        cta_index = len(sentences) - 1

    hook_window = sentences[: min(3, len(sentences))]
    hook = max(hook_window, key=_sentence_score) if hook_window else sentences[0]
    hook_index = sentences.index(hook)

    intro_indexes: List[int] = []
    for idx in range(min(len(sentences), 4)):
        if idx == hook_index or idx == cta_index:
            continue
        intro_indexes.append(idx)
        if len(intro_indexes) >= (2 if mode_name == "Detailed" else 1):
            break
    intro = " ".join(sentences[idx] for idx in intro_indexes).strip()

    excluded = {hook_index}
    excluded.update(intro_indexes)
    if cta_index is not None:
        excluded.add(cta_index)

    body_sentences = [sentences[idx] for idx in range(len(sentences)) if idx not in excluded]
    max_points = 5 if mode_name == "Detailed" else 3
    main_points = body_sentences[:max_points]

    if not intro and body_sentences:
        intro = body_sentences[0]
        main_points = body_sentences[1:max_points + 1]

    cta = sentences[cta_index] if cta_index is not None and 0 <= cta_index < len(sentences) else ""

    if not cta and len(sentences) >= 2:
        cta = sentences[-1]
        if cta in main_points:
            main_points = [point for point in main_points if point != cta]

    if not main_points:
        fallback = [sentence for sentence in sentences if sentence not in {hook, intro, cta}]
        main_points = fallback[:max_points]

    return {
        "hook": hook.strip(),
        "intro": intro.strip(),
        "main_points": [point.strip() for point in main_points if point.strip()],
        "cta": cta.strip(),
    }


def format_structure_output(structure: Dict[str, object]) -> str:
    hook = str(structure.get("hook", "")).strip()
    intro = str(structure.get("intro", "")).strip()
    cta = str(structure.get("cta", "")).strip()
    main_points = [str(item).strip() for item in (structure.get("main_points", []) or []) if str(item).strip()]

    lines: List[str] = []
    lines.append("Hook:")
    lines.append(hook or "not-given")
    lines.append("")
    lines.append("Intro:")
    lines.append(intro or "not-given")
    lines.append("")
    lines.append("Main Points:")
    if main_points:
        for idx, point in enumerate(main_points, start=1):
            lines.append(f"{idx}. {point}")
    else:
        lines.append("not-given")
    lines.append("")
    lines.append("CTA:")
    lines.append(cta or "not-given")
    return "\n".join(lines).strip()
