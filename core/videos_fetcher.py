import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html import unescape
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlencode

from PyQt6.QtCore import QThread, pyqtSignal

from utils.constants import REQUESTS_INSTALLED
from utils.proxy_utils import normalize_proxy, to_requests_proxies

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

try:
    import yt_dlp
except ImportError:  # pragma: no cover
    yt_dlp = None


def _response_text_utf8(response) -> str:
    try:
        data = bytes(response.content or b"")
        if data:
            return data.decode("utf-8", errors="replace")
    except Exception:
        pass
    return str(getattr(response, "text", "") or "")


def _http_get(url: str, *, params=None, headers=None, timeout=25, proxy_url: str = "", proxies=None):
    if not REQUESTS_INSTALLED or requests is None:
        raise ImportError("Dependency Error: requests is missing. Run: pip install requests")
    session = requests.Session()
    session.trust_env = False
    proxy_payload = proxies
    if proxy_payload is None and proxy_url:
        normalized = normalize_proxy(proxy_url)
        proxy_payload = to_requests_proxies(normalized) if normalized else None
    if proxy_payload:
        session.proxies.update(proxy_payload)
    response = session.get(url, params=params, headers=headers, timeout=timeout)
    return response


def _default_video_row() -> Dict[str, str]:
    return {
        "Rating": "not-given",
        "Comments": "not-given",
        "View Count": "not-given",
        "Length Seconds": "not-given",
        "Published": "not-given",
        "Published Age (Days)": "not-given",
        "Avg. Views per Day": "not-given",
        "Category": "not-given",
        "Subtitles": "not-given",
        "Channel": "",
        "Channel Link": "",
        "Subscribers": "not-given",
        "Tags": "",
    }


def _normalize_numeric_label(text: str, default: str = "not-given") -> str:
    raw = str(text or "").strip()
    if not raw:
        return default
    raw_lc = raw.lower()
    if "turned off" in raw_lc:
        return "0"
    if "no comment" in raw_lc or "no subscriber" in raw_lc:
        return "0"
    match = re.search(r"([0-9]*\.?[0-9]+)\s*([kmb])?\+?", raw_lc)
    if not match:
        return default
    number = float(match.group(1))
    suffix = (match.group(2) or "").lower()
    multiplier = 1
    has_suffix = False
    if suffix == "k":
        multiplier = 1_000
        has_suffix = True
    elif suffix == "m":
        multiplier = 1_000_000
        has_suffix = True
    elif suffix == "b":
        multiplier = 1_000_000_000
        has_suffix = True
    value = int(number * multiplier)
    return f"{value:,}+" if has_suffix else f"{value:,}"


def fetch_video_page_details(video_id: str = "", video_link: str = "", proxy_url: str = "") -> Dict[str, str]:
    details: Dict[str, str] = {}
    video_key = str(video_id or "").strip()
    watch_url = str(video_link or "").strip()
    if not video_key and "watch?v=" in watch_url:
        parsed = re.search(r"[?&]v=([^&]+)", watch_url)
        if parsed:
            video_key = str(parsed.group(1)).strip()

    if not REQUESTS_INSTALLED or requests is None:
        return details
    if not video_key and not watch_url:
        return details

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    proxies = None
    normalized_proxy = normalize_proxy(proxy_url)
    if normalized_proxy:
        proxies = to_requests_proxies(normalized_proxy)

    if video_key:
        response = _http_get(
            "https://www.youtube.com/watch",
            params={"v": video_key, "hl": "en"},
            headers=headers,
            timeout=25,
            proxies=proxies,
        )
    else:
        response = _http_get(
            watch_url,
            headers=headers,
            timeout=25,
            proxies=proxies,
        )
    response.raise_for_status()
    page_html = _response_text_utf8(response)

    def _extract_text(field) -> str:
        if not isinstance(field, dict):
            return ""
        if "simpleText" in field:
            return str(field.get("simpleText", "")).strip()
        runs = field.get("runs", [])
        if isinstance(runs, list):
            return "".join(str(part.get("text", "")) for part in runs if isinstance(part, dict)).strip()
        return ""

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

    def _parse_age_days(date_text: str) -> int:
        raw = str(date_text or "").strip()
        if not raw:
            return 0
        try:
            if "T" in raw:
                raw = raw.replace("Z", "+00:00")
                target = datetime.fromisoformat(raw)
                if target.tzinfo is None:
                    target = target.replace(tzinfo=timezone.utc)
                delta = datetime.now(timezone.utc) - target.astimezone(timezone.utc)
                return max(0, delta.days)
            target = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            delta = datetime.now(timezone.utc) - target
            return max(0, delta.days)
        except Exception:
            return 0

    marker = "var ytInitialPlayerResponse = "
    blob = VideoSearchWorker._extract_json_blob(page_html, marker)
    if not blob:
        marker = 'window["ytInitialPlayerResponse"] = '
        blob = VideoSearchWorker._extract_json_blob(page_html, marker)
    if not blob:
        return details

    player = json.loads(blob)
    video_details = player.get("videoDetails", {}) if isinstance(player, dict) else {}
    microformat = (
        player.get("microformat", {}).get("playerMicroformatRenderer", {})
        if isinstance(player, dict)
        else {}
    )

    title = str(video_details.get("title", "")).strip()
    description = str(video_details.get("shortDescription", "")).strip()
    author = str(video_details.get("author", "")).strip()
    channel_id = str(video_details.get("channelId", "")).strip()
    view_count = str(video_details.get("viewCount", "")).strip()
    length_seconds = str(video_details.get("lengthSeconds", "")).strip()
    publish_date = str(microformat.get("publishDate", "")).strip()
    upload_date = str(microformat.get("uploadDate", "")).strip()
    category = str(microformat.get("category", "")).strip()
    owner_url = microformat.get("ownerProfileUrl", "")
    owner_url = str(owner_url).strip() if owner_url not in (None, "None") else ""
    average_rating = str(video_details.get("averageRating", "")).strip()
    keywords = video_details.get("keywords", [])
    captions = (
        player.get("captions", {})
        .get("playerCaptionsTracklistRenderer", {})
        .get("captionTracks", [])
        if isinstance(player, dict)
        else []
    )

    thumb_url = ""
    thumbs = video_details.get("thumbnail", {}).get("thumbnails", [])
    if isinstance(thumbs, list) and thumbs:
        last = thumbs[-1] if isinstance(thumbs[-1], dict) else {}
        thumb_url = VideoSearchWorker._normalize_thumbnail_url(str(last.get("url", "")).strip(), video_key)

    initial_data = VideoSearchWorker(query="details", max_results=1)._extract_initial_data(page_html)
    owner_renderer = _find_first_key(initial_data, "videoOwnerRenderer")
    comments_header = _find_first_key(initial_data, "commentsHeaderRenderer")
    subscriber_text = ""
    comments_text = ""
    if isinstance(owner_renderer, dict):
        subscriber_text = _extract_text(owner_renderer.get("subscriberCountText"))
    if isinstance(comments_header, dict):
        comments_text = _extract_text(comments_header.get("countText"))

    publish_exact = upload_date or publish_date
    age_days = _parse_age_days(publish_exact)
    view_count_num = int(re.sub(r"[^0-9]", "", view_count)) if re.sub(r"[^0-9]", "", view_count) else 0
    avg_views_per_day = int(view_count_num / max(1, age_days)) if age_days > 0 else 0
    tags_text = ", ".join(str(tag).strip() for tag in keywords if str(tag).strip())
    subtitles = "YES" if captions else "NO"

    normalized_comments = _normalize_numeric_label(comments_text)
    normalized_subscribers = _normalize_numeric_label(subscriber_text)

    details.update(
        {
            "Title": title,
            "Description": description,
            "Channel Name": author,
            "Channel ID": channel_id,
            "Channel URL": owner_url or (f"https://www.youtube.com/channel/{channel_id}" if channel_id else ""),
            "Channel Link": owner_url or (f"https://www.youtube.com/channel/{channel_id}" if channel_id else ""),
            "View Count": f"{view_count_num:,}" if view_count_num > 0 else view_count,
            "Length Seconds": length_seconds,
            "Publish Date": publish_date,
            "Upload Date": upload_date,
            "Category": category,
            "Thumbnail URL": thumb_url,
            "Rating": average_rating or "not-given",
            "Comments": normalized_comments,
            "Published": publish_exact or "not-given",
            "Published Age (Days)": str(age_days) if age_days > 0 else "not-given",
            "Avg. Views per Day": f"{avg_views_per_day:,}" if avg_views_per_day > 0 else "0",
            "Subtitles": subtitles,
            "Channel": author,
            "Subscribers": normalized_subscribers,
            "Tags": tags_text,
        }
    )

    if yt_dlp is not None and (
        details.get("Comments", "not-given") == "not-given"
        or details.get("Subscribers", "not-given") == "not-given"
        or details.get("Published", "not-given") == "not-given"
    ):
        original_proxy_values = {k: os.environ.pop(k, None) for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")}
        try:
            ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True, "proxy": ""}
            normalized_proxy = normalize_proxy(proxy_url)
            if normalized_proxy:
                ydl_opts["proxy"] = normalized_proxy
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_link or f"https://www.youtube.com/watch?v={video_key}", download=False)
            if info:
                comment_count = info.get("comment_count")
                if comment_count is not None and details.get("Comments", "not-given") == "not-given":
                    details["Comments"] = f"{int(comment_count):,}"
                follower_count = info.get("channel_follower_count")
                if follower_count is not None and details.get("Subscribers", "not-given") == "not-given":
                    details["Subscribers"] = f"{int(follower_count):,}"
                upload_date_raw = str(info.get("upload_date", "")).strip()
                if upload_date_raw and details.get("Published", "not-given") == "not-given":
                    if len(upload_date_raw) == 8 and upload_date_raw.isdigit():
                        details["Published"] = f"{upload_date_raw[:4]}-{upload_date_raw[4:6]}-{upload_date_raw[6:]}"
                if details.get("Published", "not-given") != "not-given":
                    age_days = _parse_age_days(details["Published"])
                    details["Published Age (Days)"] = str(age_days) if age_days > 0 else "not-given"
                    views_digits = re.sub(r"[^0-9]", "", str(details.get("View Count", "")))
                    view_count_num = int(views_digits) if views_digits else 0
                    details["Avg. Views per Day"] = f"{int(view_count_num / max(1, age_days)):,}" if age_days > 0 else "0"
        except Exception:
            pass
        finally:
            for key, value in original_proxy_values.items():
                if value:
                    os.environ[key] = value

    return details


class VideoMetadataEnrichWorker(QThread):
    row_enriched_signal = pyqtSignal(str, dict)
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(dict)

    def __init__(self, rows: List[dict], proxy_url: str = ""):
        super().__init__()
        self.rows = [dict(row) for row in (rows or []) if isinstance(row, dict)]
        self.proxy_url = str(proxy_url or "").strip()
        self._running = True
        self.max_workers = 2

    def stop(self):
        self._running = False

    def run(self):
        total = len(self.rows)
        if total == 0:
            self.finished_signal.emit({"count": 0, "updated": 0, "stopped": False})
            return

        updated = 0
        workers = max(1, min(self.max_workers, total))

        def _task(payload):
            video_id = str(payload.get("Video ID", "")).strip()
            video_link = str(payload.get("Video Link", "")).strip()
            title = str(payload.get("Title", "")).strip() or video_id or "video"
            details = fetch_video_page_details(video_id=video_id, video_link=video_link, proxy_url=self.proxy_url)
            return video_id, title, details

        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {executor.submit(_task, row): idx for idx, row in enumerate(self.rows, start=1)}
            for future in as_completed(future_map):
                idx = future_map[future]
                if not self._running:
                    self.finished_signal.emit({"count": total, "updated": updated, "stopped": True})
                    return
                try:
                    video_id, title, details = future.result()
                    self.status_signal.emit(f"Enriched metadata {idx}/{total}: {title}")
                    if details:
                        self.row_enriched_signal.emit(video_id, details)
                        updated += 1
                except Exception as exc:
                    self.error_signal.emit(f"Metadata enrich failed: {str(exc).strip() or 'unknown error'}")
        self.finished_signal.emit({"count": total, "updated": updated, "stopped": False})


class _DownloadStopped(Exception):
    pass


class VideoDownloadWorker(QThread):
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(dict)

    def __init__(self, video_rows: List[dict], output_dir: str, proxy_url: str = ""):
        super().__init__()
        self.video_rows = [dict(row) for row in (video_rows or []) if isinstance(row, dict)]
        self.output_dir = str(output_dir or "").strip()
        self.proxy_url = str(proxy_url or "").strip()
        self._running = True

    def stop(self):
        self._running = False

    def _progress_hook_factory(self, title: str, index: int, total: int):
        def _hook(progress):
            if not self._running:
                raise _DownloadStopped()
            status = str(progress.get("status", "")).strip().lower()
            if status == "downloading":
                percent = str(progress.get("_percent_str", "")).strip()
                speed = str(progress.get("_speed_str", "")).strip()
                eta = str(progress.get("_eta_str", "")).strip()
                parts = [f"Downloading {index}/{total}: {title}"]
                if percent:
                    parts.append(percent)
                if speed:
                    parts.append(speed)
                if eta:
                    parts.append(f"ETA {eta}")
                self.status_signal.emit(" | ".join(parts))
            elif status == "finished":
                self.status_signal.emit(f"Processing downloaded file {index}/{total}: {title}")

        return _hook

    def _ydl_options(self, title: str, index: int, total: int):
        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "outtmpl": os.path.join(self.output_dir, "%(title).150B [%(id)s].%(ext)s"),
            "windowsfilenames": True,
            "restrictfilenames": False,
            "progress_hooks": [self._progress_hook_factory(title, index, total)],
            "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best",
            "merge_output_format": "mp4",
        }
        if self.proxy_url:
            options["proxy"] = self.proxy_url
        return options

    def _download_one(self, row: dict, index: int, total: int):
        link = str(row.get("Video Link", "")).strip()
        title = str(row.get("Title", "")).strip() or str(row.get("Video ID", "")).strip() or f"video-{index}"
        if not link:
            return {"ok": False, "title": title, "error": "Missing video link"}
        if yt_dlp is None:
            return {"ok": False, "title": title, "error": "yt-dlp is not installed"}

        try:
            with yt_dlp.YoutubeDL(self._ydl_options(title, index, total)) as ydl:
                ydl.download([link])
            return {"ok": True, "title": title}
        except _DownloadStopped:
            raise
        except Exception as exc:
            first_error = str(exc).strip() or "Download failed"
            # Fallback for systems without ffmpeg or when adaptive merge fails.
            try:
                fallback_opts = self._ydl_options(title, index, total)
                fallback_opts["format"] = "best[ext=mp4]/best"
                fallback_opts.pop("merge_output_format", None)
                with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                    ydl.download([link])
                return {"ok": True, "title": title}
            except _DownloadStopped:
                raise
            except Exception as fallback_exc:
                second_error = str(fallback_exc).strip() or first_error
                return {"ok": False, "title": title, "error": second_error}

    def run(self):
        if not self.video_rows:
            self.error_signal.emit("No videos selected for download.")
            self.finished_signal.emit({"total": 0, "downloaded": 0, "failed": 0, "stopped": False})
            return
        if yt_dlp is None:
            self.error_signal.emit("yt-dlp is not installed. Run: pip install yt-dlp")
            self.finished_signal.emit({"total": len(self.video_rows), "downloaded": 0, "failed": len(self.video_rows), "stopped": False})
            return

        os.makedirs(self.output_dir, exist_ok=True)
        total = len(self.video_rows)
        downloaded = 0
        failures = []

        try:
            for index, row in enumerate(self.video_rows, start=1):
                if not self._running:
                    raise _DownloadStopped()
                title = str(row.get("Title", "")).strip() or str(row.get("Video ID", "")).strip() or f"video-{index}"
                self.status_signal.emit(f"Preparing download {index}/{total}: {title}")
                result = self._download_one(row, index, total)
                if result.get("ok"):
                    downloaded += 1
                    self.status_signal.emit(f"Downloaded {index}/{total}: {title}")
                else:
                    failures.append(result)
                    self.error_signal.emit(f"{title}: {result.get('error', 'Download failed')}")
        except _DownloadStopped:
            self.status_signal.emit("Video download stopped.")
            self.finished_signal.emit(
                {
                    "total": total,
                    "downloaded": downloaded,
                    "failed": len(failures),
                    "failed_items": failures,
                    "stopped": True,
                }
            )
            return

        self.finished_signal.emit(
            {
                "total": total,
                "downloaded": downloaded,
                "failed": len(failures),
                "failed_items": failures,
                "stopped": False,
            }
        )


class VideoSearchWorker(QThread):
    video_signal = pyqtSignal(dict)
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(dict)

    def __init__(
        self,
        query: str,
        max_results: int = 20,
        sort_by: str = "Relevance",
        require_subtitles: bool = False,
        require_creative_commons: bool = False,
        first_page_only: bool = True,
        use_proxies: bool = False,
        proxy_list: Optional[List[str]] = None,
    ):
        super().__init__()
        self.query = (query or "").strip()
        self.max_results = max(1, int(max_results))
        self.sort_by = str(sort_by or "Relevance").strip()
        self.require_subtitles = bool(require_subtitles)
        self.require_creative_commons = bool(require_creative_commons)
        self.first_page_only = bool(first_page_only)
        self._watch_meta_cache: Dict[str, Dict[str, bool]] = {}
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

    @staticmethod
    def _extract_text(field: Optional[dict]) -> str:
        if not isinstance(field, dict):
            return ""
        if "simpleText" in field:
            return str(field.get("simpleText", "")).strip()
        runs = field.get("runs", [])
        if isinstance(runs, list):
            return "".join(str(part.get("text", "")) for part in runs if isinstance(part, dict)).strip()
        return ""

    @staticmethod
    def _extract_thumbnail_url(field: Optional[dict]) -> str:
        if not isinstance(field, dict):
            return ""
        thumbs = field.get("thumbnails", [])
        if not isinstance(thumbs, list) or not thumbs:
            return ""
        last = thumbs[-1] if isinstance(thumbs[-1], dict) else {}
        raw_url = str(last.get("url", "")).strip()
        return VideoSearchWorker._normalize_thumbnail_url(raw_url)

    @staticmethod
    def _extract_channel_name(field: Optional[dict]) -> str:
        return VideoSearchWorker._extract_text(field)

    @staticmethod
    def _extract_channel_link(field: Optional[dict]) -> str:
        if not isinstance(field, dict):
            return ""
        runs = field.get("runs", [])
        if not isinstance(runs, list) or not runs:
            return ""
        first = runs[0] if isinstance(runs[0], dict) else {}
        browse_id = (
            first.get("navigationEndpoint", {})
            .get("browseEndpoint", {})
            .get("browseId", "")
        )
        browse_id = str(browse_id or "").strip()
        if browse_id:
            return f"https://www.youtube.com/channel/{browse_id}"
        return ""

    @staticmethod
    def _parse_length_seconds(text: str) -> int:
        raw = str(text or "").strip()
        if not raw:
            return 0
        parts = [p for p in raw.split(":") if p.strip().isdigit()]
        if not parts:
            return 0
        total = 0
        for part in parts:
            total = (total * 60) + int(part)
        return total

    @staticmethod
    def _extract_video_id_from_thumbnail_url(thumb_url: str) -> str:
        match = re.search(r"/vi(?:_webp)?/([^/]+)/", str(thumb_url or ""))
        if not match:
            return ""
        return str(match.group(1)).strip()

    @staticmethod
    def _normalize_thumbnail_url(thumb_url: str, video_id: str = "") -> str:
        url = str(thumb_url or "").strip()
        if not url:
            return ""
        vid = str(video_id or "").strip() or VideoSearchWorker._extract_video_id_from_thumbnail_url(url)
        if not vid:
            return url
        # Prefer higher quality JPEG while keeping PyQt decode stable.
        return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"

    @staticmethod
    def _thumbnail_candidates(thumb_url: str, video_id: str = "") -> List[str]:
        vid = str(video_id or "").strip() or VideoSearchWorker._extract_video_id_from_thumbnail_url(thumb_url)
        urls: List[str] = []
        if str(thumb_url or "").strip():
            urls.append(str(thumb_url).strip())
        if not vid:
            return urls
        for quality in ("maxresdefault.jpg", "sddefault.jpg", "hqdefault.jpg", "mqdefault.jpg"):
            candidate = f"https://i.ytimg.com/vi/{vid}/{quality}"
            if candidate not in urls:
                urls.append(candidate)
        return urls

    @staticmethod
    def _extract_json_blob(page_html: str, marker: str) -> Optional[str]:
        marker_index = page_html.find(marker)
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

    def _extract_initial_data(self, page_html: str) -> dict:
        markers = (
            "var ytInitialData = ",
            "window['ytInitialData'] = ",
            'window["ytInitialData"] = ',
        )
        for marker in markers:
            blob = self._extract_json_blob(page_html, marker)
            if blob:
                try:
                    return json.loads(blob)
                except json.JSONDecodeError:
                    continue
        return {}

    def _iter_video_renderers(self, node) -> Iterable[dict]:
        if isinstance(node, dict):
            video_renderer = node.get("videoRenderer")
            if isinstance(video_renderer, dict):
                yield video_renderer
            for value in node.values():
                yield from self._iter_video_renderers(value)
            return
        if isinstance(node, list):
            for item in node:
                yield from self._iter_video_renderers(item)

    @staticmethod
    def _parse_view_count_number(text: str) -> int:
        raw = str(text or "").strip().lower()
        if not raw:
            return 0
        raw = raw.replace("views", "").replace("view", "").replace(",", "").strip()
        match = re.search(r"([0-9]*\.?[0-9]+)\s*([kmb])?", raw)
        if not match:
            digits = re.sub(r"[^0-9]", "", raw)
            return int(digits) if digits else 0

        num = float(match.group(1))
        suffix = (match.group(2) or "").lower()
        if suffix == "k":
            num *= 1_000
        elif suffix == "m":
            num *= 1_000_000
        elif suffix == "b":
            num *= 1_000_000_000
        return int(num)

    @staticmethod
    def _parse_age_seconds(text: str) -> int:
        raw = str(text or "").strip().lower()
        if not raw:
            return 10**12
        match = re.search(r"(\d+)\s+(second|minute|hour|day|week|month|year)", raw)
        if not match:
            return 10**12
        value = int(match.group(1))
        unit = match.group(2)
        multipliers = {
            "second": 1,
            "minute": 60,
            "hour": 3600,
            "day": 86400,
            "week": 604800,
            "month": 2629800,
            "year": 31557600,
        }
        return value * multipliers.get(unit, 1)

    def _fetch_watch_meta(self, video_id: str) -> Dict[str, bool]:
        video_key = str(video_id or "").strip()
        if not video_key:
            return {"has_subtitles": False, "is_creative_commons": False}
        if video_key in self._watch_meta_cache:
            return self._watch_meta_cache[video_key]

        result = {"has_subtitles": False, "is_creative_commons": False}
        if not REQUESTS_INSTALLED or requests is None:
            self._watch_meta_cache[video_key] = result
            return result

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        response = _http_get(
            "https://www.youtube.com/watch",
            params={"v": video_key, "hl": "en"},
            headers=headers,
            timeout=25,
            proxies=self._next_requests_proxies(),
        )
        response.raise_for_status()
        page_html = _response_text_utf8(response)

        marker = "var ytInitialPlayerResponse = "
        blob = self._extract_json_blob(page_html, marker)
        if not blob:
            marker = 'window["ytInitialPlayerResponse"] = '
            blob = self._extract_json_blob(page_html, marker)
        if blob:
            try:
                player = json.loads(blob)
                captions = (
                    player.get("captions", {})
                    .get("playerCaptionsTracklistRenderer", {})
                    .get("captionTracks", [])
                )
                result["has_subtitles"] = bool(captions)
                license_text = (
                    player.get("microformat", {})
                    .get("playerMicroformatRenderer", {})
                    .get("license", "")
                )
                if "creative commons" in str(license_text or "").lower():
                    result["is_creative_commons"] = True
            except Exception:
                pass

        if not result["is_creative_commons"]:
            html_lc = page_html.lower()
            if "creative commons attribution license (reuse allowed)" in html_lc:
                result["is_creative_commons"] = True

        self._watch_meta_cache[video_key] = result
        return result

    def _matches_filters(self, video_id: str) -> bool:
        if not self.require_subtitles and not self.require_creative_commons:
            return True
        meta = self._fetch_watch_meta(video_id)
        if self.require_subtitles and not meta.get("has_subtitles", False):
            return False
        if self.require_creative_commons and not meta.get("is_creative_commons", False):
            return False
        return True

    def _sort_results(self, rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
        if not rows:
            return rows
        option = self.sort_by.lower()
        if option == "upload date":
            return sorted(rows, key=lambda r: int(r.get("_age_seconds", 10**12)))
        if option == "view count":
            return sorted(rows, key=lambda r: int(r.get("_view_count", 0)), reverse=True)
        # "Rating" is deprecated/unstable on YouTube search; keep relevance fallback.
        return rows

    def _fetch_youtube_videos(self) -> List[Dict[str, str]]:
        if not REQUESTS_INSTALLED or requests is None:
            raise ImportError("Dependency Error: requests is missing. Run: pip install requests")

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        params = {
            "search_query": self.query,
            "sp": "EgIQAQ%3D%3D",  # Video type filter.
            "hl": "en",
        }

        response = _http_get(
            "https://www.youtube.com/results",
            params=params,
            headers=headers,
            timeout=25,
            proxies=self._next_requests_proxies(),
        )
        response.raise_for_status()

        initial_data = self._extract_initial_data(_response_text_utf8(response))
        if not initial_data:
            raise RuntimeError("Could not parse YouTube search data. Try again in a few seconds.")

        results: List[Dict[str, str]] = []
        seen_ids = set()
        renderers = self._iter_video_renderers(initial_data)
        scan_limit = 20 if self.first_page_only else max(50, self.max_results * 4)
        scanned = 0

        for renderer in renderers:
            if not self._running:
                break

            video_id = str(renderer.get("videoId", "")).strip()
            if not video_id or video_id in seen_ids:
                continue
            scanned += 1
            if scanned > scan_limit:
                break

            title = self._extract_text(renderer.get("title"))
            description = self._extract_text(renderer.get("descriptionSnippet"))
            if not description:
                snippets = renderer.get("detailedMetadataSnippets", [])
                if isinstance(snippets, list) and snippets:
                    snippet_text = snippets[0].get("snippetText") if isinstance(snippets[0], dict) else {}
                    description = self._extract_text(snippet_text)
            if not self._matches_filters(video_id):
                continue

            view_text = self._extract_text(renderer.get("viewCountText")) or self._extract_text(
                renderer.get("shortViewCountText")
            )
            published_text = self._extract_text(renderer.get("publishedTimeText"))
            channel_name = self._extract_channel_name(renderer.get("ownerText")) or self._extract_channel_name(
                renderer.get("longBylineText")
            )
            channel_link = self._extract_channel_link(renderer.get("ownerText")) or self._extract_channel_link(
                renderer.get("longBylineText")
            )
            length_text = self._extract_text(renderer.get("lengthText"))
            view_count_num = self._parse_view_count_number(view_text)
            age_seconds = self._parse_age_seconds(published_text)
            age_days = int(age_seconds / 86400) if age_seconds < 10**11 else 0
            avg_views_per_day = int(view_count_num / max(1, age_days)) if age_days > 0 else 0

            payload = {
                "Video ID": video_id,
                "Video Link": f"https://www.youtube.com/watch?v={video_id}",
                "Source": "YouTube",
                "Search Phrase": self.query,
                "Title": title,
                "Description": description,
                "_view_count": view_count_num,
                "_age_seconds": age_seconds,
                "_published_text": published_text,
                "Thumbnail URL": self._normalize_thumbnail_url(
                    self._extract_thumbnail_url(renderer.get("thumbnail")),
                    video_id=video_id,
                ),
                "View Count": f"{view_count_num:,}" if view_count_num > 0 else "not-given",
                "Length Seconds": str(self._parse_length_seconds(length_text) or "not-given"),
                "Published": published_text or "not-given",
                "Published Age (Days)": str(age_days) if age_days > 0 else "not-given",
                "Avg. Views per Day": f"{avg_views_per_day:,}" if avg_views_per_day > 0 else "0",
                "Subtitles": "YES" if self.require_subtitles else "not-given",
                "Channel": channel_name,
                "Channel Link": channel_link,
            }
            payload.update(_default_video_row())
            payload["Length Seconds"] = str(self._parse_length_seconds(length_text) or "not-given")
            payload["View Count"] = f"{view_count_num:,}" if view_count_num > 0 else "not-given"
            payload["Published"] = published_text or "not-given"
            payload["Published Age (Days)"] = str(age_days) if age_days > 0 else "not-given"
            payload["Avg. Views per Day"] = f"{avg_views_per_day:,}" if avg_views_per_day > 0 else "0"
            payload["Subtitles"] = "YES" if self.require_subtitles else "not-given"
            payload["Channel"] = channel_name
            payload["Channel Link"] = channel_link
            seen_ids.add(video_id)
            results.append(payload)
            if len(results) >= self.max_results:
                break

        return self._sort_results(results)

    def run(self):
        if not self.query:
            self.error_signal.emit("Please enter a search phrase first.")
            self.finished_signal.emit({"count": 0})
            return

        try:
            tags = [f"sort={self.sort_by}"]
            if self.require_subtitles:
                tags.append("subtitles")
            if self.require_creative_commons:
                tags.append("creative_commons")
            if self.sort_by.lower() == "rating":
                tags.append("rating->relevance")
            self.status_signal.emit(f"Searching videos for '{self.query}' ({', '.join(tags)})...")
            videos = self._fetch_youtube_videos()
            total = len(videos)
            if total == 0:
                self.status_signal.emit("No videos found for this query.")
                self.finished_signal.emit({"count": 0})
                return

            for idx, video in enumerate(videos, start=1):
                if not self._running:
                    break
                self.video_signal.emit(video)
                self.status_signal.emit(f"Loaded {idx}/{total} videos for '{self.query}'...")

            if self._running:
                self.status_signal.emit(f"Done. Loaded {total} videos.")
                self.finished_signal.emit({"count": total})
            else:
                self.status_signal.emit("Stopped.")
                self.finished_signal.emit({"count": 0})
        except Exception as exc:
            self.error_signal.emit(str(exc))
            self.finished_signal.emit({"count": 0})


class ImportedLinksMetadataWorker(QThread):
    row_signal = pyqtSignal(dict)
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(dict)

    def __init__(
        self,
        rows: List[Dict[str, str]],
        retry_attempts: int = 3,
        retry_waits: Optional[List[float]] = None,
        use_proxies: bool = False,
        proxy_list: Optional[List[str]] = None,
    ):
        super().__init__()
        self.rows = list(rows)
        self._running = True
        self.retry_attempts = max(1, int(retry_attempts))
        waits = retry_waits or [1.0, 2.0]
        self.retry_waits = [max(0.0, float(v)) for v in waits]
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

    def _fetch_oembed(self, video_link: str) -> Dict[str, str]:
        if not REQUESTS_INSTALLED or requests is None:
            raise ImportError("Dependency Error: requests is missing. Run: pip install requests")

        params = {"url": video_link, "format": "json"}
        endpoint = f"https://www.youtube.com/oembed?{urlencode(params)}"
        response = _http_get(endpoint, timeout=15, proxies=self._next_requests_proxies())
        response.raise_for_status()
        payload = response.json()
        return {
            "title": str(payload.get("title", "")).strip(),
            "author_name": str(payload.get("author_name", "")).strip(),
            "thumbnail_url": str(payload.get("thumbnail_url", "")).strip(),
        }

    def _fetch_oembed_with_retry(self, video_link: str, idx: int, total: int):
        last_error_text = ""
        for attempt in range(1, self.retry_attempts + 1):
            if not self._running:
                break
            try:
                meta = self._fetch_oembed(video_link)
                return meta, ""
            except Exception as exc:
                last_error_text = str(exc).strip() or "Unknown metadata error"
                if attempt >= self.retry_attempts or not self._running:
                    break

                wait_seconds = self.retry_waits[min(attempt - 1, len(self.retry_waits) - 1)] if self.retry_waits else 0.0
                self.status_signal.emit(
                    f"Metadata error ({idx}/{total}) retry {attempt + 1}/{self.retry_attempts} in {int(round(wait_seconds))}s..."
                )
                if wait_seconds > 0:
                    time.sleep(wait_seconds)

        return None, last_error_text

    def run(self):
        total = len(self.rows)
        if total == 0:
            self.finished_signal.emit({"count": 0, "failed": 0, "failed_items": []})
            return

        success_count = 0
        failed_count = 0
        failed_items = []
        for idx, base_row in enumerate(self.rows, start=1):
            if not self._running:
                break

            video_link = str(base_row.get("Video Link", "")).strip()
            self.status_signal.emit(f"Fetching metadata ({idx}/{total})...")

            row = dict(base_row)
            meta, err_text = self._fetch_oembed_with_retry(video_link, idx, total)
            if meta is not None:
                if meta.get("title"):
                    row["Title"] = meta["title"]
                author = meta.get("author_name", "")
                if author:
                    row["Source"] = f"Imported ({author})"
                    row["Channel"] = author
                thumb = meta.get("thumbnail_url", "")
                if thumb:
                    row["Thumbnail URL"] = VideoSearchWorker._normalize_thumbnail_url(
                        thumb,
                        video_id=str(row.get("Video ID", "")).strip(),
                    )
                success_count += 1
            else:
                # Keep the row, only flag metadata fallback.
                failed_count += 1
                if not row.get("Title"):
                    row["Title"] = "(Metadata unavailable)"
                row["Metadata Error"] = err_text or "Metadata unavailable"
                failed_items.append(
                    {
                        "video_link": video_link,
                        "error": row["Metadata Error"],
                    }
                )

            self.row_signal.emit(row)

        if self._running:
            self.status_signal.emit(
                f"Import completed. Metadata loaded: {success_count}/{total}."
            )
            self.finished_signal.emit({"count": total, "failed": failed_count, "failed_items": failed_items})
        else:
            self.status_signal.emit("Import stopped.")
            self.finished_signal.emit({"count": success_count, "failed": failed_count, "failed_items": failed_items})


class TrendingVideosWorker(QThread):
    video_signal = pyqtSignal(dict)
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(dict)

    def __init__(
        self,
        region_code: str = "US",
        max_results: int = 20,
        use_proxies: bool = False,
        proxy_list: Optional[List[str]] = None,
    ):
        super().__init__()
        self.region_code = (region_code or "US").strip().upper()
        self.max_results = max(1, int(max_results))
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

    @staticmethod
    def _extract_video_id_from_youtube_url(url_text: str) -> str:
        url = str(url_text or "").strip()
        if not url:
            return ""
        if "youtu.be/" in url:
            tail = url.split("youtu.be/", 1)[1]
            return tail.split("?", 1)[0].split("&", 1)[0].split("/", 1)[0].strip()
        match = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", url)
        if match:
            return match.group(1).strip()
        match = re.search(r"/shorts/([A-Za-z0-9_-]{11})", url)
        if match:
            return match.group(1).strip()
        return ""

    def _fetch_kworb_trending(self) -> List[Dict[str, str]]:
        if not REQUESTS_INSTALLED or requests is None:
            return []

        kworb_slug_map = {
            "US": "us",
            "VN": "vn",
            "GB": "uk",
            "UK": "uk",
            "IN": "in",
            "JP": "jp",
            "KR": "kr",
            "BR": "br",
            "DE": "de",
            "FR": "fr",
        }
        country_slug = kworb_slug_map.get(self.region_code, self.region_code.lower())
        url = f"https://kworb.net/youtube/trending/{country_slug}.html"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        response = _http_get(url, headers=headers, timeout=25, proxies=self._next_requests_proxies())
        if response.status_code >= 400:
            return []

        html_text = _response_text_utf8(response)
        anchor_start = html_text.find("Videos trending in")
        if anchor_start > 0:
            html_text = html_text[anchor_start:]

        link_pattern = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
        rows: List[Dict[str, str]] = []
        seen_ids = set()
        for href, raw_title in link_pattern.findall(html_text):
            if not self._running:
                break
            if "youtu" not in href:
                continue
            video_id = self._extract_video_id_from_youtube_url(href)
            if not video_id or video_id in seen_ids:
                continue
            title = re.sub(r"<[^>]+>", "", raw_title or "")
            title = unescape(title).strip()
            if len(title) < 3:
                continue

            rows.append(
                {
                    "Video ID": video_id,
                    "Video Link": f"https://www.youtube.com/watch?v={video_id}",
                    "Source": "KWORB Trending",
                    "Search Phrase": f"Trending ({self.region_code})",
                    "Title": title,
                    "Description": "",
                    "Thumbnail URL": VideoSearchWorker._normalize_thumbnail_url("", video_id=video_id),
                    **_default_video_row(),
                }
            )
            seen_ids.add(video_id)
            if len(rows) >= self.max_results:
                break
        return rows

    def _fetch_trending_videos(self) -> List[Dict[str, str]]:
        if not REQUESTS_INSTALLED or requests is None:
            raise ImportError("Dependency Error: requests is missing. Run: pip install requests")

        kworb_rows = self._fetch_kworb_trending()
        if kworb_rows:
            return kworb_rows

        region_lang_map = {
            "US": "en-US,en;q=0.9",
            "VN": "vi-VN,vi;q=0.9,en;q=0.6",
            "GB": "en-GB,en;q=0.9",
            "IN": "en-IN,en;q=0.9,hi;q=0.7",
            "JP": "ja-JP,ja;q=0.9,en;q=0.5",
            "KR": "ko-KR,ko;q=0.9,en;q=0.5",
            "BR": "pt-BR,pt;q=0.9,en;q=0.5",
            "DE": "de-DE,de;q=0.9,en;q=0.5",
            "FR": "fr-FR,fr;q=0.9,en;q=0.5",
        }
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": region_lang_map.get(self.region_code, "en-US,en;q=0.9"),
        }

        parser = VideoSearchWorker(query="trending", max_results=self.max_results)
        def parse_from_html(page_html: str, source_name: str) -> List[Dict[str, str]]:
            initial_data = parser._extract_initial_data(page_html)
            if not initial_data:
                return []
            rows: List[Dict[str, str]] = []
            seen_ids = set()
            for renderer in parser._iter_video_renderers(initial_data):
                if not self._running:
                    break
                video_id = str(renderer.get("videoId", "")).strip()
                if not video_id or video_id in seen_ids:
                    continue

                title = parser._extract_text(renderer.get("title"))
                description = parser._extract_text(renderer.get("descriptionSnippet"))
                if not description:
                    snippets = renderer.get("detailedMetadataSnippets", [])
                    if isinstance(snippets, list) and snippets:
                        snippet_text = snippets[0].get("snippetText") if isinstance(snippets[0], dict) else {}
                        description = parser._extract_text(snippet_text)
                channel_name = parser._extract_channel_name(renderer.get("ownerText")) or parser._extract_channel_name(
                    renderer.get("longBylineText")
                )
                channel_link = parser._extract_channel_link(renderer.get("ownerText")) or parser._extract_channel_link(
                    renderer.get("longBylineText")
                )
                view_text = parser._extract_text(renderer.get("viewCountText")) or parser._extract_text(
                    renderer.get("shortViewCountText")
                )
                published_text = parser._extract_text(renderer.get("publishedTimeText"))
                length_text = parser._extract_text(renderer.get("lengthText"))
                view_count_num = parser._parse_view_count_number(view_text)
                age_seconds = parser._parse_age_seconds(published_text)
                age_days = int(age_seconds / 86400) if age_seconds < 10**11 else 0
                avg_views_per_day = int(view_count_num / max(1, age_days)) if age_days > 0 else 0

                rows.append(
                    {
                        **_default_video_row(),
                        "Video ID": video_id,
                        "Video Link": f"https://www.youtube.com/watch?v={video_id}",
                        "Source": source_name,
                        "Search Phrase": f"Trending ({self.region_code})",
                        "Title": title,
                        "Description": description,
                        "Thumbnail URL": parser._normalize_thumbnail_url(
                            parser._extract_thumbnail_url(renderer.get("thumbnail")),
                            video_id=video_id,
                        ),
                        "View Count": f"{view_count_num:,}" if view_count_num > 0 else "not-given",
                        "Length Seconds": str(parser._parse_length_seconds(length_text) or "not-given"),
                        "Published": published_text or "not-given",
                        "Published Age (Days)": str(age_days) if age_days > 0 else "not-given",
                        "Avg. Views per Day": f"{avg_views_per_day:,}" if avg_views_per_day > 0 else "0",
                        "Channel": channel_name,
                        "Channel Link": channel_link,
                    }
                )
                seen_ids.add(video_id)
                if len(rows) >= self.max_results:
                    break
            return rows

        primary_params = {"gl": self.region_code, "hl": "en", "persist_gl": "1", "persist_hl": "1"}
        primary_response = _http_get(
            "https://www.youtube.com/feed/trending",
            params=primary_params,
            headers=headers,
            timeout=25,
            proxies=self._next_requests_proxies(),
        )
        primary_response.raise_for_status()
        primary_html = _response_text_utf8(primary_response)
        if "consent.youtube.com" in str(primary_response.url or "") or "consent.youtube.com" in primary_html:
            self.status_signal.emit("Trending feed requires consent, switching to fallback...")
        else:
            primary_rows = parse_from_html(primary_html, "YouTube Trending")
            if primary_rows:
                return primary_rows

        # Fallback: use video search query with region to guarantee non-empty rows.
        self.status_signal.emit("Trending feed unavailable, using search fallback...")
        fallback_query_by_region = {
            "US": "trending videos usa",
            "VN": "video thịnh hành việt nam",
            "GB": "trending videos uk",
            "IN": "india trending videos",
            "JP": "日本 トレンド 動画",
            "KR": "한국 트렌드 동영상",
            "BR": "videos em alta brasil",
            "DE": "trending videos deutschland",
            "FR": "videos tendances france",
        }
        fallback_query = fallback_query_by_region.get(self.region_code, "trending videos")
        fallback_hl = "vi" if self.region_code == "VN" else "en"

        fallback_response = _http_get(
            "https://www.youtube.com/results",
            params={
                "search_query": fallback_query,
                "sp": "EgIQAQ%3D%3D",  # video filter
                "hl": fallback_hl,
                "gl": self.region_code,
                "persist_gl": "1",
                "persist_hl": "1",
            },
            headers=headers,
            timeout=25,
            proxies=self._next_requests_proxies(),
        )
        fallback_response.raise_for_status()
        fallback_rows = parse_from_html(_response_text_utf8(fallback_response), "YouTube Trending (fallback search)")
        if fallback_rows:
            return fallback_rows

        raise RuntimeError("Could not parse YouTube trending data for this region.")

    def run(self):
        try:
            self.status_signal.emit(f"Loading trending videos (region={self.region_code})...")
            videos = self._fetch_trending_videos()
            total = len(videos)
            if total == 0:
                self.status_signal.emit("No trending videos found for this region.")
                self.finished_signal.emit({"count": 0})
                return

            for idx, video in enumerate(videos, start=1):
                if not self._running:
                    break
                self.video_signal.emit(video)
                self.status_signal.emit(f"Loaded trending {idx}/{total} (region={self.region_code})...")

            if self._running:
                self.status_signal.emit(f"Done. Loaded {total} trending videos.")
                self.finished_signal.emit({"count": total})
            else:
                self.status_signal.emit("Trending load stopped.")
                self.finished_signal.emit({"count": 0})
        except Exception as exc:
            self.error_signal.emit(str(exc))
            self.finished_signal.emit({"count": 0})

