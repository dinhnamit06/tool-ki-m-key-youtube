from __future__ import annotations

from typing import Dict, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from core.video_to_text_fetcher import normalize_video_text_input

try:
    import yt_dlp
except ImportError:  # pragma: no cover
    yt_dlp = None


class CommentsLoadVideoWorker(QThread):
    status_signal = pyqtSignal(str)
    loaded_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, raw_input: str):
        super().__init__()
        self.raw_input = str(raw_input or "").strip()
        self._running = True

    def request_stop(self):
        self._running = False

    def _extract_with_ydlp(self, video_url: str) -> Dict[str, str]:
        if yt_dlp is None:
            raise ImportError("Dependency Error: yt-dlp is missing. Run: pip install yt-dlp")

        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
            "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(video_url, download=False) or {}

        upload_date = str(info.get("upload_date", "") or "").strip()
        posted = ""
        if len(upload_date) == 8 and upload_date.isdigit():
            posted = f"{upload_date[0:4]}-{upload_date[4:6]}-{upload_date[6:8]}"

        description = str(info.get("description", "") or "").strip()
        channel_url = (
            str(info.get("channel_url", "") or "").strip()
            or str(info.get("uploader_url", "") or "").strip()
        )
        channel_name = (
            str(info.get("channel", "") or "").strip()
            or str(info.get("uploader", "") or "").strip()
        )
        webpage_url = str(info.get("webpage_url", "") or "").strip() or video_url
        video_id = str(info.get("id", "") or "").strip()

        return {
            "input": self.raw_input,
            "normalized_url": video_url,
            "video_id": video_id,
            "title": str(info.get("title", "") or "").strip(),
            "channel_name": channel_name,
            "channel_url": channel_url,
            "description": description,
            "posted": posted,
            "duration": str(info.get("duration_string", "") or "").strip(),
            "view_count": str(info.get("view_count", "") or "").strip(),
            "comment_count": str(info.get("comment_count", "") or "").strip(),
            "thumbnail_url": str(info.get("thumbnail", "") or "").strip(),
            "webpage_url": webpage_url,
        }

    def run(self):
        try:
            self.status_signal.emit("Normalizing video target...")
            video_url = normalize_video_text_input(self.raw_input)
            if not video_url:
                raise ValueError("Please enter a valid YouTube video link or 11-character video ID.")
            if not self._running:
                return
            self.status_signal.emit("Loading video metadata...")
            payload = self._extract_with_ydlp(video_url)
            if not self._running:
                return
            self.loaded_signal.emit(payload)
        except Exception as exc:
            if self._running:
                self.error_signal.emit(str(exc).strip() or "Unable to load video metadata.")
        finally:
            self.finished_signal.emit()

