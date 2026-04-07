import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from typing import Dict, List, Optional
from urllib.parse import parse_qs, quote_plus, urlparse

from PyQt6.QtCore import QThread, pyqtSignal

from core.videos_fetcher import (
    VideoSearchWorker,
    _http_get,
    _normalize_numeric_label,
    _response_text_utf8,
)
from utils.constants import REQUESTS_INSTALLED
from utils.proxy_utils import normalize_proxy, to_requests_proxies

try:
    import yt_dlp
except ImportError:  # pragma: no cover
    yt_dlp = None


CHANNEL_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def normalize_channel_input(raw_text: str) -> Optional[Dict[str, str]]:
    raw = str(raw_text or "").strip()
    if not raw:
        return None

    if raw.startswith("@"):
        base_url = f"https://www.youtube.com/{raw}"
        return {"input": raw, "channel_url": base_url, "about_url": f"{base_url}/about"}

    if re.fullmatch(r"UC[A-Za-z0-9_-]{20,}", raw):
        base_url = f"https://www.youtube.com/channel/{raw}"
        return {"input": raw, "channel_url": base_url, "about_url": f"{base_url}/about"}

    text = raw
    if "://" not in text and "youtube.com/" in text:
        text = f"https://{text}"

    parsed = urlparse(text)
    host = (parsed.netloc or "").lower()
    if "youtube.com" not in host:
        return None

    path = (parsed.path or "").strip("/")
    if not path:
        return None
    segments = [seg for seg in path.split("/") if seg]
    if not segments:
        return None

    if segments[0].startswith("@"):
        base_path = segments[0]
    elif segments[0] in {"channel", "c", "user"} and len(segments) >= 2:
        base_path = f"{segments[0]}/{segments[1]}"
    else:
        return None

    base_url = f"https://www.youtube.com/{base_path}"
    return {"input": raw, "channel_url": base_url, "about_url": f"{base_url}/about"}


def _extract_text(field) -> str:
    if isinstance(field, str):
        return field.strip()
    if isinstance(field, dict):
        if "content" in field:
            return str(field.get("content", "")).strip()
        if "text" in field:
            return str(field.get("text", "")).strip()
        style_runs = field.get("styleRuns", [])
        if isinstance(style_runs, list) and style_runs:
            base = str(field.get("content", "")).strip()
            if base:
                return base
    return VideoSearchWorker._extract_text(field)


def _find_first_key(node, key_name):
    if isinstance(node, dict):
        if key_name in node:
            return node.get(key_name)
        for value in node.values():
            found = _find_first_key(value, key_name)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_first_key(item, key_name)
            if found is not None:
                return found
    return None


def _extract_meta_content(page_html: str, name: str) -> str:
    patterns = (
        rf'<meta[^>]+property="{re.escape(name)}"[^>]+content="([^"]*)"',
        rf'<meta[^>]+content="([^"]*)"[^>]+property="{re.escape(name)}"',
        rf'<meta[^>]+name="{re.escape(name)}"[^>]+content="([^"]*)"',
        rf'<meta[^>]+content="([^"]*)"[^>]+name="{re.escape(name)}"',
    )
    for pattern in patterns:
        match = re.search(pattern, page_html, re.IGNORECASE)
        if match:
            return unescape(str(match.group(1) or "").strip())
    return ""


def _clean_url(url_text: str) -> str:
    url = str(url_text or "").strip()
    if not url:
        return ""
    return unescape(url.replace("\\/", "/").replace("\\u0026", "&")).strip()


def _extract_urls_from_text(text: str) -> List[str]:
    seen = set()
    output: List[str] = []
    for raw in re.findall(r'https?://[^\s"<>\']+', str(text or "")):
        cleaned = _clean_url(raw).rstrip(".,);]")
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(cleaned)
    return output


def _filter_external_urls(urls: List[str]) -> List[str]:
    blocked = (
        "youtube.com",
        "youtu.be",
        "google.com",
        "googleusercontent.com",
        "ytimg.com",
        "gstatic.com",
        "googlevideo.com",
        "ggpht.com",
        "schema.org",
        "youtubei-att.googleapis.com",
        "yt3.ggpht.com",
    )
    seen = set()
    output = []
    for url in urls:
        cleaned = _clean_url(url)
        parsed = urlparse(cleaned)
        host = (parsed.netloc or "").lower()
        if not host or any(domain in host for domain in blocked):
            continue
        host_key = host[4:] if host.startswith("www.") else host
        path_key = (parsed.path or "").rstrip("/")
        query_key = parsed.query or ""
        key = f"{host_key}{path_key}?{query_key}".lower()
        if key in seen:
            continue
        seen.add(key)
        canonical = f"https://{host_key}{path_key}"
        if query_key:
            canonical = f"{canonical}?{query_key}"
        output.append(canonical)
    return output


def _extract_external_links_from_about_view(node) -> List[str]:
    found: List[str] = []
    if isinstance(node, dict):
        link_vm = node.get("channelExternalLinkViewModel")
        if isinstance(link_vm, dict):
            link_obj = link_vm.get("link")
            content = _extract_text(link_obj)
            content = str(content or "").strip()
            if content:
                if not content.startswith(("http://", "https://")):
                    content = f"https://{content}"
                found.append(content)
            if isinstance(link_obj, dict):
                for command in link_obj.get("commandRuns", []):
                    if not isinstance(command, dict):
                        continue
                    url = (
                        command.get("onTap", {})
                        .get("innertubeCommand", {})
                        .get("urlEndpoint", {})
                        .get("url", "")
                    )
                    if url:
                        parsed = urlparse(url)
                        query = parse_qs(parsed.query)
                        target = query.get("q", [""])[0]
                        if target:
                            found.append(target)
        for value in node.values():
            found.extend(_extract_external_links_from_about_view(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_extract_external_links_from_about_view(item))
    return found


def _default_channel_row() -> Dict[str, str]:
    return {
        "Thumbnail URL": "",
        "Channel ID": "",
        "Channel Link": "",
        "Source": "youtube",
        "Search Phrase": "",
        "Title": "",
        "Description": "",
        "Total Videos": "not-given",
        "Total Views": "not-given",
        "Subscribers": "not-given",
        "Date Joined": "not-given",
        "Country": "not-given",
        "Keywords": "not-given",
        "External Links": "not-given",
    }


def _ydlp_channel_fallback(channel_url: str, proxy_url: str = "") -> Dict[str, str]:
    if yt_dlp is None:
        return {}
    try:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
            "playlistend": 1,
            "proxy": normalize_proxy(proxy_url) or "",
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
        if not isinstance(info, dict):
            return {}
        result = {}
        channel_id = str(info.get("channel_id") or info.get("id") or "").strip()
        if channel_id:
            result["Channel ID"] = channel_id
        title = str(info.get("channel") or info.get("uploader") or info.get("title") or "").strip()
        if title:
            result["Title"] = title
        channel_link = str(info.get("channel_url") or info.get("uploader_url") or "").strip()
        if channel_link:
            result["Channel Link"] = channel_link
        followers = info.get("channel_follower_count")
        if followers is not None:
            result["Subscribers"] = f"{int(followers):,}"
        playlist_count = info.get("playlist_count")
        if playlist_count is not None:
            result["Total Videos"] = f"{int(playlist_count):,}"
        description = str(info.get("description") or "").strip()
        if description:
            result["Description"] = description
        thumbs = info.get("thumbnails") or []
        if isinstance(thumbs, list) and thumbs:
            last = thumbs[-1] if isinstance(thumbs[-1], dict) else {}
            thumb_url = str(last.get("url", "")).strip()
            if thumb_url:
                result["Thumbnail URL"] = thumb_url
        return result
    except Exception:
        return {}


def fetch_channel_details(channel_input: str, proxy_url: str = "") -> Dict[str, str]:
    normalized = normalize_channel_input(channel_input)
    if not normalized:
        raise ValueError(f"Invalid YouTube channel input: {channel_input}")
    if not REQUESTS_INSTALLED:
        raise ImportError("Dependency Error: requests is missing. Run: pip install requests")

    proxies = None
    proxy = normalize_proxy(proxy_url)
    if proxy:
        proxies = to_requests_proxies(proxy)

    response = _http_get(
        normalized["about_url"],
        params={"hl": "en"},
        headers=CHANNEL_HEADERS,
        timeout=25,
        proxies=proxies,
    )
    response.raise_for_status()
    page_html = _response_text_utf8(response)
    parser = VideoSearchWorker(query="channel", max_results=1)
    initial_data = parser._extract_initial_data(page_html)

    metadata = _find_first_key(initial_data, "channelMetadataRenderer")
    if not isinstance(metadata, dict):
        metadata = {}
    header = _find_first_key(initial_data, "c4TabbedHeaderRenderer")
    if not isinstance(header, dict):
        header = {}
    about_renderer = _find_first_key(initial_data, "aboutChannelRenderer")
    if not isinstance(about_renderer, dict):
        about_renderer = {}
    about_view = _find_first_key(initial_data, "aboutChannelViewModel")
    if not isinstance(about_view, dict):
        about_view = {}

    row = _default_channel_row()
    row["Channel Link"] = normalized["channel_url"]
    row["Channel ID"] = str(metadata.get("externalId", "")).strip()
    row["Title"] = (
        str(metadata.get("title", "")).strip()
        or _extract_text(header.get("title"))
        or _extract_text(about_view.get("title"))
        or _extract_meta_content(page_html, "og:title")
    )
    row["Description"] = (
        str(metadata.get("description", "")).strip()
        or _extract_text(about_renderer.get("description"))
        or _extract_text(about_view.get("description"))
        or _extract_meta_content(page_html, "og:description")
    )
    row["Keywords"] = (
        str(metadata.get("keywords", "")).strip()
        or _extract_text(about_view.get("keywords"))
        or _extract_meta_content(page_html, "keywords")
        or "not-given"
    )
    row["Thumbnail URL"] = _clean_url(_extract_meta_content(page_html, "og:image"))
    row["Channel Link"] = _clean_url(_extract_meta_content(page_html, "og:url")) or row["Channel Link"]

    subscriber_text = (
        _extract_text(about_view.get("subscriberCountText"))
        or _extract_text(about_renderer.get("subscriberCountText"))
        or _extract_text(header.get("subscriberCountText"))
        or _extract_text(_find_first_key(initial_data, "subscriberCountText"))
    )
    view_text = (
        _extract_text(about_view.get("viewCountText"))
        or _extract_text(about_renderer.get("viewCountText"))
        or _extract_text(_find_first_key(initial_data, "viewCountText"))
    )
    videos_text = (
        _extract_text(about_view.get("videoCountText"))
        or _extract_text(about_renderer.get("videosCountText"))
        or _extract_text(header.get("videosCountText"))
        or _extract_text(_find_first_key(initial_data, "videosCountText"))
    )
    joined_text = (
        _extract_text(_find_first_key(initial_data, "joinedDateText"))
        or _extract_text(about_renderer.get("joinedDateText"))
        or _extract_text(about_view.get("joinedDateText"))
        or _extract_text(about_view.get("joinedDate"))
    )
    country_node = _find_first_key(initial_data, "country")
    if isinstance(country_node, dict):
        country_text = _extract_text(country_node)
    else:
        country_text = str(country_node or "").strip()
    if not country_text:
        country_text = _extract_text(about_renderer.get("country")) or _extract_text(about_view.get("country"))

    row["Subscribers"] = _normalize_numeric_label(subscriber_text)
    row["Total Views"] = _normalize_numeric_label(view_text)
    row["Total Videos"] = _normalize_numeric_label(videos_text)
    row["Date Joined"] = joined_text.replace("Joined", "").strip() if joined_text else "not-given"
    row["Country"] = country_text or "not-given"

    external_urls = _filter_external_urls(
        _extract_external_links_from_about_view(about_view)
        + _extract_external_links_from_about_view(about_renderer)
        + _extract_urls_from_text(_extract_text(about_renderer.get("description")))
        + _extract_urls_from_text(_extract_text(about_view.get("description")))
    )
    if external_urls:
        row["External Links"] = ", ".join(external_urls)

    fallback = _ydlp_channel_fallback(row["Channel Link"], proxy_url=proxy)
    for key, value in fallback.items():
        if str(value or "").strip() and str(row.get(key, "")).strip() in {"", "not-given"}:
            row[key] = str(value)

    row["Title"] = row["Title"] or row["Channel ID"] or row["Channel Link"]
    row["Description"] = row["Description"] or "not-given"
    return row


class ChannelImportWorker(QThread):
    row_signal = pyqtSignal(dict)
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(dict)

    def __init__(self, inputs: List, use_proxies: bool = False, proxy_list: Optional[List[str]] = None):
        super().__init__()
        self.inputs = list(inputs or [])
        self._running = True
        self._use_proxies = bool(use_proxies)
        self._proxy_list = [p for p in (normalize_proxy(x) for x in (proxy_list or [])) if p]
        self._proxy_cursor = -1
        self.max_workers = 2

    def stop(self):
        self._running = False

    def _next_proxy(self) -> str:
        if not self._use_proxies or not self._proxy_list:
            return ""
        self._proxy_cursor = (self._proxy_cursor + 1) % len(self._proxy_list)
        return self._proxy_list[self._proxy_cursor]

    def _task(self, payload) -> Dict[str, str]:
        if isinstance(payload, dict):
            raw_input = str(payload.get("input", "")).strip()
            base = {k: v for k, v in payload.items() if k != "input"}
        else:
            raw_input = str(payload).strip()
            base = {}
        row = fetch_channel_details(raw_input, proxy_url=self._next_proxy())
        for key, value in base.items():
            if str(value or "").strip() and str(row.get(key, "")).strip() in {"", "not-given"}:
                row[key] = value
        row["__input__"] = raw_input
        return row

    def run(self):
        if not self.inputs:
            self.error_signal.emit("Please enter at least one channel link, handle, or channel ID.")
            self.finished_signal.emit({"count": 0, "invalid": 0, "failed": 0, "stopped": False})
            return

        normalized_inputs = []
        invalid_inputs = []
        seen = set()
        for payload in self.inputs:
            raw = str(payload.get("input", "")).strip() if isinstance(payload, dict) else str(payload).strip()
            normalized = normalize_channel_input(raw)
            if not normalized:
                invalid_inputs.append(raw)
                continue
            key = normalized["channel_url"].lower()
            if key in seen:
                continue
            seen.add(key)
            normalized_inputs.append(payload)

        if not normalized_inputs:
            self.error_signal.emit("No valid YouTube channel links or IDs were found.")
            self.finished_signal.emit({"count": 0, "invalid": len(invalid_inputs), "failed": 0, "stopped": False})
            return

        emitted = 0
        failed = 0
        workers = max(1, min(self.max_workers, len(normalized_inputs)))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {executor.submit(self._task, payload): payload for payload in normalized_inputs}
            total = len(future_map)
            for idx, future in enumerate(as_completed(future_map), start=1):
                payload = future_map[future]
                raw = str(payload.get("input", "")).strip() if isinstance(payload, dict) else str(payload).strip()
                if not self._running:
                    self.finished_signal.emit({"count": emitted, "invalid": len(invalid_inputs), "failed": failed, "stopped": True})
                    return
                try:
                    row = future.result()
                    emitted += 1
                    self.row_signal.emit(row)
                    if idx == 1 or idx == total or idx % 3 == 0:
                        title = str(row.get("Title", "")).strip() or raw
                        self.status_signal.emit(f"Loaded channel {idx}/{total}: {title}")
                except Exception as exc:
                    failed += 1
                    self.error_signal.emit(f"Channel import failed for '{raw}': {str(exc).strip() or 'unknown error'}")
        self.finished_signal.emit({"count": emitted, "invalid": len(invalid_inputs), "failed": failed, "stopped": False})


class ChannelsSearchWorker(QThread):
    item_signal = pyqtSignal(dict)
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(dict)

    def __init__(
        self,
        query: str,
        include_youtube: bool = True,
        include_google: bool = True,
        include_bing: bool = True,
        pages: int = 1,
        use_proxies: bool = False,
        proxy_list: Optional[List[str]] = None,
    ):
        super().__init__()
        self.query = str(query or "").strip()
        self.include_youtube = bool(include_youtube)
        self.include_google = bool(include_google)
        self.include_bing = bool(include_bing)
        self.pages = max(1, int(pages or 1))
        self._running = True
        self._use_proxies = bool(use_proxies)
        self._proxy_list = [p for p in (normalize_proxy(x) for x in (proxy_list or [])) if p]
        self._proxy_cursor = -1

    def stop(self):
        self._running = False

    def _next_requests_proxies(self):
        if not self._use_proxies or not self._proxy_list:
            return None
        self._proxy_cursor = (self._proxy_cursor + 1) % len(self._proxy_list)
        return to_requests_proxies(self._proxy_list[self._proxy_cursor])

    def _append_item(self, items: List[Dict[str, str]], seen: set, item: Dict[str, str]):
        normalized = normalize_channel_input(item.get("input", ""))
        if not normalized:
            return
        key = normalized["channel_url"].lower()
        if key in seen:
            return
        seen.add(key)
        item["input"] = normalized["channel_url"]
        items.append(item)
        self.item_signal.emit(dict(item))

    def _youtube_items(self) -> List[Dict[str, str]]:
        url = f"https://www.youtube.com/results?search_query={quote_plus(self.query)}&sp=EgIQAg%253D%253D&hl=en"
        response = _http_get(url, headers=CHANNEL_HEADERS, timeout=25, proxies=self._next_requests_proxies())
        response.raise_for_status()
        parser = VideoSearchWorker(query=self.query, max_results=30)
        initial_data = parser._extract_initial_data(_response_text_utf8(response))
        items: List[Dict[str, str]] = []
        seen = set()
        for renderer in self._iter_channel_renderers(initial_data):
            if not self._running:
                break
            item = self._renderer_to_item(renderer)
            if item:
                self._append_item(items, seen, item)
        return items

    def _iter_channel_renderers(self, node):
        if isinstance(node, dict):
            renderer = node.get("channelRenderer")
            if isinstance(renderer, dict):
                yield renderer
            for value in node.values():
                yield from self._iter_channel_renderers(value)
        elif isinstance(node, list):
            for item in node:
                yield from self._iter_channel_renderers(item)

    def _renderer_to_item(self, renderer: dict) -> Optional[Dict[str, str]]:
        if not isinstance(renderer, dict):
            return None
        title_text = _extract_text(renderer.get("title"))
        web_url = ""
        browse_id = str(renderer.get("channelId", "")).strip()
        nav = renderer.get("navigationEndpoint", {})
        nav_url = (
            nav.get("commandMetadata", {})
            .get("webCommandMetadata", {})
            .get("url", "")
        )
        nav_browse_id = (
            nav.get("browseEndpoint", {})
            .get("browseId", "")
        )
        title_runs = renderer.get("title", {}).get("runs", [])
        if isinstance(title_runs, list) and title_runs:
            first = title_runs[0] if isinstance(title_runs[0], dict) else {}
            web_url = (
                first.get("navigationEndpoint", {})
                .get("commandMetadata", {})
                .get("webCommandMetadata", {})
                .get("url", "")
            )
            if not browse_id:
                browse_id = (
                    first.get("navigationEndpoint", {})
                    .get("browseEndpoint", {})
                    .get("browseId", "")
                )
        if not web_url:
            web_url = nav_url
        if not browse_id:
            browse_id = str(nav_browse_id or "").strip()
        if web_url:
            channel_url = f"https://www.youtube.com{web_url}" if web_url.startswith("/") else str(web_url).strip()
        elif browse_id:
            channel_url = f"https://www.youtube.com/channel/{browse_id}"
        else:
            return None
        video_count_text = _extract_text(renderer.get("videoCountText"))
        subscriber_text = _extract_text(renderer.get("subscriberCountText"))
        if "subscriber" in video_count_text.lower():
            subscriber_value = _normalize_numeric_label(video_count_text)
            total_videos_value = "not-given"
        else:
            subscriber_value = _normalize_numeric_label(subscriber_text)
            total_videos_value = _normalize_numeric_label(video_count_text)
        return {
            "input": channel_url,
            "Source": "youtube",
            "Search Phrase": self.query,
            "Channel ID": browse_id,
            "Title": title_text,
            "Description": _extract_text(renderer.get("descriptionSnippet")),
            "Subscribers": subscriber_value,
            "Total Videos": total_videos_value,
            "Thumbnail URL": VideoSearchWorker._extract_thumbnail_url(renderer.get("thumbnail")),
        }

    def _engine_items(self, engine: str) -> List[Dict[str, str]]:
        items: List[Dict[str, str]] = []
        seen = set()
        for page in range(1, self.pages + 1):
            if not self._running:
                break
            if engine == "google":
                url = f"https://www.google.com/search?q={quote_plus(f'site:youtube.com (@ OR channel) {self.query}')}&start={(page - 1) * 10}"
                source = "google"
            else:
                url = f"https://www.bing.com/search?q={quote_plus(f'site:youtube.com (@ OR channel) {self.query}')}&first={((page - 1) * 10) + 1}"
                source = "bing"
            response = _http_get(url, headers=CHANNEL_HEADERS, timeout=25, proxies=self._next_requests_proxies())
            response.raise_for_status()
            for found in _extract_urls_from_text(_response_text_utf8(response)):
                normalized = normalize_channel_input(found)
                if not normalized:
                    continue
                self._append_item(items, seen, {"input": normalized["channel_url"], "Source": source, "Search Phrase": self.query})
        return items

    def run(self):
        if not self.query:
            self.error_signal.emit("Please enter a search phrase first.")
            self.finished_signal.emit({"items": [], "count": 0, "stopped": False})
            return

        if not any((self.include_youtube, self.include_google, self.include_bing)):
            self.error_signal.emit("Select at least one search source.")
            self.finished_signal.emit({"items": [], "count": 0, "stopped": False})
            return

        items: List[Dict[str, str]] = []
        seen = set()
        try:
            if self.include_youtube and self._running:
                self.status_signal.emit(f"Searching YouTube channels for '{self.query}'...")
                for item in self._youtube_items():
                    self._append_item(items, seen, item)
            if self.include_google and self._running:
                self.status_signal.emit(f"Searching Google channels for '{self.query}'...")
                for item in self._engine_items("google"):
                    self._append_item(items, seen, item)
            if self.include_bing and self._running:
                self.status_signal.emit(f"Searching Bing channels for '{self.query}'...")
                for item in self._engine_items("bing"):
                    self._append_item(items, seen, item)
            self.finished_signal.emit({"items": items, "count": len(items), "stopped": not self._running})
        except Exception as exc:
            self.error_signal.emit(str(exc).strip() or "Channel search failed.")
            self.finished_signal.emit({"items": items, "count": len(items), "stopped": not self._running})
