from urllib.parse import urlparse


def _build_proxy_candidates(text):
    raw = str(text or "").strip()
    if not raw:
        return []

    candidates = [raw]
    if "://" not in raw:
        candidates.append(f"http://{raw}")

    # Common 4-part formats:
    # 1) host:port:user:pass
    # 2) user:pass:host:port
    if "@" not in raw:
        parts = raw.split(":")
        if len(parts) == 4:
            p1, p2, p3, p4 = parts
            if p2.isdigit():
                candidates.append(f"http://{p3}:{p4}@{p1}:{p2}")
            if p4.isdigit():
                candidates.append(f"http://{p1}:{p2}@{p3}:{p4}")

    return candidates


def normalize_proxy(proxy_text):
    text = str(proxy_text or "").strip()
    if not text:
        return ""

    for candidate in _build_proxy_candidates(text):
        parsed = urlparse(candidate)
        if not parsed.hostname or not parsed.port:
            continue

        scheme = parsed.scheme or "http"
        auth = ""
        if parsed.username:
            auth = parsed.username
            if parsed.password is not None:
                auth += f":{parsed.password}"
            auth += "@"
        return f"{scheme}://{auth}{parsed.hostname}:{parsed.port}"

    return ""


def parse_proxy_lines(text):
    seen = set()
    output = []
    for line in str(text or "").splitlines():
        normalized = normalize_proxy(line)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(normalized)
    return output


def to_requests_proxies(proxy_url):
    proxy = normalize_proxy(proxy_url)
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}
