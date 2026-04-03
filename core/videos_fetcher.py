import json
import time
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlencode

from PyQt6.QtCore import QThread, pyqtSignal

from utils.constants import REQUESTS_INSTALLED

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


class VideoSearchWorker(QThread):
    video_signal = pyqtSignal(dict)
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(dict)

    def __init__(self, query: str, max_results: int = 20):
        super().__init__()
        self.query = (query or "").strip()
        self.max_results = max(1, int(max_results))
        self._running = True

    def stop(self):
        self._running = False

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
        )
        response.raise_for_status()

        initial_data = self._extract_initial_data(response.text)
        if not initial_data:
            raise RuntimeError("Could not parse YouTube search data. Try again in a few seconds.")

        results: List[Dict[str, str]] = []
        seen_ids = set()
        renderers = self._iter_video_renderers(initial_data)

        for renderer in renderers:
            if not self._running:
                break

            video_id = str(renderer.get("videoId", "")).strip()
            if not video_id or video_id in seen_ids:
                continue

            title = self._extract_text(renderer.get("title"))
            description = self._extract_text(renderer.get("descriptionSnippet"))
            if not description:
                snippets = renderer.get("detailedMetadataSnippets", [])
                if isinstance(snippets, list) and snippets:
                    snippet_text = snippets[0].get("snippetText") if isinstance(snippets[0], dict) else {}
                    description = self._extract_text(snippet_text)

            payload = {
                "Video ID": video_id,
                "Video Link": f"https://www.youtube.com/watch?v={video_id}",
                "Source": "YouTube",
                "Search Phrase": self.query,
                "Title": title,
                "Description": description,
            }
            seen_ids.add(video_id)
            results.append(payload)
            if len(results) >= self.max_results:
                break

        return results

    def run(self):
        if not self.query:
            self.error_signal.emit("Please enter a search phrase first.")
            self.finished_signal.emit({"count": 0})
            return

        try:
            self.status_signal.emit(f"Searching videos for '{self.query}'...")
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
    ):
        super().__init__()
        self.rows = list(rows)
        self._running = True
        self.retry_attempts = max(1, int(retry_attempts))
        waits = retry_waits or [1.0, 2.0]
        self.retry_waits = [max(0.0, float(v)) for v in waits]

    def stop(self):
        self._running = False

    @staticmethod
    def _fetch_oembed(video_link: str) -> Dict[str, str]:
        if not REQUESTS_INSTALLED or requests is None:
            raise ImportError("Dependency Error: requests is missing. Run: pip install requests")

        params = {"url": video_link, "format": "json"}
        endpoint = f"https://www.youtube.com/oembed?{urlencode(params)}"
        response = requests.get(endpoint, timeout=15)
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
                    row["Thumbnail URL"] = thumb
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
