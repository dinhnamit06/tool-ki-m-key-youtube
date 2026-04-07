import json
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse, urlsplit, urlunsplit

from PyQt6.QtCore import QThread, pyqtSignal

from core.videos_fetcher import _http_get

try:
    import yt_dlp
except ImportError:  # pragma: no cover
    yt_dlp = None


YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_URL_RE = re.compile(
    r"(https?://(?:www\.)?(?:youtube\.com/watch\?[^\"'\s<>]+|youtu\.be/[A-Za-z0-9_-]{11}[^\"'\s<>]*))",
    re.IGNORECASE,
)
BROWSER_COOKIE_SOURCES = ["chrome", "edge", "firefox", "brave", "opera", "vivaldi"]
ALT_PLAYER_CLIENT_SETS = [
    ("android", ["android"]),
    ("android+tv", ["android", "tv_embedded"]),
    ("tv_embedded", ["tv_embedded"]),
]


def normalize_video_text_input(raw_text: str) -> str:
    raw = str(raw_text or "").strip()
    if not raw:
        return ""
    matched_url = YOUTUBE_URL_RE.search(raw)
    if matched_url:
        candidate = matched_url.group(1).strip()
        if "youtu.be/" in candidate:
            parsed = urlparse(candidate)
            video_id = parsed.path.strip("/").split("/")[0]
            if YOUTUBE_ID_RE.fullmatch(video_id):
                return f"https://www.youtube.com/watch?v={video_id}"
        parsed = urlparse(candidate)
        if "youtube.com" in (parsed.netloc or ""):
            query_id = parse_qs(parsed.query or "").get("v", [""])[0].strip()
            if YOUTUBE_ID_RE.fullmatch(query_id):
                return f"https://www.youtube.com/watch?v={query_id}"
        return candidate
    if "watch?v=" in raw:
        parsed = urlparse(raw)
        query_id = parse_qs(parsed.query or "").get("v", [""])[0].strip()
        if YOUTUBE_ID_RE.fullmatch(query_id):
            return f"https://www.youtube.com/watch?v={query_id}"
    if YOUTUBE_ID_RE.fullmatch(raw):
        return f"https://www.youtube.com/watch?v={raw}"
    return raw


def _clean_caption_text(value: str) -> str:
    text = unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\u200b", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _dedupe_lines(lines: List[str]) -> str:
    cleaned: List[str] = []
    previous = ""
    for line in lines:
        line = _clean_caption_text(line)
        if not line:
            continue
        if line == previous:
            continue
        cleaned.append(line)
        previous = line
    return "\n".join(cleaned).strip()


def _response_text_utf8(response) -> str:
    try:
        data = bytes(getattr(response, "content", b"") or b"")
        if data:
            return data.decode("utf-8", errors="replace")
    except Exception:
        pass
    return str(getattr(response, "text", "") or "")


def _parse_json3_text(body: str) -> str:
    payload = json.loads(body or "{}")
    events = payload.get("events", []) if isinstance(payload, dict) else []
    lines: List[str] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        segments = event.get("segs", [])
        if not isinstance(segments, list):
            continue
        text = "".join(str(seg.get("utf8", "")) for seg in segments if isinstance(seg, dict))
        if text.strip():
            lines.append(text)
    return _dedupe_lines(lines)


def _parse_vtt_text(body: str) -> str:
    lines: List[str] = []
    buffer: List[str] = []
    for raw_line in str(body or "").splitlines():
        line = raw_line.strip("\ufeff").rstrip()
        if not line.strip():
            if buffer:
                lines.append(" ".join(buffer))
                buffer = []
            continue
        if line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if "-->" in line:
            continue
        if line.isdigit():
            continue
        buffer.append(line.strip())
    if buffer:
        lines.append(" ".join(buffer))
    return _dedupe_lines(lines)


def _parse_xml_caption_text(body: str) -> str:
    root = ET.fromstring(body or "<transcript/>")
    lines = []
    for node in root.iter():
        if node.tag.endswith("text"):
            if node.text and node.text.strip():
                lines.append(node.text)
    return _dedupe_lines(lines)


def _parse_caption_body(body: str, caption_format: str) -> str:
    if _looks_like_html_payload(body):
        return ""
    fmt = str(caption_format or "").lower()
    try:
        if fmt == "json3":
            return _parse_json3_text(body)
        if fmt in {"vtt", "webvtt"}:
            return _parse_vtt_text(body)
        if fmt.startswith("srv") or fmt in {"ttml", "xml"}:
            return _parse_xml_caption_text(body)
    except Exception:
        pass
    for fallback in (_parse_json3_text, _parse_vtt_text, _parse_xml_caption_text):
        try:
            text = fallback(body)
            if text:
                return text
        except Exception:
            continue
    return ""


def _pick_caption_track(info: Dict) -> Dict:
    subtitles = info.get("subtitles", {}) or {}
    auto_captions = info.get("automatic_captions", {}) or {}
    preferred_langs = []
    info_lang = str(info.get("language", "")).strip()
    if info_lang:
        preferred_langs.append(info_lang)
    preferred_langs.extend(["vi", "vi-VN", "en", "en-US", "en-GB"])
    preferred_formats = ["json3", "srv3", "vtt", "srv1", "ttml"]

    def _find_track(source_name: str, payload: Dict) -> Dict:
        if not isinstance(payload, dict):
            return {}
        candidate_langs = preferred_langs + [lang for lang in payload.keys() if lang not in preferred_langs]
        for lang in candidate_langs:
            tracks = payload.get(lang, [])
            if not isinstance(tracks, list):
                continue
            for preferred_fmt in preferred_formats:
                for track in tracks:
                    if not isinstance(track, dict):
                        continue
                    if str(track.get("ext", "")).lower() == preferred_fmt and str(track.get("url", "")).strip():
                        return {
                            "source": source_name,
                            "language": lang,
                            "format": preferred_fmt,
                            "url": str(track.get("url", "")).strip(),
                        }
            for track in tracks:
                if not isinstance(track, dict):
                    continue
                if str(track.get("url", "")).strip():
                    return {
                        "source": source_name,
                        "language": lang,
                        "format": str(track.get("ext", "")).lower(),
                        "url": str(track.get("url", "")).strip(),
                    }
        return {}

    return _find_track("subtitles", subtitles) or _find_track("auto-captions", auto_captions)


def _extract_video_id(video_url: str) -> str:
    normalized = normalize_video_text_input(video_url)
    if not normalized:
        return ""
    if YOUTUBE_ID_RE.fullmatch(normalized):
        return normalized
    parsed = urlparse(normalized)
    query_id = parse_qs(parsed.query or "").get("v", [""])[0].strip()
    if YOUTUBE_ID_RE.fullmatch(query_id):
        return query_id
    if "youtu.be" in (parsed.netloc or ""):
        short_id = parsed.path.strip("/").split("/")[0]
        if YOUTUBE_ID_RE.fullmatch(short_id):
            return short_id
    return ""


def _looks_like_html_payload(body: str) -> bool:
    sample = str(body or "")[:5000].lower()
    return any(
        marker in sample
        for marker in (
            "<!doctype html",
            "<html",
            "window.wiz_global_data",
            "window.ytcfg",
            "var ytcfg=",
            "ytcfg.set(",
            "<script",
            "<body",
        )
    )


def _extract_json_blob(page_html: str, marker: str) -> Optional[str]:
    marker_index = str(page_html or "").find(marker)
    if marker_index < 0:
        return None

    start = page_html.find("{", marker_index)
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for idx in range(start, len(page_html)):
        ch = page_html[idx]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
            continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                return page_html[start : idx + 1]
    return None


def _caption_url_with_format(base_url: str, fmt: str) -> str:
    raw = str(base_url or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    query_pairs = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() != "fmt"]
    if fmt:
        query_pairs.append(("fmt", fmt))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query_pairs), parts.fragment))


def _build_info_from_player_response(player: Dict, video_url: str) -> Dict:
    if not isinstance(player, dict):
        return {}
    video_details = player.get("videoDetails", {}) or {}
    captions_payload = (
        player.get("captions", {}) or {}
    ).get("playerCaptionsTracklistRenderer", {}) or {}
    caption_tracks = captions_payload.get("captionTracks", []) or []
    subtitles: Dict[str, List[Dict[str, str]]] = {}
    automatic_captions: Dict[str, List[Dict[str, str]]] = {}

    for raw_track in caption_tracks:
        if not isinstance(raw_track, dict):
            continue
        base_url = str(raw_track.get("baseUrl", "")).strip()
        if not base_url:
            continue
        lang = str(raw_track.get("languageCode", "")).strip() or "unknown"
        is_auto = str(raw_track.get("kind", "")).strip().lower() == "asr" or str(raw_track.get("vssId", "")).strip().lower().startswith("a.")
        target = automatic_captions if is_auto else subtitles
        bucket = target.setdefault(lang, [])
        seen_urls = {str(item.get("url", "")).strip() for item in bucket if isinstance(item, dict)}
        for ext in ("json3", "srv3", "vtt"):
            url = _caption_url_with_format(base_url, ext)
            if url and url not in seen_urls:
                bucket.append({"ext": ext, "url": url})
                seen_urls.add(url)
        if base_url not in seen_urls:
            bucket.append({"ext": "", "url": base_url})

    primary_language = ""
    audio_tracks = captions_payload.get("audioTracks", []) or []
    if isinstance(audio_tracks, list):
        for audio_track in audio_tracks:
            if not isinstance(audio_track, dict):
                continue
            if audio_track.get("visibility") or audio_track.get("defaultAudioTrack"):
                primary_language = str(audio_track.get("captionTrackIndices", [""])[0] if audio_track.get("captionTrackIndices") else "").strip()
                break

    return {
        "id": _extract_video_id(video_url),
        "title": str(video_details.get("title", "")).strip(),
        "language": primary_language,
        "subtitles": subtitles,
        "automatic_captions": automatic_captions,
    }


def _load_info_from_watch_page(video_url: str, status_callback=None) -> Dict:
    video_id = _extract_video_id(video_url)
    if not video_id:
        return {}

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    watch_url = "https://www.youtube.com/watch"
    params = {"v": video_id, "hl": "en", "bpctr": "9999999999", "has_verified": "1"}
    try:
        if status_callback:
            status_callback("Retrying by parsing captions from watch page...")
        response = _http_get(watch_url, params=params, headers=headers, timeout=25)
        response.raise_for_status()
    except Exception:
        return {}

    page_html = _response_text_utf8(response)
    for marker in (
        "var ytInitialPlayerResponse = ",
        'window["ytInitialPlayerResponse"] = ',
        "ytInitialPlayerResponse = ",
    ):
        blob = _extract_json_blob(page_html, marker)
        if not blob:
            continue
        try:
            player = json.loads(blob)
        except json.JSONDecodeError:
            continue
        info = _build_info_from_player_response(player, video_url)
        if info:
            return info
    return {}


def _download_caption_via_ydlp(
    video_url: str,
    track: Dict,
    *,
    browser: str = "",
    player_clients: Optional[List[str]] = None,
) -> str:
    if yt_dlp is None:
        return ""

    language = str(track.get("language", "")).strip() or "en"
    with tempfile.TemporaryDirectory(prefix="tubevibe_caption_") as tmpdir:
        outtmpl = os.path.join(tmpdir, "caption.%(ext)s")
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "no_warnings": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": [language],
            "subtitlesformat": "json3/srv3/vtt/best",
            "outtmpl": outtmpl,
        }
        if browser:
            ydl_opts["cookiesfrombrowser"] = (browser,)
        if player_clients:
            ydl_opts["extractor_args"] = {"youtube": {"player_client": list(player_clients)}}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        candidates = sorted(Path(tmpdir).glob("caption*"))
        for path in candidates:
            if not path.is_file():
                continue
            ext = path.suffix.lstrip(".").lower()
            try:
                body = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if _looks_like_html_payload(body):
                continue
            transcript = _parse_caption_body(body, ext)
            if transcript.strip():
                return transcript
    return ""


def _extract_info_with_ydlp(video_url: str, *, browser: str = "", player_clients: Optional[List[str]] = None) -> Dict:
    if yt_dlp is None:
        raise ImportError("Dependency Error: yt-dlp is missing. Run: pip install yt-dlp")
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "no_warnings": True,
        "extract_flat": False,
    }
    if browser:
        ydl_opts["cookiesfrombrowser"] = (browser,)
    if player_clients:
        ydl_opts["extractor_args"] = {"youtube": {"player_client": list(player_clients)}}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(video_url, download=False)


def _looks_like_bot_check(message: str) -> bool:
    raw = str(message or "").lower()
    return any(
        needle in raw
        for needle in (
            "confirm you're not a bot",
            "cookies-from-browser",
            "use --cookies",
            "sign in to confirm",
            "http error 429",
            "too many requests",
        )
    )


def fetch_video_transcript(video_url: str, status_callback=None) -> Dict[str, str]:
    normalized_url = normalize_video_text_input(video_url)
    if not normalized_url:
        raise ValueError("Please enter a YouTube video link or ID.")

    info: Optional[Dict] = None
    last_error = ""
    tried_cookie_browsers: List[str] = []
    used_browser = ""
    used_client_label = ""
    used_player_clients: List[str] = []

    try:
        if status_callback:
            status_callback("Loading video metadata...")
        info = _extract_info_with_ydlp(normalized_url)
    except Exception as exc:
        last_error = str(exc)
        if not _looks_like_bot_check(last_error):
            raise

        for client_label, player_clients in ALT_PLAYER_CLIENT_SETS:
            try:
                if status_callback:
                    status_callback(f"Retrying with YouTube client: {client_label}...")
                info = _extract_info_with_ydlp(normalized_url, player_clients=player_clients)
                used_client_label = client_label
                used_player_clients = list(player_clients)
                last_error = ""
                break
            except Exception as alt_exc:
                last_error = str(alt_exc)
                continue

        if not info:
            for browser in BROWSER_COOKIE_SOURCES:
                tried_cookie_browsers.append(browser)
                try:
                    if status_callback:
                        status_callback(f"Retrying with {browser.title()} cookies...")
                    info = _extract_info_with_ydlp(normalized_url, browser=browser)
                    used_browser = browser
                    last_error = ""
                    break
                except Exception as cookie_exc:
                    last_error = str(cookie_exc)
                if not info:
                    for client_label, player_clients in ALT_PLAYER_CLIENT_SETS:
                        try:
                            if status_callback:
                                status_callback(f"Retrying with {browser.title()} cookies + {client_label} client...")
                            info = _extract_info_with_ydlp(normalized_url, browser=browser, player_clients=player_clients)
                            used_browser = browser
                            used_client_label = client_label
                            used_player_clients = list(player_clients)
                            last_error = ""
                            break
                        except Exception as combo_exc:
                            last_error = str(combo_exc)
                            continue
                if info:
                    break

        if not info:
            info = _load_info_from_watch_page(normalized_url, status_callback=status_callback)
            if info:
                last_error = ""

    if not info:
        if tried_cookie_browsers:
            raise RuntimeError(
                "YouTube requested sign-in/bot verification. Automatic retries with browser cookies failed "
                f"({', '.join(browser.title() for browser in tried_cookie_browsers)}). "
                "Open the same video in your browser, make sure you are logged in and can view it normally, "
                "then try again."
            )
        raise RuntimeError(last_error or "Could not load YouTube video metadata.")

    track = _pick_caption_track(info)
    if not track:
        source_hint = f" (client: {used_client_label})" if used_client_label else ""
        raise RuntimeError(f"No subtitles or auto-captions were found for this video{source_hint}.")

    response = _http_get(
        track["url"],
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        },
        timeout=25,
    )
    response.raise_for_status()
    caption_body = response.text
    transcript = _parse_caption_body(caption_body, track.get("format", ""))
    if not transcript and _looks_like_html_payload(caption_body):
        if status_callback:
            status_callback("Caption endpoint returned HTML. Retrying with yt-dlp subtitle download...")
        transcript = _download_caption_via_ydlp(
            normalized_url,
            track,
            browser=used_browser,
            player_clients=used_player_clients,
        )
    if not transcript:
        raise RuntimeError("Transcript track was found, but it could not be parsed.")

    return {
        "ok": True,
        "title": str(info.get("title", "")).strip(),
        "video_url": normalized_url,
        "transcript": transcript,
        "language": str(track.get("language", "")).strip() or "unknown",
        "caption_source": str(track.get("source", "")).strip() or "captions",
    }


class VideoToTextWorker(QThread):
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(dict)

    def __init__(self, video_url: str):
        super().__init__()
        self.video_url = str(video_url or "").strip()
        self._stop_requested = False

    def request_stop(self):
        self._stop_requested = True

    def run(self):
        try:
            if self._stop_requested:
                return
            result = fetch_video_transcript(self.video_url, status_callback=self.status_signal.emit)
            if self._stop_requested:
                return
            self.finished_signal.emit(result)
        except Exception as exc:
            if not self._stop_requested:
                self.error_signal.emit(str(exc))
