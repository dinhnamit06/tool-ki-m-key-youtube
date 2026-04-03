from utils.config import (
    GEMINI_HEADERS,
    GEMINI_URL,
    OPENAI_MODEL,
    OPENAI_URL,
    ensure_gemini_api_key,
    ensure_openai_api_key,
    get_openai_headers,
)
from utils.constants import REQUESTS_INSTALLED
try:
    import requests
except ImportError:
    pass

def _generate_keywords_gemini(prompt):
    if not REQUESTS_INSTALLED:
        raise ImportError("The 'requests' module is missing.")
    ensure_gemini_api_key()

    data = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.7
        }
    }
    
    response = requests.post(GEMINI_URL, headers=GEMINI_HEADERS, json=data, timeout=35)
    response.raise_for_status()
    
    result_json = response.json()
    
    if "candidates" in result_json and len(result_json["candidates"]) > 0:
        content = result_json["candidates"][0]["content"]["parts"][0]["text"]
        return content
    return ""


def _generate_keywords_openai(prompt):
    if not REQUESTS_INSTALLED:
        raise ImportError("The 'requests' module is missing.")
    ensure_openai_api_key()

    data = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
    }
    response = requests.post(OPENAI_URL, headers=get_openai_headers(), json=data, timeout=45)
    response.raise_for_status()
    result_json = response.json()

    choices = result_json.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    return str(message.get("content", "")).strip()


def generate_keywords_api(prompt, provider="gemini"):
    """
    Generate keyword text with selected provider.
    provider: gemini | gpt | auto
    """
    p = str(provider or "gemini").strip().lower()

    if p == "gpt":
        return _generate_keywords_openai(prompt)
    if p == "auto":
        try:
            return _generate_keywords_gemini(prompt)
        except Exception:
            return _generate_keywords_openai(prompt)
    return _generate_keywords_gemini(prompt)
