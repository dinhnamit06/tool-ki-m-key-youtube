import re
from typing import List


SENTENCE_END_RE = re.compile(r'[.!?]["\']?$')
NEW_SENTENCE_HINT_RE = re.compile(
    r"^(?:I|We|You|He|She|They|It|This|That|There|Here|So|But|And|Then|Now|Well|Okay|Yes|No|What|Why|How|When|Where)\b|^[A-Z][a-z]+"
)


def _normalize_fragment(text: str) -> str:
    value = str(text or "")
    value = value.replace("\u200b", " ")
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\s+([,.;:!?])", r"\1", value)
    value = value.strip()
    if not value:
        return ""
    value = re.sub(r"\bi\b", "I", value)
    return value


def _capitalize_sentence(text: str) -> str:
    chars = list(text)
    for idx, char in enumerate(chars):
        if char.isalpha():
            chars[idx] = char.upper()
            break
    return "".join(chars)


def _finalize_sentence(text: str) -> str:
    sentence = _normalize_fragment(text)
    if not sentence:
        return ""
    sentence = _capitalize_sentence(sentence)
    if sentence.endswith((",", ";", ":")):
        sentence = sentence[:-1].rstrip()
    if not SENTENCE_END_RE.search(sentence):
        sentence = f"{sentence}."
    return sentence


def auto_punctuate_transcript(text: str) -> str:
    raw_lines = [_normalize_fragment(line) for line in str(text or "").splitlines()]
    lines = [line for line in raw_lines if line]
    if not lines:
        return ""

    sentences: List[str] = []
    buffer: List[str] = []

    for index, line in enumerate(lines):
        buffer.append(line)
        merged = " ".join(buffer).strip()
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        buffered_lines = len(buffer)

        end_mark = SENTENCE_END_RE.search(line) is not None
        next_starts_new = bool(NEW_SENTENCE_HINT_RE.match(next_line))
        long_enough = len(merged) >= 65
        too_long = len(merged) >= 110
        enough_caption_lines = buffered_lines >= 3 and len(merged) >= 55
        at_end = index == len(lines) - 1

        if end_mark or at_end or too_long or enough_caption_lines or (long_enough and next_starts_new):
            sentence = _finalize_sentence(merged)
            if sentence:
                sentences.append(sentence)
            buffer = []

    if buffer:
        sentence = _finalize_sentence(" ".join(buffer))
        if sentence:
            sentences.append(sentence)

    paragraphs: List[str] = []
    current: List[str] = []
    current_len = 0

    for sentence in sentences:
        current.append(sentence)
        current_len += len(sentence)
        if len(current) >= 2 or current_len >= 210:
            paragraphs.append(" ".join(current).strip())
            current = []
            current_len = 0

    if current:
        paragraphs.append(" ".join(current).strip())

    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)
