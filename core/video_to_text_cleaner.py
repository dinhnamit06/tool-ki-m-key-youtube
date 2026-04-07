import html
import re
from typing import List

from core.video_to_text_formatter import auto_punctuate_transcript


SAFE_FILLER_WORDS = {
    "uh",
    "um",
    "erm",
    "hmm",
    "mm",
    "ah",
    "eh",
}

STRONG_FILLER_PHRASES = (
    "you know",
    "i mean",
    "kind of",
    "sort of",
)

NOISE_LINE_RE = re.compile(
    r"^\s*(?:\[(?:music|applause|laughter|cheering|noise)\]|\((?:music|applause|laughter|cheering|noise)\)|music|applause|laughter|cheering)\s*$",
    re.IGNORECASE,
)


def _normalize_line(text: str, *, fix_noise: bool) -> str:
    value = html.unescape(str(text or ""))
    value = value.replace("\u200b", " ").replace("\xa0", " ")
    value = value.replace("♪", " ")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        return ""

    if fix_noise:
        value = value.replace("& amp", "&")
        value = value.replace("..", ".")
        value = re.sub(r"\s+([,.;:!?])", r"\1", value)
        value = re.sub(r"([,.;:!?])([A-Za-z])", r"\1 \2", value)
        value = re.sub(r"\b([A-Za-z]+)(?:\s+\1\b)+", r"\1", value, flags=re.IGNORECASE)
        value = re.sub(r"\b(\w+)-\1\b", r"\1", value, flags=re.IGNORECASE)
        value = re.sub(r"\s+", " ", value).strip()

    return value


def _remove_fillers(line: str, *, strong_cleanup: bool, preserve_meaning: bool) -> str:
    value = f" {line} "
    for word in SAFE_FILLER_WORDS:
        value = re.sub(rf"(?i)(?<![A-Za-z]){re.escape(word)}(?=[,.\s!?;:])", " ", value)

    if strong_cleanup and not preserve_meaning:
        for phrase in STRONG_FILLER_PHRASES:
            value = re.sub(rf"(?i)\b{re.escape(phrase)}\b", " ", value)

    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"\s+([,.;:!?])", r"\1", value)
    value = re.sub(r"^[,.;:!?-]+\s*", "", value)
    return value.strip()


def _line_signature(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "", str(text or "").lower())
    return value


def _dedupe_lines(lines: List[str], *, strong_cleanup: bool) -> List[str]:
    deduped: List[str] = []
    seen_signatures = set()
    previous_sig = ""

    for line in lines:
        sig = _line_signature(line)
        if not sig:
            continue
        if sig == previous_sig:
            continue
        if strong_cleanup and sig in seen_signatures and len(sig) <= 20:
            continue
        deduped.append(line)
        previous_sig = sig
        seen_signatures.add(sig)

    return deduped


def _paragraphize_lines(lines: List[str]) -> str:
    if not lines:
        return ""
    paragraphs: List[str] = []
    bucket: List[str] = []
    char_count = 0

    for line in lines:
        bucket.append(line)
        char_count += len(line)
        if len(bucket) >= 3 or char_count >= 220:
            paragraphs.append(" ".join(bucket).strip())
            bucket = []
            char_count = 0

    if bucket:
        paragraphs.append(" ".join(bucket).strip())

    return "\n\n".join(part for part in paragraphs if part)


def clean_script_text(
    text: str,
    *,
    mode: str = "Basic",
    output_style: str = "Readable Transcript",
    remove_filler_words: bool = True,
    remove_repeated_lines: bool = True,
    fix_spacing_and_noise: bool = True,
    preserve_original_meaning: bool = True,
) -> str:
    source_lines = [part for part in str(text or "").splitlines()]
    if not source_lines:
        return ""

    mode_name = str(mode or "Basic").strip()
    if mode_name == "AI Enhanced (Later)":
        mode_name = "Strong Cleanup"
    strong_cleanup = mode_name == "Strong Cleanup"

    cleaned_lines: List[str] = []
    for raw_line in source_lines:
        line = _normalize_line(raw_line, fix_noise=fix_spacing_and_noise)
        if not line:
            continue
        if NOISE_LINE_RE.match(line):
            continue
        if remove_filler_words:
            line = _remove_fillers(
                line,
                strong_cleanup=strong_cleanup,
                preserve_meaning=preserve_original_meaning,
            )
        line = _normalize_line(line, fix_noise=fix_spacing_and_noise)
        if line:
            cleaned_lines.append(line)

    if remove_repeated_lines:
        cleaned_lines = _dedupe_lines(cleaned_lines, strong_cleanup=strong_cleanup)

    if not cleaned_lines:
        return ""

    style = str(output_style or "Readable Transcript").strip()
    if style == "Minimal Cleanup":
        return "\n".join(cleaned_lines).strip()

    joined = "\n".join(cleaned_lines)
    punctuated = auto_punctuate_transcript(joined) if fix_spacing_and_noise else ""

    if style == "Clean Script":
        if punctuated.strip():
            return punctuated.strip()
        return _paragraphize_lines(cleaned_lines).strip()

    if punctuated.strip():
        return punctuated.strip()
    return _paragraphize_lines(cleaned_lines).strip()
