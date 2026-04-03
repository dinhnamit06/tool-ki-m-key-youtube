from utils.config import (
    GEMINI_HEADERS,
    OPENAI_MODEL,
    OPENAI_URL,
    ensure_gemini_api_key,
    ensure_openai_api_key,
    get_gemini_urls_for_model,
    get_openai_headers,
)
from utils.constants import REQUESTS_INSTALLED
try:
    import requests
except ImportError:
    pass


def _is_gemini_rate_limit_response(status_code, response_text):
    text = str(response_text or "").lower()
    return status_code == 429 or "resource_exhausted" in text or "quota" in text


def _generate_keywords_gemini(prompt, gemini_model=""):
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

    gemini_urls = get_gemini_urls_for_model(gemini_model)
    last_error = None

    for idx, url in enumerate(gemini_urls):
        try:
            response = requests.post(url, headers=GEMINI_HEADERS, json=data, timeout=35)
            if response.status_code >= 400:
                body_preview = response.text[:500]
                if idx < len(gemini_urls) - 1 and _is_gemini_rate_limit_response(response.status_code, body_preview):
                    continue
                response.raise_for_status()
            result_json = response.json()
            if "candidates" in result_json and len(result_json["candidates"]) > 0:
                content = result_json["candidates"][0]["content"]["parts"][0]["text"]
                return content
            return ""
        except Exception as exc:
            last_error = exc
            if idx < len(gemini_urls) - 1:
                continue
            raise

    if last_error is not None:
        raise last_error
    return ""


def _generate_keywords_openai(prompt, openai_model=""):
    if not REQUESTS_INSTALLED:
        raise ImportError("The 'requests' module is missing.")
    ensure_openai_api_key()

    data = {
        "model": (str(openai_model or "").strip() or OPENAI_MODEL),
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


def generate_keywords_api(prompt, provider="gemini", model_name=""):
    """
    Generate keyword text with selected provider.
    provider: gemini | gpt | auto
    """
    p = str(provider or "gemini").strip().lower()
    model = str(model_name or "").strip()

    if p == "gpt":
        return _generate_keywords_openai(prompt, openai_model=model)
    if p == "auto":
        try:
            return _generate_keywords_gemini(prompt, gemini_model=model)
        except Exception:
            return _generate_keywords_openai(prompt)
    return _generate_keywords_gemini(prompt, gemini_model=model)
