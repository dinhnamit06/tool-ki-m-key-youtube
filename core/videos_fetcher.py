import json
import re
import time
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


def _response_text_utf8(response) -> str:
    try:
        data = bytes(response.content or b"")
        if data:
            return data.decode("utf-8", errors="replace")
    except Exception:
        pass
    return str(getattr(response, "text", "") or "")


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
        response = requests.get(
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

        response = requests.get(
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

            payload = {
                "Video ID": video_id,
                "Video Link": f"https://www.youtube.com/watch?v={video_id}",
                "Source": "YouTube",
                "Search Phrase": self.query,
                "Title": title,
                "Description": description,
                "_view_count": self._parse_view_count_number(view_text),
                "_age_seconds": self._parse_age_seconds(published_text),
                "_published_text": published_text,
                "Thumbnail URL": self._normalize_thumbnail_url(
                    self._extract_thumbnail_url(renderer.get("thumbnail")),
                    video_id=video_id,
                ),
            }
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
        response = requests.get(endpoint, timeout=15, proxies=self._next_requests_proxies())
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
        response = requests.get(url, headers=headers, timeout=25, proxies=self._next_requests_proxies())
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

                rows.append(
                    {
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
                    }
                )
                seen_ids.add(video_id)
                if len(rows) >= self.max_results:
                    break
            return rows

        primary_params = {"gl": self.region_code, "hl": "en", "persist_gl": "1", "persist_hl": "1"}
        primary_response = requests.get(
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

        fallback_response = requests.get(
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

