import random
import re

from utils.config import GEMINI_HEADERS, ensure_gemini_api_key, get_gemini_urls_for_model
from utils.constants import REQUESTS_INSTALLED

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


def _is_gemini_rate_limit_response(status_code, response_text):
    text = str(response_text or "").lower()
    return status_code == 429 or "resource_exhausted" in text or "quota" in text


def _normalize_topic(keyword_text):
    topic = re.sub(r"\s+", " ", str(keyword_text or "")).strip()
    variants = [part.strip() for part in re.split(r"[,;/|]+", topic) if part.strip()]
    primary = variants[0] if variants else topic
    secondary = variants[1] if len(variants) > 1 else primary
    return topic, primary, secondary


def build_local_titles(keyword_text, target_count):
    topic, primary, secondary = _normalize_topic(keyword_text)
    if not topic:
        return []

    numbers = [3, 5, 7, 9, 10, 12, 15]
    hooks = [
        "Beginners Need to Know",
        "That Actually Works",
        "Most People Ignore",
        "You Can Try Today",
        "Without Wasting Time",
        "For Fast Results",
        "Step by Step",
        "Like a Pro",
    ]
    templates = [
        "Breaking News: {topic}",
        "{n} {topic} Tips That Actually Work",
        "{n} Mistakes to Avoid in {topic}",
        "How to Start {topic} for Beginners",
        "The Ultimate {topic} Guide ({n} Steps)",
        "{n} Secrets of {topic} You Should Know",
        "Why Your {topic} Is Not Working ({n} Fixes)",
        "Top {n} {topic} Ideas for This Year",
        "{topic} vs {secondary}: Which One Is Better?",
        "I Tried {topic} for {n} Days - Here's What Happened",
        "{n} Proven Ways to Improve {topic}",
        "How to Master {topic} in {n} Simple Steps",
        "Stop Doing This in {topic} ({n} Big Mistakes)",
        "{n} Powerful {topic} Hacks for Beginners",
        "{topic}: {hook}",
        "The Truth About {topic} ({n} Things Nobody Tells You)",
        "{n} Smart {topic} Strategies to Grow Faster",
        "Can You Really Improve {topic}? ({n} Real Tips)",
        "{n} Best Tools for {topic}",
        "How to Get Better at {topic} Without Stress",
    ]

    rng = random.Random()
    titles = []
    seen = set()
    max_attempts = max(80, int(target_count) * 20)
    for _ in range(max_attempts):
        tpl = rng.choice(templates)
        title = tpl.format(
            topic=primary,
            secondary=secondary,
            n=rng.choice(numbers),
            hook=rng.choice(hooks),
        )
        title = re.sub(r"\s+", " ", title).strip(" -")
        key = title.lower()
        if not title or key in seen:
            continue
        seen.add(key)
        titles.append(title)
        if len(titles) >= int(target_count):
            break

    if len(titles) < int(target_count):
        idx = 1
        while len(titles) < int(target_count):
            fallback = f"{idx} Ways to Improve {primary}"
            if fallback.lower() not in seen:
                seen.add(fallback.lower())
                titles.append(fallback)
            idx += 1
    return titles


def _parse_ai_titles(raw_text, target_count):
    lines = []
    seen = set()
    for raw_line in str(raw_text or "").splitlines():
        text = str(raw_line or "").strip()
        text = re.sub(r"^\s*(?:[-*•]+|\d+[\).\:-])\s*", "", text)
        text = text.strip().strip('"').strip("'")
        text = re.sub(r"\s+", " ", text)
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        if len(text) < 6:
            continue
        seen.add(lowered)
        lines.append(text)
        if len(lines) >= int(target_count):
            break
    return lines


def generate_ai_titles(keyword_text, target_count, model_name="gemini-2.5-flash-lite"):
    if not REQUESTS_INSTALLED or requests is None:
        raise ImportError("The 'requests' module is missing.")
    ensure_gemini_api_key()

    topic, primary, secondary = _normalize_topic(keyword_text)
    if not topic:
        return []

    prompt = (
        "You are a YouTube title strategist.\n"
        f"Create exactly {int(target_count)} unique YouTube video titles for the topic: {topic}.\n"
        f"Primary keyword: {primary}.\n"
        f"Secondary keyword: {secondary}.\n"
        "Rules:\n"
        "- Make them clickable but not spammy.\n"
        "- Mix formats: listicle, how-to, curiosity, myth-busting, tutorial, comparison, beginner, mistake, and case study.\n"
        "- Keep most titles between 35 and 80 characters.\n"
        "- Keep the main topic visible naturally in each title.\n"
        "- Avoid duplicates and near-duplicates.\n"
        "- No hashtags.\n"
        "- No quotation marks around titles.\n"
        "- No numbering list prefix in the output.\n"
        "- Return only the titles, one per line.\n"
    )

    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.9,
            "topP": 0.95,
        },
    }

    gemini_urls = get_gemini_urls_for_model(model_name)
    last_error = None

    for idx, url in enumerate(gemini_urls):
        try:
            response = requests.post(url, headers=GEMINI_HEADERS, json=data, timeout=40)
            if response.status_code >= 400:
                body_preview = response.text[:500]
                if idx < len(gemini_urls) - 1 and _is_gemini_rate_limit_response(response.status_code, body_preview):
                    continue
                response.raise_for_status()
            result_json = response.json()
            candidates = result_json.get("candidates", [])
            if not candidates:
                continue
            parts = candidates[0].get("content", {}).get("parts", [])
            content = "\n".join(str(part.get("text", "")) for part in parts if str(part.get("text", "")).strip())
            titles = _parse_ai_titles(content, target_count)
            if len(titles) < int(target_count):
                local_titles = build_local_titles(topic, target_count)
                for title in local_titles:
                    if len(titles) >= int(target_count):
                        break
                    if title.lower() not in {item.lower() for item in titles}:
                        titles.append(title)
            return titles[: int(target_count)]
        except Exception as exc:
            last_error = exc
            if idx < len(gemini_urls) - 1:
                continue
            raise

    if last_error is not None:
        raise last_error
    return build_local_titles(topic, target_count)
