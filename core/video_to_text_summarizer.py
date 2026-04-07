import re
from collections import Counter
from typing import List

from core.video_to_text_formatter import auto_punctuate_transcript


COMMON_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "at", "for", "with",
    "from", "by", "is", "are", "was", "were", "be", "been", "being", "it", "this",
    "that", "these", "those", "i", "you", "we", "they", "he", "she", "them", "our",
    "your", "his", "her", "their", "as", "if", "so", "then", "than", "too", "very",
    "do", "does", "did", "have", "has", "had", "can", "could", "will", "would", "should",
    "một", "những", "các", "và", "là", "của", "cho", "với", "trong", "đó", "này", "thì",
    "khi", "để", "được", "đang", "rất", "nhiều", "có", "không", "mình", "mọi", "người",
}


def _normalize_source_text(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    punct_count = len(re.findall(r"[.!?]", raw))
    if punct_count < 2:
        normalized = auto_punctuate_transcript(raw)
        if normalized.strip():
            return normalized.strip()
    return raw


def _split_sentences(text: str) -> List[str]:
    source = _normalize_source_text(text)
    if not source:
        return []
    parts = re.split(r"(?<=[.!?])\s+|\n+", source)
    cleaned: List[str] = []
    seen = set()
    for part in parts:
        sentence = re.sub(r"\s+", " ", str(part or "")).strip()
        if not sentence:
            continue
        signature = re.sub(r"[^a-z0-9]+", "", sentence.lower())
        if not signature or signature in seen:
            continue
        seen.add(signature)
        cleaned.append(sentence)
    return cleaned


def _tokenize(sentence: str) -> List[str]:
    return re.findall(r"[A-Za-zÀ-ỹ0-9][A-Za-zÀ-ỹ0-9'-]*", str(sentence or "").lower())


def _sentence_count_for_length(length: str) -> int:
    mapping = {
        "Short": 2,
        "Medium": 4,
        "Detailed": 6,
    }
    return mapping.get(str(length or "").strip(), 3)


def summarize_text(
    text: str,
    *,
    mode: str = "Short Summary",
    length: str = "Medium",
    keep_names_and_keywords: bool = True,
) -> str:
    sentences = _split_sentences(text)
    if not sentences:
        return ""

    content_words: List[str] = []
    for sentence in sentences:
        for token in _tokenize(sentence):
            if len(token) <= 2:
                continue
            if token in COMMON_STOPWORDS:
                continue
            content_words.append(token)
    freq = Counter(content_words)

    scored = []
    for idx, sentence in enumerate(sentences):
        tokens = _tokenize(sentence)
        score = 0.0
        for token in tokens:
            if len(token) <= 2 or token in COMMON_STOPWORDS:
                continue
            score += freq.get(token, 0)
        length_bonus = 1.0 if 35 <= len(sentence) <= 220 else 0.2
        position_bonus = max(0.0, 1.2 - (idx * 0.08))
        proper_noun_bonus = 0.0
        if keep_names_and_keywords and re.search(r"\b[A-ZÀ-Ỹ][a-zà-ỹA-ZÀ-Ỹ0-9]+\b", sentence):
            proper_noun_bonus = 0.8
        digit_bonus = 0.5 if re.search(r"\d", sentence) else 0.0
        score += length_bonus + position_bonus + proper_noun_bonus + digit_bonus
        scored.append((idx, score, sentence))

    wanted = min(max(1, _sentence_count_for_length(length)), len(scored))
    top = sorted(scored, key=lambda item: item[1], reverse=True)[:wanted]
    selected = [sentence for _, _, sentence in sorted(top, key=lambda item: item[0])]

    mode_name = str(mode or "").strip()
    if mode_name == "Bullet Summary":
        return "\n".join(f"- {sentence}" for sentence in selected).strip()
    if mode_name == "Key Takeaways":
        return "\n".join(f"- Key takeaway: {sentence}" for sentence in selected).strip()
    return " ".join(selected).strip()
