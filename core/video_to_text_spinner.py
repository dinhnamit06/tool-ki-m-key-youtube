import re
from typing import Dict, List


SPIN_REPLACEMENTS: Dict[str, List[str]] = {
    "important": ["key", "notable", "major"],
    "good": ["solid", "strong", "positive"],
    "bad": ["poor", "weak", "negative"],
    "big": ["large", "major", "significant"],
    "small": ["minor", "compact", "smaller"],
    "look": ["appear", "look", "seem"],
    "really": ["truly", "really", "genuinely"],
    "very": ["quite", "very", "highly"],
    "maybe": ["perhaps", "maybe", "possibly"],
    "also": ["also", "as well", "in addition"],
    "because": ["because", "since", "as"],
    "so": ["so", "therefore", "as a result"],
    "buy": ["purchase", "buy"],
    "sell": ["sell", "trade"],
    "easy": ["simple", "easy", "straightforward"],
    "hard": ["difficult", "hard", "challenging"],
}

STARTER_REPLACEMENTS = {
    "but": ["But", "Still", "Even so"],
    "and": ["And", "Plus", "Also"],
    "so": ["So", "As a result", "That means"],
    "because": ["Because", "Since", "As"],
    "then": ["Then", "Next", "After that"],
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "at", "for",
    "with", "from", "by", "is", "are", "was", "were", "be", "been", "being",
    "it", "this", "that", "these", "those", "i", "you", "we", "they", "he", "she",
}


def _split_sentences(text: str) -> List[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    raw = re.sub(r"\r\n?", "\n", raw)
    parts = re.split(r'(?<=[.!?])\s+|\n{2,}', raw)
    sentences = [part.strip() for part in parts if part and part.strip()]
    if not sentences and raw:
        return [raw]
    return sentences


def _pick_variant(options: List[str], index: int) -> str:
    if not options:
        return ""
    return options[index % len(options)]


def _replace_words(sentence: str, intensity: int, preserve_meaning: bool, keep_keywords: bool) -> str:
    if not preserve_meaning:
        intensity += 1

    protected = set()
    if keep_keywords:
        for token in re.findall(r"\b[A-Za-z][A-Za-z-]{4,}\b", sentence):
            token_l = token.lower()
            if token_l not in STOPWORDS:
                protected.add(token_l)
                if len(protected) >= 3:
                    break

    def repl(match):
        word = match.group(0)
        key = word.lower()
        if key in protected:
            return word
        choices = SPIN_REPLACEMENTS.get(key)
        if not choices:
            return word
        variant = _pick_variant(choices, intensity)
        if word[0].isupper():
            variant = variant[:1].upper() + variant[1:]
        return variant

    return re.sub(r"\b[A-Za-z][A-Za-z'-]*\b", repl, sentence)


def _replace_starter(sentence: str, intensity: int) -> str:
    parts = sentence.split(None, 1)
    if not parts:
        return sentence
    starter = parts[0].strip(", ").lower()
    if starter not in STARTER_REPLACEMENTS:
        return sentence
    replacement = _pick_variant(STARTER_REPLACEMENTS[starter], intensity)
    rest = parts[1] if len(parts) > 1 else ""
    if rest:
        return f"{replacement} {rest}"
    return replacement


def _cleanup_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"([.!?])([A-Za-z])", r"\1 \2", cleaned)
    return cleaned.strip()


def spin_content(
    text: str,
    *,
    mode: str = "Basic",
    strength: str = "Light",
    preserve_meaning: bool = True,
    avoid_repetition: bool = True,
    keep_keywords: bool = True,
) -> str:
    sentences = _split_sentences(text)
    if not sentences:
        return ""

    strength_map = {"Light": 0, "Medium": 1, "Strong": 2}
    intensity = strength_map.get(strength, 0)
    mode_name = str(mode or "Basic").strip()
    if mode_name == "AI Enhanced (Later)":
        mode_name = "Basic"

    spun_sentences: List[str] = []
    previous = ""

    for idx, sentence in enumerate(sentences):
        current = sentence
        current = _replace_words(current, intensity + idx, preserve_meaning, keep_keywords)
        if mode_name in {"Sentence Spin", "Paragraph Spin"}:
            current = _replace_starter(current, intensity + idx)
        current = _cleanup_text(current)
        if avoid_repetition and current == previous:
            current = _replace_starter(current, intensity + idx + 1)
            current = _cleanup_text(current)
        spun_sentences.append(current)
        previous = current

    if mode_name == "Paragraph Spin":
        paragraphs: List[str] = []
        bucket: List[str] = []
        for sentence in spun_sentences:
            bucket.append(sentence)
            if len(bucket) >= 2:
                paragraphs.append(" ".join(bucket).strip())
                bucket = []
        if bucket:
            paragraphs.append(" ".join(bucket).strip())
        return "\n\n".join(paragraphs).strip()

    return "\n".join(spun_sentences).strip()
