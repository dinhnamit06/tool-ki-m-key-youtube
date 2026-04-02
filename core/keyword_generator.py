from utils.constants import GEMINI_URL, GEMINI_HEADERS, REQUESTS_INSTALLED
try:
    import requests
except ImportError:
    pass

def generate_keywords_api(prompt):
    """
    Calls the Gemini API with the given prompt and returns the raw response text.
    """
    if not REQUESTS_INSTALLED:
        raise ImportError("The 'requests' module is missing.")

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
    else:
        return ""
