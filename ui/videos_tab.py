from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPixmap, QTextOption
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
import os
import webbrowser
import re
from collections import Counter
from urllib.parse import parse_qs, urlparse

from core.videos_fetcher import (
    ImportedLinksMetadataWorker,
    TrendingVideosWorker,
    VideoDownloadWorker,
    VideoSearchWorker,
    fetch_video_page_details,
)
from utils.constants import REQUESTS_INSTALLED

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


class ThumbnailFallbackWorker(QThread):
    finished_signal = pyqtSignal(str, bytes, str)

    def __init__(self, request_url):
        super().__init__()
        self.request_url = str(request_url or "").strip()

    def _candidate_urls(self):
        return VideoSearchWorker._thumbnail_candidates(self.request_url)

    def run(self):
        if not REQUESTS_INSTALLED or requests is None:
            self.finished_signal.emit(self.request_url, b"", "requests not installed")
            return

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": "https://www.youtube.com/",
        }

        last_error = "thumbnail download failed"
        for candidate in self._candidate_urls():
            try:
                response = requests.get(candidate, headers=headers, timeout=15)
                response.raise_for_status()
                content = bytes(response.content or b"")
                if content:
                    self.finished_signal.emit(self.request_url, content, "")
                    return
                last_error = "empty thumbnail response"
            except Exception as exc:
                last_error = str(exc).strip() or "thumbnail download failed"

        self.finished_signal.emit(self.request_url, b"", last_error)


class VideoDetailsWorker(QThread):
    details_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, video_id="", video_link="", proxy_url=""):
        super().__init__()
        self.video_id = str(video_id or "").strip()
        self.video_link = str(video_link or "").strip()
        self.proxy_url = str(proxy_url or "").strip()

    def run(self):
        try:
            details = fetch_video_page_details(
                video_id=self.video_id,
                video_link=self.video_link,
                proxy_url=self.proxy_url,
            )
            self.details_signal.emit(details)
        except Exception as exc:
            self.error_signal.emit(str(exc).strip() or "Unable to load full video details.")


class VideosFilterDialog(QDialog):
    def __init__(self, parent=None, sources=None, preset=None):
        super().__init__(parent)
        self.setWindowTitle("Filter Videos")
        self.setModal(True)
        self.setMinimumWidth(520)

        source_list = sorted({str(s).strip() for s in (sources or []) if str(s).strip()})
        source_list.insert(0, "All Sources")
        preset = dict(preset or {})

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        top_row.addWidget(QLabel("Source:"))
        self.combo_source = QComboBox()
        self.combo_source.addItems(source_list)
        self.combo_source.setCurrentText(preset.get("source", "All Sources"))
        top_row.addWidget(self.combo_source, stretch=1)
        root.addLayout(top_row)

        self.input_phrase = QLineEdit()
        self.input_phrase.setPlaceholderText("Search Phrase contains...")
        self.input_phrase.setText(preset.get("phrase", ""))
        root.addWidget(self.input_phrase)

        self.input_title = QLineEdit()
        self.input_title.setPlaceholderText("Title contains...")
        self.input_title.setText(preset.get("title", ""))
        root.addWidget(self.input_title)

        self.input_desc = QLineEdit()
        self.input_desc.setPlaceholderText("Description contains...")
        self.input_desc.setText(preset.get("description", ""))
        root.addWidget(self.input_desc)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_reset = QPushButton("Reset")
        self.btn_reset.clicked.connect(self._reset_fields)
        btn_row.addWidget(self.btn_reset)
        btn_row.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        btn_row.addWidget(buttons)
        root.addLayout(btn_row)

        self.setStyleSheet(
            "QDialog { background-color:#181b22; color:#f3f4f6; }"
            "QLabel { color:#f3f4f6; }"
            "QLineEdit, QComboBox { background:#ffffff; color:#111111; border:1px solid #c7c7c7; border-radius:4px; padding:6px 8px; }"
            "QPushButton { background-color:#2d3342; color:#ffffff; border:none; border-radius:4px; padding:6px 12px; }"
            "QPushButton:hover { background-color:#3c4356; }"
            "QDialogButtonBox QPushButton { background-color:#e50914; color:#ffffff; border:none; border-radius:4px; padding:6px 14px; font-weight:700; }"
            "QDialogButtonBox QPushButton:hover { background-color:#ff1a25; }"
        )

    def _reset_fields(self):
        self.combo_source.setCurrentIndex(0)
        self.input_phrase.clear()
        self.input_title.clear()
        self.input_desc.clear()

    def filter_values(self):
        return {
            "source": self.combo_source.currentText().strip(),
            "phrase": self.input_phrase.text().strip(),
            "title": self.input_title.text().strip(),
            "description": self.input_desc.text().strip(),
        }


class VideosSearchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Search In Table")
        self.setModal(False)
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        self.input_text = QLineEdit()
        self.input_text.setPlaceholderText("Type text to search in Title/Description/Link...")
        root.addWidget(self.input_text)

        self.lbl_info = QLabel("Enter a keyword and click Find.")
        root.addWidget(self.lbl_info)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.btn_find = QPushButton("Find")
        self.btn_prev = QPushButton("Prev")
        self.btn_next = QPushButton("Next")
        self.btn_close = QPushButton("Close")
        row.addWidget(self.btn_find)
        row.addWidget(self.btn_prev)
        row.addWidget(self.btn_next)
        row.addStretch()
        row.addWidget(self.btn_close)
        root.addLayout(row)

        self.setStyleSheet(
            "QDialog { background-color:#181b22; color:#f3f4f6; }"
            "QLabel { color:#f3f4f6; }"
            "QLineEdit { background:#ffffff; color:#111111; border:1px solid #c7c7c7; border-radius:4px; padding:6px 8px; }"
            "QPushButton { background-color:#2d3342; color:#ffffff; border:none; border-radius:4px; padding:6px 12px; }"
            "QPushButton:hover { background-color:#3c4356; }"
        )


class VideosAnalyzeDialog(QDialog):
    def __init__(self, parent=None, metrics=None):
        super().__init__(parent)
        self.setWindowTitle("Videos Analyze")
        self.setModal(True)
        self.setMinimumWidth(640)
        self.setMinimumHeight(420)
        data = dict(metrics or {})

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        def make_metric_card(title, value):
            frame = QFrame()
            frame.setStyleSheet("QFrame { background:#11151f; border:1px solid #2f3444; border-radius:6px; }")
            v = QVBoxLayout(frame)
            v.setContentsMargins(10, 8, 10, 8)
            v.setSpacing(2)
            lbl_title = QLabel(title)
            lbl_title.setStyleSheet("QLabel { color:#9aa3b2; font-size:12px; }")
            lbl_value = QLabel(value)
            lbl_value.setStyleSheet("QLabel { color:#ffffff; font-size:20px; font-weight:700; }")
            v.addWidget(lbl_title)
            v.addWidget(lbl_value)
            return frame

        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(make_metric_card("Total Videos", str(data.get("total_videos", 0))))
        top.addWidget(make_metric_card("Avg Title Length", data.get("avg_title_len", "0 words")))
        top.addWidget(make_metric_card("Missing Description", data.get("missing_desc_ratio", "0.0%")))
        root.addLayout(top)

        row_mid = QHBoxLayout()
        row_mid.setSpacing(10)

        left_box = QFrame()
        left_box.setStyleSheet("QFrame { background:#11151f; border:1px solid #2f3444; border-radius:6px; }")
        left_v = QVBoxLayout(left_box)
        left_v.setContentsMargins(10, 8, 10, 8)
        left_v.addWidget(QLabel("Source Ratio"))
        lbl_sources = QLabel(data.get("source_ratio_text", "-"))
        lbl_sources.setStyleSheet("QLabel { color:#f3f4f6; }")
        lbl_sources.setWordWrap(True)
        left_v.addWidget(lbl_sources)
        left_v.addStretch()
        row_mid.addWidget(left_box, stretch=1)

        right_box = QFrame()
        right_box.setStyleSheet("QFrame { background:#11151f; border:1px solid #2f3444; border-radius:6px; }")
        right_v = QVBoxLayout(right_box)
        right_v.setContentsMargins(10, 8, 10, 8)
        right_v.addWidget(QLabel("Top Repeated Terms (Title)"))
        lbl_terms = QLabel(data.get("top_terms_text", "-"))
        lbl_terms.setStyleSheet("QLabel { color:#f3f4f6; }")
        lbl_terms.setWordWrap(True)
        right_v.addWidget(lbl_terms)
        right_v.addStretch()
        row_mid.addWidget(right_box, stretch=1)

        root.addLayout(row_mid)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_close.setStyleSheet(
            "QPushButton { background-color:#e50914; color:#ffffff; border:none; border-radius:4px; padding:7px 14px; font-weight:700; }"
            "QPushButton:hover { background-color:#ff1a25; }"
        )
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        root.addLayout(btn_row)

        self.setStyleSheet(
            "QDialog { background-color:#181b22; color:#f3f4f6; }"
            "QLabel { color:#ffffff; }"
        )


class VideoDetailsDialog(QDialog):
    def __init__(self, parent=None, video_data=None):
        super().__init__(parent)
        self.setWindowTitle("Video Details")
        self.setModal(True)
        self.resize(920, 620)
        data = dict(video_data or {})

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(14)

        text_col = QVBoxLayout()
        text_col.setSpacing(10)

        title = QLabel(data.get("Title", "") or "(No title)")
        title.setWordWrap(True)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        title.setStyleSheet("QLabel { color:#ffffff; font-size:22px; font-weight:700; }")
        text_col.addWidget(title)
        self.lbl_title = title

        meta_frame = QFrame()
        meta_frame.setStyleSheet("QFrame { background:#11151f; border:1px solid #2f3444; border-radius:8px; }")
        meta_layout = QVBoxLayout(meta_frame)
        meta_layout.setContentsMargins(12, 10, 12, 10)
        meta_layout.setSpacing(6)
        self._meta_labels = {}
        for label in (
            "Video ID",
            "Video Link",
            "Thumbnail URL",
            "Source",
            "Search Phrase",
            "Channel Name",
            "Channel ID",
            "Channel URL",
            "View Count",
            "Length Seconds",
            "Publish Date",
            "Upload Date",
            "Category",
            "Title Length",
            "Description Length",
        ):
            row = QLabel()
            row.setTextFormat(Qt.TextFormat.RichText)
            row.setWordWrap(True)
            row.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.setStyleSheet("QLabel { color:#dbe4ee; font-size:13px; }")
            meta_layout.addWidget(row)
            self._meta_labels[label] = row
        text_col.addWidget(meta_frame, stretch=1)
        top_row.addLayout(text_col, stretch=1)

        thumb_frame = QFrame()
        thumb_frame.setMinimumWidth(280)
        thumb_frame.setMaximumWidth(320)
        thumb_frame.setStyleSheet("QFrame { background:#11151f; border:1px solid #2f3444; border-radius:8px; }")
        thumb_layout = QVBoxLayout(thumb_frame)
        thumb_layout.setContentsMargins(12, 12, 12, 12)
        thumb_layout.setSpacing(8)
        thumb_title = QLabel("Thumbnail Preview")
        thumb_title.setStyleSheet("QLabel { color:#ffffff; font-size:14px; font-weight:700; }")
        thumb_layout.addWidget(thumb_title)

        self.thumb_label = QLabel()
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setMinimumHeight(160)
        self.thumb_label.setStyleSheet("QLabel { background:#0f131b; border:1px solid #2f3444; border-radius:6px; color:#8a94a6; }")
        thumb_layout.addWidget(self.thumb_label, stretch=1)
        top_row.addWidget(thumb_frame)

        root.addLayout(top_row)

        lbl_desc = QLabel("Description")
        lbl_desc.setStyleSheet("QLabel { color:#ffffff; font-size:15px; font-weight:700; }")
        root.addWidget(lbl_desc)

        self.text_desc = QTextEdit()
        self.text_desc.setReadOnly(True)
        self.text_desc.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.text_desc.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.text_desc.setPlainText(data.get("Description", "") or "")
        self.text_desc.setStyleSheet(
            "QTextEdit { background:#0f131b; color:#f8fafc; border:1px solid #2f3444; border-radius:8px; padding:10px; }"
        )
        root.addWidget(self.text_desc, stretch=1)

        btn_open = QPushButton("Open Video")
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.setStyleSheet(
            "QPushButton { background-color:#2d3342; color:#ffffff; border:none; border-radius:4px; padding:8px 16px; font-weight:700; }"
            "QPushButton:hover { background-color:#3c4356; }"
        )
        btn_open.clicked.connect(lambda: webbrowser.open_new_tab(str(data.get("Video Link", "")).strip()))
        btn_open.setEnabled(bool(str(data.get("Video Link", "")).strip()))

        btn_copy = QPushButton("Copy Link")
        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy.setStyleSheet(
            "QPushButton { background-color:#2d3342; color:#ffffff; border:none; border-radius:4px; padding:8px 16px; font-weight:700; }"
            "QPushButton:hover { background-color:#3c4356; }"
        )
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(str(data.get("Video Link", "")).strip()))

        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(
            "QPushButton { background-color:#e50914; color:#ffffff; border:none; border-radius:4px; padding:8px 16px; font-weight:700; }"
            "QPushButton:hover { background-color:#ff1a25; }"
        )
        btn_close.clicked.connect(self.accept)

        row_btn = QHBoxLayout()
        row_btn.addWidget(btn_open)
        row_btn.addWidget(btn_copy)
        row_btn.addStretch()
        row_btn.addWidget(btn_close)
        root.addLayout(row_btn)

        self.setStyleSheet("QDialog { background-color:#181b22; color:#f3f4f6; }")
        self._populate_from_data(data)

    def _set_thumb_pixmap(self, pixmap):
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            self.thumb_label.setPixmap(
                pixmap.scaled(
                    280,
                    160,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            self.thumb_label.setText("")
        else:
            self.thumb_label.setPixmap(QPixmap())
            self.thumb_label.setText("No thumbnail preview")

    def _populate_from_data(self, data):
        title_text = str(data.get("Title", "") or "(No title)")
        desc_text = str(data.get("Description", "") or "")
        self.lbl_title.setText(title_text)

        values = {
            "Video ID": data.get("Video ID", ""),
            "Video Link": data.get("Video Link", ""),
            "Thumbnail URL": data.get("Thumbnail URL", ""),
            "Source": data.get("Source", ""),
            "Search Phrase": data.get("Search Phrase", ""),
            "Channel Name": data.get("Channel Name", ""),
            "Channel ID": data.get("Channel ID", ""),
            "Channel URL": data.get("Channel URL", ""),
            "View Count": data.get("View Count", ""),
            "Length Seconds": data.get("Length Seconds", ""),
            "Publish Date": data.get("Publish Date", ""),
            "Upload Date": data.get("Upload Date", ""),
            "Category": data.get("Category", ""),
            "Title Length": f"{len(title_text)} chars",
            "Description Length": f"{len(desc_text)} chars",
        }
        for label, widget in self._meta_labels.items():
            safe_value = str(values.get(label, "") or "").strip() or "-"
            widget.setText(f"<b>{label}:</b> {safe_value}")

        self.text_desc.setPlainText(desc_text)
        self._set_thumb_pixmap(data.get("Thumbnail Pixmap"))

    def apply_loaded_details(self, details, thumb_pixmap=None):
        merged = dict(details or {})
        if thumb_pixmap is not None:
            merged["Thumbnail Pixmap"] = thumb_pixmap
        self._populate_from_data(merged)


class VideosTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._mode = "search"
        self._checkbox_syncing = False
        self._search_worker = None
        self._trending_worker = None
        self._import_worker = None
        self._download_worker = None
        self._invalid_import_count = 0
        self._invalid_import_rows = []
        self._all_rows_cache = []
        self._active_filter = {"source": "All Sources", "phrase": "", "title": "", "description": ""}
        self._default_column_widths = {0: 26, 1: 94, 2: 100, 3: 210, 4: 76, 5: 120, 6: 250, 7: 320}
        self._table_search_dialog = None
        self._search_hits = []
        self._search_hit_index = -1
        self._search_term = ""
        self._thumbnail_cache = {}
        self._thumbnail_pending_rows = {}
        self._thumbnail_inflight = set()
        self._thumbnail_fallback_workers = {}
        self._thumbnail_manager = QNetworkAccessManager(self)
        self._thumbnail_manager.finished.connect(self._on_thumbnail_finished)
        self._dark_label_style = "QLabel { color: #f3f4f6; }"
        self._light_input_style = (
            "QLineEdit { background:#ffffff; color:#111111; border:1px solid #c7c7c7; border-radius:3px; padding:5px 8px; }"
            "QLineEdit:focus { border:1px solid #9c9c9c; }"
        )
        self._light_combo_style = (
            "QComboBox { background:#ffffff; color:#111111; border:1px solid #c7c7c7; border-radius:3px; padding:4px 8px; }"
            "QComboBox::drop-down { border: none; width: 20px; }"
            "QComboBox QAbstractItemView { background:#ffffff; color:#111111; border:1px solid #c7c7c7; selection-background-color:#e7e7e7; selection-color:#111111; }"
        )
        self._dark_checkbox_style = "QCheckBox { color:#f3f4f6; }"
        self._red_button_style = (
            "QPushButton { background-color:#e50914; color:#ffffff; border:none; border-radius:4px; padding:6px 12px; font-weight:700; }"
            "QPushButton:hover { background-color:#ff1a25; }"
        )
        self.setup_ui()

    def setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(10)

        title = QLabel("Videos Tool")
        title.setStyleSheet("QLabel { color:#ffffff; font-size:28px; font-weight:700; }")
        root.addWidget(title)

        self._build_mode_bar(root)
        body = QHBoxLayout()
        body.setSpacing(8)
        root.addLayout(body, stretch=1)

        left_panel = self._build_left_panel()
        right_panel = self._build_right_panel()

        body.addWidget(left_panel, stretch=0)
        body.addWidget(right_panel, stretch=1)

        self.switch_mode("search")
        self._update_status_labels()

    def _build_mode_bar(self, parent_layout):
        bar = QFrame()
        bar.setStyleSheet("QFrame { background-color: transparent; }")
        h = QHBoxLayout(bar)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)

        self.btn_mode_search = QPushButton("Search")
        self.btn_mode_browse = QPushButton("Browse or Import")
        self.btn_analyze = QPushButton("Analyze")

        for btn in (self.btn_mode_search, self.btn_mode_browse):
            btn.setFixedHeight(28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background-color: #2b2b2b; color: #f0f0f0; border: 1px solid #444444; border-radius: 4px; padding: 0 16px; font-weight: 600; }"
                "QPushButton:hover { background-color: #383838; }"
            )

        self.btn_analyze.setFixedHeight(28)
        self.btn_analyze.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_analyze.setStyleSheet(
            "QPushButton { background-color: #e50914; color: #ffffff; border: none; border-radius: 4px; padding: 0 16px; font-weight: 700; }"
            "QPushButton:hover { background-color: #ff1a25; }"
        )

        self.btn_mode_search.clicked.connect(lambda: self.switch_mode("search"))
        self.btn_mode_browse.clicked.connect(lambda: self.switch_mode("browse"))
        self.btn_analyze.clicked.connect(self.open_analyze_dialog)

        h.addWidget(self.btn_mode_search)
        h.addWidget(self.btn_mode_browse)
        h.addStretch()
        h.addWidget(self.btn_analyze)
        parent_layout.addWidget(bar)

    def _build_left_panel(self):
        panel = QFrame()
        panel.setMinimumWidth(250)
        panel.setMaximumWidth(270)
        panel.setStyleSheet("QFrame { background-color: #161922; border: 1px solid #2f3444; border-radius: 6px; }")
        v = QVBoxLayout(panel)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(10)

        self.left_stack = QStackedWidget()
        self.left_stack.addWidget(self._build_search_left_page())
        self.left_stack.addWidget(self._build_browse_left_page())
        v.addWidget(self.left_stack, stretch=1)
        return panel

    def _build_search_left_page(self):
        page = QWidget()
        page.setStyleSheet(self._dark_label_style)
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        self.input_search_phrase = QLineEdit()
        self.input_search_phrase.setPlaceholderText("Search Phrase")
        self.input_search_phrase.setStyleSheet(self._light_input_style)

        self.btn_search = QPushButton("Search")
        self.btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_search.setStyleSheet(self._red_button_style)
        self.btn_search.clicked.connect(self.start_search)

        self.btn_stop_search = QPushButton("Stop")
        self.btn_stop_search.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop_search.setEnabled(False)
        self.btn_stop_search.setStyleSheet(
            "QPushButton { background-color:#3c4253; color:#ffffff; border:none; border-radius:4px; padding:6px 12px; font-weight:700; }"
            "QPushButton:hover { background-color:#4a5166; }"
            "QPushButton:disabled { background-color:#2a2e3b; color:#8d92a3; }"
        )
        self.btn_stop_search.clicked.connect(self.stop_search)

        v.addWidget(QLabel("Search Phrase:"))
        v.addWidget(self.input_search_phrase)
        search_btn_row = QHBoxLayout()
        search_btn_row.setContentsMargins(0, 0, 0, 0)
        search_btn_row.setSpacing(8)
        search_btn_row.addWidget(self.btn_search)
        search_btn_row.addWidget(self.btn_stop_search)
        v.addLayout(search_btn_row)

        self.chk_youtube_first = QCheckBox("Youtube (first page results only)")
        self.chk_youtube_first.setChecked(True)
        self.chk_youtube_first.setStyleSheet(self._dark_checkbox_style)
        v.addWidget(self.chk_youtube_first)

        row_sort = QHBoxLayout()
        row_sort.addWidget(QLabel("Sort Youtube results by:"))
        self.combo_sort = QComboBox()
        self.combo_sort.addItems(["Relevance", "Upload date", "View count", "Rating"])
        self.combo_sort.setStyleSheet(self._light_combo_style)
        row_sort.addWidget(self.combo_sort, stretch=1)
        v.addLayout(row_sort)

        self.chk_contains_subtitles = QCheckBox("Contains subtitles")
        self.chk_creative_commons = QCheckBox("Creative Commons License")
        self.chk_contains_subtitles.setStyleSheet(self._dark_checkbox_style)
        self.chk_creative_commons.setStyleSheet(self._dark_checkbox_style)
        v.addWidget(self.chk_contains_subtitles)
        v.addWidget(self.chk_creative_commons)

        row_source = QHBoxLayout()
        self.chk_google = QCheckBox("Google")
        self.chk_google.setChecked(True)
        self.chk_bing = QCheckBox("Bing")
        self.chk_bing.setChecked(True)
        self.chk_google.setStyleSheet(self._dark_checkbox_style)
        self.chk_bing.setStyleSheet(self._dark_checkbox_style)
        row_source.addWidget(self.chk_google)
        row_source.addWidget(self.chk_bing)
        row_source.addSpacing(8)
        row_source.addWidget(QLabel("Pages:"))
        self.combo_pages = QComboBox()
        self.combo_pages.addItems([str(i) for i in range(1, 11)])
        self.combo_pages.setCurrentText("1")
        self.combo_pages.setStyleSheet(self._light_combo_style)
        row_source.addWidget(self.combo_pages)
        v.addLayout(row_source)

        v.addSpacing(6)
        v.addWidget(QLabel("Extract latest trending Youtube videos:"))
        row_trending = QHBoxLayout()
        row_trending.setContentsMargins(0, 0, 0, 0)
        row_trending.setSpacing(8)
        region_label = QLabel("Region:")
        self.combo_trending_region = QComboBox()
        self.combo_trending_region.setStyleSheet(self._light_combo_style)
        self.combo_trending_region.setMinimumWidth(130)
        trending_regions = [
            ("United States", "US"),
            ("Worldwide (best effort)", "US"),
            ("Vietnam", "VN"),
            ("United Kingdom", "GB"),
            ("India", "IN"),
            ("Japan", "JP"),
            ("South Korea", "KR"),
            ("Brazil", "BR"),
            ("Germany", "DE"),
            ("France", "FR"),
        ]
        for label, code in trending_regions:
            self.combo_trending_region.addItem(label, code)
        row_trending.addWidget(region_label)
        row_trending.addWidget(self.combo_trending_region, stretch=1)
        v.addLayout(row_trending)

        self.btn_trending_videos = QPushButton("Trending Videos")
        self.btn_trending_videos.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_trending_videos.setStyleSheet(self._red_button_style)
        self.btn_trending_videos.clicked.connect(self.start_trending_videos)
        v.addWidget(self.btn_trending_videos)
        v.addStretch()
        return page

    def _build_browse_left_page(self):
        page = QWidget()
        page.setStyleSheet(self._dark_label_style)
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        self.btn_get_data = QPushButton("Get Data")
        self.btn_get_data.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_get_data.setStyleSheet(self._red_button_style)
        self.btn_get_data.clicked.connect(self.import_links_to_table)

        self.btn_stop_import = QPushButton("Stop")
        self.btn_stop_import.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop_import.setEnabled(False)
        self.btn_stop_import.setStyleSheet(
            "QPushButton { background-color:#3c4253; color:#ffffff; border:none; border-radius:4px; padding:6px 12px; font-weight:700; }"
            "QPushButton:hover { background-color:#4a5166; }"
            "QPushButton:disabled { background-color:#2a2e3b; color:#8d92a3; }"
        )
        self.btn_stop_import.clicked.connect(self.stop_import)

        get_data_row = QHBoxLayout()
        get_data_row.setContentsMargins(0, 0, 0, 0)
        get_data_row.setSpacing(8)
        get_data_row.addWidget(self.btn_get_data)
        get_data_row.addWidget(self.btn_stop_import)
        v.addLayout(get_data_row)

        v.addWidget(QLabel("Extract video links by:"))
        row_type = QHBoxLayout()
        self.btn_browser_links = QPushButton("Browser")
        self.btn_content_links = QPushButton("Content")
        for btn in (self.btn_browser_links, self.btn_content_links):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._red_button_style)
        row_type.addWidget(self.btn_browser_links)
        row_type.addWidget(self.btn_content_links)
        v.addLayout(row_type)

        v.addWidget(QLabel("Youtube video links: ( one per line )"))
        self.input_video_links = QTextEdit()
        self.input_video_links.setPlaceholderText(
            "https://www.youtube.com/watch?v=abc123\n"
            "https://youtu.be/def456\n"
            "https://www.youtube.com/shorts/ghi789"
        )
        self.input_video_links.setMinimumHeight(120)
        self.input_video_links.setStyleSheet(
            "QTextEdit { background:#ffffff; color:#111111; border:1px solid #c7c7c7; border-radius:3px; padding:6px 8px; }"
            "QTextEdit:focus { border:1px solid #9c9c9c; }"
        )
        v.addWidget(self.input_video_links)
        self.lbl_import_hint = QLabel("Tips: support watch, youtu.be, and shorts links.")
        self.lbl_import_hint.setStyleSheet("QLabel { color:#b8bfd1; font-size:12px; }")
        v.addWidget(self.lbl_import_hint)
        v.addStretch()
        return page

    def _build_right_panel(self):
        panel = QFrame()
        panel.setStyleSheet("QFrame { background-color: #161922; border: 1px solid #2f3444; border-radius: 6px; }")
        v = QVBoxLayout(panel)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(6)

        self.videos_table = QTableWidget()
        self.videos_table.setColumnCount(8)
        self.videos_table.setHorizontalHeaderLabels(
            ["", "Image", "Video ID", "Video Link", "Source", "Search Phrase", "Title", "Description"]
        )
        self.videos_table.setAlternatingRowColors(False)
        self.videos_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.videos_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.videos_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.videos_table.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.videos_table.setFont(QFont("Segoe UI", 11))
        self.videos_table.verticalHeader().setVisible(False)
        self.videos_table.verticalHeader().setDefaultSectionSize(30)
        self.videos_table.itemChanged.connect(self._on_table_item_changed)
        self.videos_table.cellDoubleClicked.connect(self._on_table_cell_double_clicked)
        self.videos_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.videos_table.customContextMenuRequested.connect(self._on_table_context_menu)
        self.videos_table.setStyleSheet(
            "QTableWidget { background-color:#ffffff; color:#111111; gridline-color:#dddddd; border:1px solid #cfcfcf; }"
            "QHeaderView::section { background-color:#f0f0f0; color:#111111; border:1px solid #d0d0d0; font-weight:700; padding:4px; }"
        )

        header = self.videos_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Interactive)

        for col, width in self._default_column_widths.items():
            self.videos_table.setColumnWidth(col, width)

        v.addWidget(self.videos_table, stretch=1)

        slider_row = QHBoxLayout()
        slider_row.setContentsMargins(4, 0, 4, 0)
        slider_row.setSpacing(8)
        slider_label = QLabel("Image Size:")
        slider_label.setStyleSheet("QLabel { color:#f3f4f6; }")
        slider_row.addWidget(slider_label)
        self.slider_image_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_image_size.setRange(40, 140)
        self.slider_image_size.setValue(72)
        self.slider_image_size.valueChanged.connect(self._on_image_size_changed)
        self.lbl_image_size = QLabel("72 px")
        self.lbl_image_size.setMinimumWidth(44)
        self.lbl_image_size.setStyleSheet("QLabel { color:#f3f4f6; }")
        slider_row.addWidget(self.slider_image_size, stretch=1)
        slider_row.addWidget(self.lbl_image_size)
        v.addLayout(slider_row)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(4, 0, 4, 0)
        bottom.setSpacing(8)

        self.lbl_total_items = QLabel("Total Items: 0")
        self.lbl_status = QLabel("Ready.")
        self.lbl_selected_rows = QLabel("Selected rows: 0")
        self.lbl_total_items.setStyleSheet("color:#ffffff; font-weight:700;")
        self.lbl_status.setStyleSheet("color:#c9ccd6; font-weight:600;")
        self.lbl_selected_rows.setStyleSheet("color:#c9ccd6; font-weight:600;")

        self.btn_file = QPushButton("File")
        self.btn_filters = QPushButton("Filters")
        self.btn_clear = QPushButton("Clear")
        for btn in (self.btn_file, self.btn_filters, self.btn_clear):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._red_button_style)
        self.btn_file.clicked.connect(lambda: self._show_coming_soon("File"))
        self.btn_filters.clicked.connect(self.open_filters_dialog)
        self.btn_clear.clicked.connect(self._clear_all_video_data)

        bottom.addWidget(self.lbl_total_items)
        bottom.addStretch()
        bottom.addWidget(self.lbl_status)
        bottom.addStretch()
        bottom.addWidget(self.lbl_selected_rows)
        bottom.addStretch()
        bottom.addWidget(self.btn_file)
        bottom.addWidget(self.btn_filters)
        bottom.addWidget(self.btn_clear)
        v.addLayout(bottom)
        self._on_image_size_changed(self.slider_image_size.value())
        return panel

    def switch_mode(self, mode):
        self._mode = mode
        self.left_stack.setCurrentIndex(0 if mode == "search" else 1)
        self._apply_mode_button_styles()

    def _apply_mode_button_styles(self):
        active_style = (
            "QPushButton { background-color:#e50914; color:#ffffff; border:none; border-radius:4px; padding:0 16px; font-weight:700; }"
            "QPushButton:hover { background-color:#ff1a25; }"
        )
        inactive_style = (
            "QPushButton { background-color:#2b2b2b; color:#f0f0f0; border:1px solid #444444; border-radius:4px; padding:0 16px; font-weight:600; }"
            "QPushButton:hover { background-color:#383838; }"
        )
        self.btn_mode_search.setStyleSheet(active_style if self._mode == "search" else inactive_style)
        self.btn_mode_browse.setStyleSheet(active_style if self._mode == "browse" else inactive_style)

    def _on_image_size_changed(self, value):
        self.lbl_image_size.setText(f"{int(value)} px")
        height_px = max(22, int(value * 9 / 16))
        self.videos_table.verticalHeader().setDefaultSectionSize(max(28, height_px + 8))
        self._refresh_visible_thumbnails()

    def _on_table_item_changed(self, item):
        if self._checkbox_syncing:
            return
        if item is None or item.column() != 0:
            return
        self._update_status_labels()

    def _update_status_labels(self):
        total = self.videos_table.rowCount()
        checked = 0
        for row in range(total):
            item = self.videos_table.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                checked += 1
        self.lbl_total_items.setText(f"Total Items: {total}")
        self.lbl_selected_rows.setText(f"Selected rows: {checked}")

    def _clear_table_ui_only(self):
        self.videos_table.setRowCount(0)
        self._update_status_labels()
        self._reset_table_search_state()
        self._thumbnail_cache.clear()
        self._thumbnail_pending_rows.clear()
        self._thumbnail_inflight.clear()
        for url, worker in list(self._thumbnail_fallback_workers.items()):
            try:
                worker.finished_signal.disconnect(self._on_thumbnail_fallback_finished)
            except Exception:
                pass
            worker.quit()
            worker.wait(1000)
        self._thumbnail_fallback_workers.clear()

    def _clear_all_video_data(self):
        self._all_rows_cache = []
        self._active_filter = {"source": "All Sources", "phrase": "", "title": "", "description": ""}
        self._clear_table_ui_only()

    def _set_status(self, message):
        self.lbl_status.setText(message)
        if self.main_window is not None:
            self.main_window.statusBar().showMessage(message, 5000)

    def _set_search_running(self, running):
        download_running = self._download_worker is not None and self._download_worker.isRunning()
        self.btn_search.setEnabled((not running) and (not download_running))
        self.btn_stop_search.setEnabled(running)
        self.btn_trending_videos.setEnabled((not running) and (not download_running))

    def _set_import_running(self, running):
        download_running = self._download_worker is not None and self._download_worker.isRunning()
        self.btn_get_data.setEnabled((not running) and (not download_running))
        self.btn_stop_import.setEnabled(running)

    def _set_download_running(self, running):
        self.btn_search.setEnabled(not running)
        self.btn_trending_videos.setEnabled(not running)
        self.btn_get_data.setEnabled(not running)
        self.btn_stop_search.setEnabled(running or (self._search_worker is not None and self._search_worker.isRunning()))
        self.btn_stop_import.setEnabled(running or (self._import_worker is not None and self._import_worker.isRunning()))

    def _current_proxy_payload(self):
        if self.main_window is None or not hasattr(self.main_window, "get_proxy_settings"):
            return {"enabled": False, "proxies": []}
        settings = self.main_window.get_proxy_settings()
        max_proxy_count = 30
        if hasattr(self.main_window, "get_proxy_runtime_settings"):
            runtime_settings = self.main_window.get_proxy_runtime_settings()
            max_proxy_count = max(1, int(runtime_settings.get("max_proxies_per_run", 30)))
        proxy_list = list(settings.get("proxies", []))[:max_proxy_count]
        return {
            "enabled": bool(settings.get("enabled", False)),
            "proxies": proxy_list,
        }

    def start_search(self):
        query = self.input_search_phrase.text().strip()
        if not query:
            QMessageBox.warning(self, "Videos Tool", "Please enter a search phrase first.")
            return
        if self._download_worker is not None and self._download_worker.isRunning():
            QMessageBox.information(self, "Videos Tool", "Video download is running. Stop it before starting a new search.")
            return

        if self._search_worker is not None and self._search_worker.isRunning():
            QMessageBox.information(self, "Videos Tool", "Search is already running.")
            return
        if self._trending_worker is not None and self._trending_worker.isRunning():
            QMessageBox.information(self, "Videos Tool", "Trending load is already running.")
            return

        target_pages = int(self.combo_pages.currentText() or "1")
        max_results = max(5, min(100, target_pages * 20))
        first_page_only = self.chk_youtube_first.isChecked()
        if first_page_only:
            max_results = min(max_results, 20)

        sort_option = self.combo_sort.currentText().strip()
        require_subtitles = self.chk_contains_subtitles.isChecked()
        require_creative_commons = self.chk_creative_commons.isChecked()

        self._clear_all_video_data()
        self._set_search_running(True)
        filters_desc = []
        if require_subtitles:
            filters_desc.append("subtitles")
        if require_creative_commons:
            filters_desc.append("creative commons")
        filter_text = f" | filter: {', '.join(filters_desc)}" if filters_desc else ""
        self._set_status(f"Searching '{query}' | sort: {sort_option}{filter_text}...")
        proxy_payload = self._current_proxy_payload()

        self._search_worker = VideoSearchWorker(
            query=query,
            max_results=max_results,
            sort_by=sort_option,
            require_subtitles=require_subtitles,
            require_creative_commons=require_creative_commons,
            first_page_only=first_page_only,
            use_proxies=proxy_payload["enabled"],
            proxy_list=proxy_payload["proxies"],
        )
        self._search_worker.video_signal.connect(self._append_video_row)
        self._search_worker.status_signal.connect(self._set_status)
        self._search_worker.error_signal.connect(self._on_search_error)
        self._search_worker.finished_signal.connect(self._on_search_finished)
        self._search_worker.start()

    def stop_search(self):
        if self._search_worker is not None and self._search_worker.isRunning():
            self._search_worker.stop()
            self._set_status("Stopping search...")
        if self._trending_worker is not None and self._trending_worker.isRunning():
            self._trending_worker.stop()
            self._set_status("Stopping trending load...")
        if self._download_worker is not None and self._download_worker.isRunning():
            self._download_worker.stop()
            self._set_status("Stopping video download...")

    def start_trending_videos(self):
        if self._download_worker is not None and self._download_worker.isRunning():
            QMessageBox.information(self, "Videos Tool", "Video download is running. Stop it before loading trending videos.")
            return
        if self._search_worker is not None and self._search_worker.isRunning():
            QMessageBox.information(self, "Videos Tool", "Search is already running.")
            return
        if self._trending_worker is not None and self._trending_worker.isRunning():
            QMessageBox.information(self, "Videos Tool", "Trending load is already running.")
            return

        region_code = str(self.combo_trending_region.currentData() or "US").strip().upper()
        region_label = self.combo_trending_region.currentText().strip() or region_code
        target_pages = int(self.combo_pages.currentText() or "1")
        max_results = max(5, min(100, target_pages * 20))
        if self.chk_youtube_first.isChecked():
            max_results = min(max_results, 20)

        self._clear_all_video_data()
        self._set_search_running(True)
        self._set_status(f"Loading trending videos for {region_label}...")
        proxy_payload = self._current_proxy_payload()

        self._trending_worker = TrendingVideosWorker(
            region_code=region_code,
            max_results=max_results,
            use_proxies=proxy_payload["enabled"],
            proxy_list=proxy_payload["proxies"],
        )
        self._trending_worker.video_signal.connect(self._append_video_row)
        self._trending_worker.status_signal.connect(self._set_status)
        self._trending_worker.error_signal.connect(self._on_search_error)
        self._trending_worker.finished_signal.connect(self._on_trending_finished)
        self._trending_worker.start()

    def stop_import(self):
        if self._import_worker is not None and self._import_worker.isRunning():
            self._import_worker.stop()
            self._set_status("Stopping import...")
        if self._download_worker is not None and self._download_worker.isRunning():
            self._download_worker.stop()
            self._set_status("Stopping video download...")

    @staticmethod
    def _extract_video_id_from_url(url_text):
        url = (url_text or "").strip()
        if not url:
            return ""

        if "://" not in url:
            url = f"https://{url}"

        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        path = (parsed.path or "").strip("/")

        if host.endswith("youtu.be"):
            return path.split("/")[0] if path else ""

        if "youtube.com" in host:
            if path == "watch":
                query = parse_qs(parsed.query)
                return (query.get("v", [""])[0] or "").strip()
            if path.startswith("shorts/"):
                return path.split("/", 1)[1].split("/")[0]
            if path.startswith("live/"):
                return path.split("/", 1)[1].split("/")[0]

        # fallback for pasted plain video IDs
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", url_text.strip()):
            return url_text.strip()
        return ""

    def _parse_import_links(self, raw_text):
        rows = []
        invalid = []
        seen_ids = set()

        for raw_line in (raw_text or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue

            video_id = self._extract_video_id_from_url(line)
            if not video_id:
                invalid.append(line)
                continue
            if video_id in seen_ids:
                continue

            seen_ids.add(video_id)
            canonical = f"https://www.youtube.com/watch?v={video_id}"
            rows.append(
                {
                    "Video ID": video_id,
                    "Video Link": canonical,
                    "Source": "Imported",
                    "Search Phrase": "Browse Import",
                    "Title": "(Imported link)",
                    "Description": line,
                }
            )
        return rows, invalid

    def import_links_to_table(self):
        if self._download_worker is not None and self._download_worker.isRunning():
            QMessageBox.information(self, "Videos Tool", "Video download is running. Stop it before importing links.")
            return
        if self._import_worker is not None and self._import_worker.isRunning():
            QMessageBox.information(self, "Videos Tool", "Import is already running.")
            return

        raw_text = self.input_video_links.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "Videos Tool", "Please paste at least one YouTube link.")
            return

        parsed_rows, invalid_rows = self._parse_import_links(raw_text)
        if not parsed_rows:
            QMessageBox.warning(self, "Videos Tool", "No valid YouTube links found.")
            self._set_status("Import failed: no valid links.")
            return

        self._clear_all_video_data()
        self._invalid_import_count = len(invalid_rows)
        self._invalid_import_rows = list(invalid_rows)
        self._set_import_running(True)
        self._set_status(f"Importing {len(parsed_rows)} links and fetching metadata...")
        proxy_payload = self._current_proxy_payload()

        self._import_worker = ImportedLinksMetadataWorker(
            parsed_rows,
            use_proxies=proxy_payload["enabled"],
            proxy_list=proxy_payload["proxies"],
        )
        self._import_worker.row_signal.connect(self._append_video_row)
        self._import_worker.status_signal.connect(self._set_status)
        self._import_worker.error_signal.connect(self._on_import_error)
        self._import_worker.finished_signal.connect(self._on_import_finished)
        self._import_worker.start()

    def _on_search_error(self, error_text):
        QMessageBox.warning(self, "Videos Tool", error_text)

    def _on_import_error(self, error_text):
        QMessageBox.warning(self, "Videos Tool", error_text)

    def _on_import_finished(self, result):
        self._set_import_running(False)
        count = int((result or {}).get("count", 0))
        failed = int((result or {}).get("failed", 0))
        failed_items = list((result or {}).get("failed_items", []))

        suffix_parts = []
        if self._invalid_import_count > 0:
            suffix_parts.append(f"skipped invalid: {self._invalid_import_count}")
        if failed > 0:
            suffix_parts.append(f"metadata unavailable: {failed}")
        suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""

        self._set_status(f"Import finished: {count} rows{suffix}.")
        if self._invalid_import_count > 0 or failed > 0:
            details = []
            if self._invalid_import_count > 0:
                details.append(f"Invalid links skipped: {self._invalid_import_count}")
                preview_invalid = self._invalid_import_rows[:3]
                if preview_invalid:
                    details.append("Examples:")
                    for line in preview_invalid:
                        details.append(f"- {line}")
            if failed > 0:
                details.append(f"Metadata failed after retry: {failed}")
                preview_failed = failed_items[:3]
                for item in preview_failed:
                    link = str(item.get("video_link", "")).strip()
                    err = str(item.get("error", "")).strip()
                    if link:
                        details.append(f"- {link}")
                    if err:
                        details.append(f"  reason: {err[:140]}")
            QMessageBox.information(self, "Import Summary", "\n".join(details))

        self._invalid_import_rows = []
        self._invalid_import_count = 0
        self._import_worker = None

    def _on_search_finished(self, result):
        self._set_search_running(False)
        count = int((result or {}).get("count", 0))
        if count > 0:
            self._set_status(f"Done. Loaded {count} videos.")
        else:
            self._set_status("Search finished.")
        self._search_worker = None

    def _on_trending_finished(self, result):
        self._set_search_running(False)
        count = int((result or {}).get("count", 0))
        if count > 0:
            self._set_status(f"Done. Loaded {count} trending videos.")
        else:
            self._set_status("Trending load finished.")
        self._trending_worker = None

    def _append_video_row(self, video):
        if video is None:
            return
        row_dict = {
            "Video ID": str(video.get("Video ID", "")).strip(),
            "Video Link": str(video.get("Video Link", "")).strip(),
            "Source": str(video.get("Source", "YouTube")).strip(),
            "Search Phrase": str(video.get("Search Phrase", "")).strip(),
            "Title": str(video.get("Title", "")).strip(),
            "Description": str(video.get("Description", "")).strip(),
            "Thumbnail URL": str(video.get("Thumbnail URL", "")).strip(),
        }
        self._all_rows_cache.append(dict(row_dict))
        if not self._row_matches_filter(row_dict, self._active_filter):
            return

        row = self.videos_table.rowCount()
        self.videos_table.insertRow(row)

        checkbox_item = QTableWidgetItem("")
        checkbox_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        checkbox_item.setCheckState(Qt.CheckState.Unchecked)
        self.videos_table.setItem(row, 0, checkbox_item)

        thumb_item = QTableWidgetItem("N/A")
        thumb_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_item.setForeground(QColor("#666666"))
        thumb_url = VideoSearchWorker._normalize_thumbnail_url(
            row_dict.get("Thumbnail URL", ""),
            video_id=row_dict.get("Video ID", ""),
        )
        if thumb_url:
            thumb_item.setText("...")
            thumb_item.setForeground(QColor("#1a73e8"))
            thumb_item.setToolTip(thumb_url)
        self.videos_table.setItem(row, 1, thumb_item)
        if thumb_url:
            self._queue_thumbnail_load(row, thumb_url)

        values = [
            row_dict.get("Video ID", ""),
            row_dict.get("Video Link", ""),
            row_dict.get("Source", "YouTube"),
            row_dict.get("Search Phrase", ""),
            row_dict.get("Title", ""),
            row_dict.get("Description", ""),
        ]

        for col_offset, text in enumerate(values, start=2):
            item = QTableWidgetItem(str(text))
            if col_offset in (2, 4):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

            if col_offset == 3:
                # Keep valid full URL and show as link-like text in the table.
                link_text = str(text).strip()
                if link_text.startswith("www.youtube.com/"):
                    link_text = f"https://{link_text}"
                if link_text and "youtube.com/watch?v=" not in link_text:
                    video_id = row_dict.get("Video ID", "")
                    if video_id:
                        link_text = f"https://www.youtube.com/watch?v={video_id}"
                        item.setText(link_text)
                if link_text.startswith("http://") or link_text.startswith("https://"):
                    item.setForeground(QColor("#1a73e8"))
                    item.setToolTip(link_text)
            elif col_offset in (6, 7):
                item.setToolTip(str(text))
            self.videos_table.setItem(row, col_offset, item)

        # Keep the Title column wide enough to show full text (with horizontal scrolling if needed).
        self.videos_table.resizeColumnToContents(6)
        self.videos_table.scrollToBottom()
        self._update_status_labels()

    def _on_table_cell_double_clicked(self, row, column):
        if column != 3:
            return
        item = self.videos_table.item(row, column)
        if item is None:
            return
        link = item.text().strip()
        if link.startswith("http://") or link.startswith("https://"):
            webbrowser.open_new_tab(link)

    @staticmethod
    def _row_matches_filter(row, flt):
        source = str((flt or {}).get("source", "All Sources")).strip()
        phrase = str((flt or {}).get("phrase", "")).strip().lower()
        title = str((flt or {}).get("title", "")).strip().lower()
        desc = str((flt or {}).get("description", "")).strip().lower()

        if source and source != "All Sources":
            if str(row.get("Source", "")).strip() != source:
                return False
        if phrase and phrase not in str(row.get("Search Phrase", "")).lower():
            return False
        if title and title not in str(row.get("Title", "")).lower():
            return False
        if desc and desc not in str(row.get("Description", "")).lower():
            return False
        return True

    def _sources_from_cache(self):
        return sorted({str(r.get("Source", "")).strip() for r in self._all_rows_cache if str(r.get("Source", "")).strip()})

    def _draw_row_without_caching(self, row_dict):
        row = self.videos_table.rowCount()
        self.videos_table.insertRow(row)

        checkbox_item = QTableWidgetItem("")
        checkbox_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        checkbox_item.setCheckState(Qt.CheckState.Unchecked)
        self.videos_table.setItem(row, 0, checkbox_item)

        thumb_item = QTableWidgetItem("N/A")
        thumb_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_item.setForeground(QColor("#666666"))
        thumb_url = VideoSearchWorker._normalize_thumbnail_url(
            str(row_dict.get("Thumbnail URL", "")).strip(),
            video_id=str(row_dict.get("Video ID", "")).strip(),
        )
        if thumb_url:
            thumb_item.setText("...")
            thumb_item.setForeground(QColor("#1a73e8"))
            thumb_item.setToolTip(thumb_url)
        self.videos_table.setItem(row, 1, thumb_item)
        if thumb_url:
            self._queue_thumbnail_load(row, thumb_url)

        values = [
            row_dict.get("Video ID", ""),
            row_dict.get("Video Link", ""),
            row_dict.get("Source", "YouTube"),
            row_dict.get("Search Phrase", ""),
            row_dict.get("Title", ""),
            row_dict.get("Description", ""),
        ]
        for col_offset, text in enumerate(values, start=2):
            item = QTableWidgetItem(str(text))
            if col_offset in (2, 4):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            if col_offset == 3:
                link_text = str(text).strip()
                if link_text and not link_text.startswith("http"):
                    video_id = str(row_dict.get("Video ID", "")).strip()
                    if video_id:
                        link_text = f"https://www.youtube.com/watch?v={video_id}"
                        item.setText(link_text)
                if link_text.startswith("http://") or link_text.startswith("https://"):
                    item.setForeground(QColor("#1a73e8"))
                    item.setToolTip(link_text)
            elif col_offset in (6, 7):
                item.setToolTip(str(text))
            self.videos_table.setItem(row, col_offset, item)

    def _rebuild_table_from_cache(self):
        self._reset_table_search_state()
        self.videos_table.setRowCount(0)
        self._thumbnail_pending_rows.clear()
        self._thumbnail_inflight.clear()
        for row_dict in self._all_rows_cache:
            if self._row_matches_filter(row_dict, self._active_filter):
                self._draw_row_without_caching(row_dict)
        self.videos_table.resizeColumnToContents(6)
        self._update_status_labels()
        self._set_status(f"Filter applied: {self.videos_table.rowCount()} / {len(self._all_rows_cache)} rows.")

    def open_filters_dialog(self):
        dlg = VideosFilterDialog(self, sources=self._sources_from_cache(), preset=self._active_filter)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._active_filter = dlg.filter_values()
        self._rebuild_table_from_cache()

    def reset_video_filters(self):
        self._active_filter = {"source": "All Sources", "phrase": "", "title": "", "description": ""}
        self._rebuild_table_from_cache()

    def auto_fit_column_widths(self):
        if self.videos_table.columnCount() == 0:
            return
        header = self.videos_table.horizontalHeader()
        for col in range(self.videos_table.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
            self.videos_table.resizeColumnToContents(col)
        # Keep fixed behavior for checkbox/image columns after auto-fit.
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.videos_table.setColumnWidth(0, self._default_column_widths[0])
        self.videos_table.setColumnWidth(1, self._default_column_widths[1])
        self._set_status("Auto-fit column widths applied.")

    def reset_column_widths(self):
        if self.videos_table.columnCount() == 0:
            return
        header = self.videos_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Interactive)
        for col, width in self._default_column_widths.items():
            self.videos_table.setColumnWidth(col, width)
        self._set_status("Column widths reset.")

    def _reset_table_search_state(self):
        self._search_hits = []
        self._search_hit_index = -1
        self._search_term = ""
        self._clear_table_search_highlight()

    def _clear_table_search_highlight(self):
        for row in range(self.videos_table.rowCount()):
            for col in range(2, self.videos_table.columnCount()):
                item = self.videos_table.item(row, col)
                if item is not None:
                    item.setBackground(QColor("#ffffff"))

    def _find_table_hits(self, term):
        needle = str(term or "").strip().lower()
        self._clear_table_search_highlight()
        self._search_hits = []
        self._search_hit_index = -1
        self._search_term = needle
        if not needle:
            return

        for row in range(self.videos_table.rowCount()):
            for col in range(2, self.videos_table.columnCount()):
                item = self.videos_table.item(row, col)
                if item is None:
                    continue
                value = item.text().strip().lower()
                if needle in value:
                    item.setBackground(QColor("#fff0a8"))
                    self._search_hits.append((row, col))

    def _jump_to_search_hit(self, direction=1):
        if not self._search_hits:
            return
        total = len(self._search_hits)
        self._search_hit_index = (self._search_hit_index + direction) % total
        row, col = self._search_hits[self._search_hit_index]
        target = self.videos_table.item(row, col)
        if target is None:
            return
        self.videos_table.setCurrentCell(row, col)
        self.videos_table.scrollToItem(target, QTableWidget.ScrollHint.PositionAtCenter)
        if self._table_search_dialog is not None:
            self._table_search_dialog.lbl_info.setText(
                f"Match {self._search_hit_index + 1}/{total} for '{self._search_term}'."
            )
        self._set_status(f"Search match {self._search_hit_index + 1}/{total} for '{self._search_term}'.")

    def open_table_search_dialog(self):
        if self._table_search_dialog is None:
            dlg = VideosSearchDialog(self)
            dlg.btn_find.clicked.connect(self._on_find_in_table)
            dlg.btn_next.clicked.connect(lambda: self._jump_to_search_hit(+1))
            dlg.btn_prev.clicked.connect(lambda: self._jump_to_search_hit(-1))
            dlg.btn_close.clicked.connect(dlg.close)
            dlg.input_text.returnPressed.connect(self._on_find_in_table)
            self._table_search_dialog = dlg
        self._table_search_dialog.show()
        self._table_search_dialog.raise_()
        self._table_search_dialog.activateWindow()
        self._table_search_dialog.input_text.setFocus()
        self._table_search_dialog.input_text.selectAll()

    def _on_find_in_table(self):
        if self._table_search_dialog is None:
            return
        term = self._table_search_dialog.input_text.text().strip()
        self._find_table_hits(term)
        if not self._search_hits:
            self._table_search_dialog.lbl_info.setText("No matches found.")
            self._set_status("No table search matches.")
            return
        self._search_hit_index = -1
        self._jump_to_search_hit(+1)

    def _checked_rows(self):
        rows = []
        for row in range(self.videos_table.rowCount()):
            item = self.videos_table.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                rows.append(row)
        return rows

    def _set_row_check_state(self, rows, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        changed = 0
        for row in sorted(set(rows)):
            item = self.videos_table.item(row, 0)
            if item is None:
                continue
            if item.checkState() != state:
                item.setCheckState(state)
                changed += 1
        if changed:
            self._update_status_labels()

    def _set_all_check_state(self, checked):
        self._set_row_check_state(list(range(self.videos_table.rowCount())), checked)

    def _selected_rows_from_highlight(self):
        if self.videos_table.selectionModel() is None:
            return []
        row_set = {idx.row() for idx in self.videos_table.selectionModel().selectedRows()}
        return sorted(row_set)

    def _effective_selected_rows(self):
        checked = self._checked_rows()
        if checked:
            return checked
        return self._selected_rows_from_highlight()

    def _video_link_for_row(self, row):
        item = self.videos_table.item(row, 3)
        if item is None:
            return ""
        text = item.text().strip()
        if text.startswith("http://") or text.startswith("https://"):
            return text
        return ""

    def _row_payload(self, row):
        if row < 0 or row >= self.videos_table.rowCount():
            return {}
        thumb_item = self.videos_table.item(row, 1)
        thumb_url = thumb_item.toolTip().strip() if thumb_item is not None else ""
        thumb_pixmap = self._thumbnail_cache.get(thumb_url)
        if thumb_pixmap is None and thumb_item is not None:
            thumb_pixmap = thumb_item.data(Qt.ItemDataRole.DecorationRole)
        return {
            "Video ID": self.videos_table.item(row, 2).text().strip() if self.videos_table.item(row, 2) else "",
            "Video Link": self.videos_table.item(row, 3).text().strip() if self.videos_table.item(row, 3) else "",
            "Source": self.videos_table.item(row, 4).text().strip() if self.videos_table.item(row, 4) else "",
            "Search Phrase": self.videos_table.item(row, 5).text().strip() if self.videos_table.item(row, 5) else "",
            "Title": self.videos_table.item(row, 6).text().strip() if self.videos_table.item(row, 6) else "",
            "Description": self.videos_table.item(row, 7).text().strip() if self.videos_table.item(row, 7) else "",
            "Thumbnail URL": thumb_url,
            "Thumbnail Pixmap": thumb_pixmap,
        }

    def _collect_video_payloads(self, rows):
        payloads = []
        for row in sorted(set(rows)):
            data = self._row_payload(row)
            if data:
                payloads.append(data)
        return payloads

    def _require_rows(self, rows, feature_name):
        if rows:
            return True
        QMessageBox.warning(self, "Videos Tool", f"Please select at least one row for {feature_name}.")
        return False

    def _send_selected_video_to_comments_tool(self, rows):
        if not self._require_rows(rows, "Comments tool"):
            return
        links = [row.get("Video Link", "") for row in self._collect_video_payloads(rows) if row.get("Video Link", "")]
        if not links:
            QMessageBox.warning(self, "Videos Tool", "No valid video links found in the selected rows.")
            return
        if self.main_window.handle_send_videos_to_comments(links):
            self._set_status(f"Sent {len(links)} video link(s) to Comments tool.")

    def _send_to_channel_tool(self, rows, all_rows=False):
        if not all_rows and not self._require_rows(rows, "Channel tool"):
            return
        target_rows = list(range(self.videos_table.rowCount())) if all_rows else rows
        payloads = self._collect_video_payloads(target_rows)
        if not payloads:
            QMessageBox.warning(self, "Videos Tool", "No rows available to send to Channel tool.")
            return
        label = "ALL rows from Videos tool" if all_rows else "SELECTED rows from Videos tool"
        if self.main_window.handle_send_videos_to_channels(payloads, source_label=label):
            self._set_status(f"Sent {len(payloads)} item(s) to Channel tool.")

    def _convert_selected_video_to_text(self, rows):
        if not self._require_rows(rows, "Video to Text"):
            return
        links = [row.get("Video Link", "") for row in self._collect_video_payloads(rows) if row.get("Video Link", "")]
        if not links:
            QMessageBox.warning(self, "Videos Tool", "No valid video links found in the selected rows.")
            return
        if self.main_window.handle_send_videos_to_text(links):
            self._set_status(f"Sent {len(links)} video link(s) to Video to Text.")

    def _show_video_details_for_row(self, row):
        data = self._row_payload(row)
        if not data:
            QMessageBox.warning(self, "Videos Tool", "Please choose a video row first.")
            return
        dlg = VideoDetailsDialog(self, video_data=data)
        proxy_payload = self._current_proxy_payload()
        proxy_url = proxy_payload["proxies"][0] if proxy_payload.get("enabled") and proxy_payload.get("proxies") else ""
        worker = VideoDetailsWorker(
            video_id=data.get("Video ID", ""),
            video_link=data.get("Video Link", ""),
            proxy_url=proxy_url,
        )
        def _apply(details):
            merged = dict(data)
            merged.update({k: v for k, v in (details or {}).items() if str(v or "").strip()})
            thumb_url = str(merged.get("Thumbnail URL", "")).strip()
            thumb_pixmap = self._thumbnail_cache.get(thumb_url) if thumb_url else None
            dlg.apply_loaded_details(merged, thumb_pixmap=thumb_pixmap)
        worker.details_signal.connect(_apply)
        worker.error_signal.connect(lambda _msg: None)
        worker.finished.connect(worker.deleteLater)
        worker.start()
        dlg._details_worker = worker
        dlg.exec()

    def _download_selected_videos(self, rows):
        if not self._require_rows(rows, "Download video"):
            return
        if self._download_worker is not None and self._download_worker.isRunning():
            QMessageBox.information(self, "Videos Tool", "A video download is already running.")
            return

        payloads = [row for row in self._collect_video_payloads(rows) if row.get("Video Link", "")]
        if not payloads:
            QMessageBox.warning(self, "Videos Tool", "No valid video links found in the selected rows.")
            return

        default_dir = os.path.join(os.path.expanduser("~"), "Downloads", "TubeVibe Videos")
        target_dir = QFileDialog.getExistingDirectory(
            self,
            "Choose Download Folder",
            default_dir,
            QFileDialog.Option.ShowDirsOnly,
        )
        if not target_dir:
            return

        proxy_payload = self._current_proxy_payload()
        proxy_url = proxy_payload["proxies"][0] if proxy_payload.get("enabled") and proxy_payload.get("proxies") else ""

        self._download_worker = VideoDownloadWorker(
            video_rows=payloads,
            output_dir=target_dir,
            proxy_url=proxy_url,
        )
        self._download_worker.status_signal.connect(self._set_status)
        self._download_worker.error_signal.connect(self._on_search_error)
        self._download_worker.finished_signal.connect(self._on_download_finished)
        self._set_download_running(True)
        self._set_status(
            f"Starting download for {len(payloads)} video(s) to {target_dir}. Use Stop to cancel."
        )
        self._download_worker.start()

    def _on_download_finished(self, result):
        self._set_download_running(False)
        total = int((result or {}).get("total", 0))
        downloaded = int((result or {}).get("downloaded", 0))
        failed = int((result or {}).get("failed", 0))
        stopped = bool((result or {}).get("stopped", False))
        failed_items = list((result or {}).get("failed_items", []))

        if stopped:
            self._set_status(f"Download stopped. Downloaded {downloaded}/{total} video(s).")
        else:
            self._set_status(f"Download finished. Success: {downloaded}, failed: {failed}.")

        if failed_items:
            preview = []
            for item in failed_items[:5]:
                title = str(item.get("title", "")).strip() or "Unknown"
                error = str(item.get("error", "")).strip() or "Download failed"
                preview.append(f"- {title}: {error[:140]}")
            QMessageBox.warning(
                self,
                "Download Summary",
                "\n".join(
                    [f"Downloaded: {downloaded}/{total}", f"Failed: {failed}"] + preview
                ),
            )

        self._download_worker = None

    def _open_video_link_for_row(self, row):
        link = self._video_link_for_row(row)
        if not link:
            QMessageBox.warning(self, "Videos Tool", "No valid video link on this row.")
            return
        webbrowser.open_new_tab(link)

    def _copy_rows_to_clipboard(self, rows, links_only=False):
        if not rows:
            QMessageBox.warning(self, "Videos Tool", "Please select at least one row.")
            return

        lines = []
        if links_only:
            for row in rows:
                link = self._video_link_for_row(row)
                if link:
                    lines.append(link)
        else:
            col_indices = [2, 3, 4, 5, 6, 7]
            headers = [self.videos_table.horizontalHeaderItem(c).text().strip() for c in col_indices]
            lines.append("\t".join(headers))
            for row in rows:
                values = []
                for col in col_indices:
                    item = self.videos_table.item(row, col)
                    values.append(item.text().strip() if item is not None else "")
                lines.append("\t".join(values))

        if not lines:
            QMessageBox.warning(self, "Videos Tool", "No data to copy.")
            return

        QApplication.clipboard().setText("\n".join(lines))
        self._set_status(f"Copied {len(rows)} row(s) to clipboard.")

    def _delete_rows(self, rows):
        if not rows:
            QMessageBox.warning(self, "Videos Tool", "Please select at least one row.")
            return
        if QMessageBox.question(
            self,
            "Delete Rows",
            f"Delete {len(rows)} selected row(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return

        links_to_delete = set()
        for row in sorted(set(rows), reverse=True):
            if 0 <= row < self.videos_table.rowCount():
                link = self._video_link_for_row(row)
                if link:
                    links_to_delete.add(link)
                self.videos_table.removeRow(row)
        if links_to_delete and self._all_rows_cache:
            self._all_rows_cache = [
                r for r in self._all_rows_cache if str(r.get("Video Link", "")).strip() not in links_to_delete
            ]
        self._update_status_labels()
        self._set_status(f"Deleted {len(rows)} row(s).")

    def _on_table_context_menu(self, position):
        clicked_item = self.videos_table.itemAt(position)
        if clicked_item is not None and not self._checked_rows():
            self.videos_table.selectRow(clicked_item.row())

        selected_rows = self._effective_selected_rows()
        clicked_row = clicked_item.row() if clicked_item is not None else -1

        menu = QMenu(self.videos_table)
        menu.setStyleSheet(
            "QMenu { background-color:#2b2b2b; color:#ffffff; border:1px solid #444444; }"
            "QMenu::item { padding:8px 22px; }"
            "QMenu::item:selected { background-color:#e50914; color:#ffffff; }"
        )

        videos_tool_menu = menu.addMenu("Videos tool")
        act_send_comments = videos_tool_menu.addAction("Send SELECTED video to Comments tool")
        act_send_comments.triggered.connect(lambda: self._send_selected_video_to_comments_tool(selected_rows))
        act_send_channel_selected = videos_tool_menu.addAction("Send SELECTED to Channel tool")
        act_send_channel_selected.triggered.connect(lambda: self._send_to_channel_tool(selected_rows, all_rows=False))
        act_send_channel_all = videos_tool_menu.addAction("Send ALL to Channel tool")
        act_send_channel_all.triggered.connect(lambda: self._send_to_channel_tool(selected_rows, all_rows=True))
        videos_tool_menu.addSeparator()
        act_video_details = videos_tool_menu.addAction("View video details")
        act_video_details.triggered.connect(lambda: self._show_video_details_for_row(clicked_row))
        act_video_to_text = videos_tool_menu.addAction("Convert SELECTED video to text")
        act_video_to_text.triggered.connect(lambda: self._convert_selected_video_to_text(selected_rows))
        act_download_video = videos_tool_menu.addAction("Download video")
        act_download_video.triggered.connect(lambda: self._download_selected_videos(selected_rows))
        videos_tool_menu.addSeparator()
        act_analyze_tags = videos_tool_menu.addAction("Analyze video tags")
        act_analyze_tags.triggered.connect(lambda: self._show_coming_soon("Analyze video tags"))
        act_analyze_keywords = videos_tool_menu.addAction("Analyze keywords in video titles")
        act_analyze_keywords.triggered.connect(lambda: self._show_coming_soon("Analyze keywords in video titles"))

        checkbox_menu = menu.addMenu("Checkboxes")
        act_check_selected = checkbox_menu.addAction("Check SELECTED rows")
        act_check_selected.triggered.connect(lambda: self._set_row_check_state(selected_rows, True))
        act_uncheck_selected = checkbox_menu.addAction("Uncheck SELECTED rows")
        act_uncheck_selected.triggered.connect(lambda: self._set_row_check_state(selected_rows, False))
        checkbox_menu.addSeparator()
        act_check_all = checkbox_menu.addAction("Check ALL rows")
        act_check_all.triggered.connect(lambda: self._set_all_check_state(True))
        act_uncheck_all = checkbox_menu.addAction("Uncheck ALL rows")
        act_uncheck_all.triggered.connect(lambda: self._set_all_check_state(False))

        filters_menu = menu.addMenu("Filters")
        act_filters = filters_menu.addAction("Open Filters")
        act_filters.triggered.connect(self.open_filters_dialog)
        act_reset_filters = filters_menu.addAction("Reset Filters")
        act_reset_filters.triggered.connect(self.reset_video_filters)

        copy_menu = menu.addMenu("Copy")
        act_copy_selected = copy_menu.addAction("Copy SELECTED rows")
        act_copy_selected.triggered.connect(lambda: self._copy_rows_to_clipboard(selected_rows, links_only=False))
        act_copy_all = copy_menu.addAction("Copy ALL rows")
        act_copy_all.triggered.connect(
            lambda: self._copy_rows_to_clipboard(list(range(self.videos_table.rowCount())), links_only=False)
        )
        copy_menu.addSeparator()
        act_copy_links_selected = copy_menu.addAction("Copy SELECTED video links")
        act_copy_links_selected.triggered.connect(lambda: self._copy_rows_to_clipboard(selected_rows, links_only=True))
        act_copy_links_all = copy_menu.addAction("Copy ALL video links")
        act_copy_links_all.triggered.connect(
            lambda: self._copy_rows_to_clipboard(list(range(self.videos_table.rowCount())), links_only=True)
        )

        act_search = menu.addAction("Search")
        act_search.triggered.connect(self.open_table_search_dialog)

        preview_menu = menu.addMenu("Preview")
        act_open = preview_menu.addAction("Open Video Link")
        act_open.triggered.connect(lambda: self._open_video_link_for_row(clicked_row))
        act_open.setEnabled(clicked_row >= 0)
        act_preview_details = preview_menu.addAction("Quick preview")
        act_preview_details.triggered.connect(lambda: self._show_coming_soon("Quick preview"))

        menu.addSeparator()
        act_auto_fit = menu.addAction("Auto-fit column widths")
        act_auto_fit.triggered.connect(self.auto_fit_column_widths)
        act_reset_columns = menu.addAction("Reset column widths")
        act_reset_columns.triggered.connect(self.reset_column_widths)

        delete_menu = menu.addMenu("Delete")
        act_delete_selected = delete_menu.addAction("Delete SELECTED rows")
        act_delete_selected.triggered.connect(lambda: self._delete_rows(selected_rows))
        act_delete_all = delete_menu.addAction("Delete ALL rows")
        act_delete_all.triggered.connect(lambda: self._delete_rows(list(range(self.videos_table.rowCount()))))

        menu.exec(self.videos_table.viewport().mapToGlobal(position))

    def _thumbnail_size_px(self):
        return max(40, int(self.slider_image_size.value()))

    def _queue_thumbnail_load(self, row, thumb_url):
        if not thumb_url:
            return

        if thumb_url in self._thumbnail_cache:
            self._apply_thumbnail_to_row(row, thumb_url)
            return

        waiting_rows = self._thumbnail_pending_rows.setdefault(thumb_url, [])
        if row not in waiting_rows:
            waiting_rows.append(row)

        if thumb_url in self._thumbnail_inflight:
            return

        self._thumbnail_inflight.add(thumb_url)
        request = QNetworkRequest(QUrl(thumb_url))
        request.setRawHeader(
            b"User-Agent",
            b"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            b"(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )
        request.setRawHeader(b"Referer", b"https://www.youtube.com/")
        self._thumbnail_manager.get(request)

    def _on_thumbnail_finished(self, reply):
        req_url = reply.request().url().toString()
        try:
            if reply.error():
                self._start_thumbnail_fallback(req_url)
                return
            data = reply.readAll()
            pix = QPixmap()
            if not pix.loadFromData(bytes(data)):
                self._start_thumbnail_fallback(req_url)
                return
            self._thumbnail_cache[req_url] = pix
            rows = self._thumbnail_pending_rows.get(req_url, [])
            for row in rows:
                self._apply_thumbnail_to_row(row, req_url)
            self._cleanup_thumbnail_request(req_url)
        finally:
            reply.deleteLater()

    def _start_thumbnail_fallback(self, req_url):
        req_url = str(req_url or "").strip()
        if not req_url:
            return
        if req_url in self._thumbnail_fallback_workers:
            return
        # Keep this URL inflight while fallback worker runs, to avoid duplicate fetches.
        self._thumbnail_inflight.add(req_url)
        worker = ThumbnailFallbackWorker(req_url)
        worker.finished_signal.connect(self._on_thumbnail_fallback_finished)
        worker.finished.connect(worker.deleteLater)
        self._thumbnail_fallback_workers[req_url] = worker
        worker.start()

    def _on_thumbnail_fallback_finished(self, req_url, image_bytes, error_text):
        req_url = str(req_url or "").strip()
        worker = self._thumbnail_fallback_workers.pop(req_url, None)
        if worker is not None:
            try:
                worker.finished_signal.disconnect(self._on_thumbnail_fallback_finished)
            except Exception:
                pass

        pix = QPixmap()
        if image_bytes and pix.loadFromData(image_bytes):
            self._thumbnail_cache[req_url] = pix
            rows = self._thumbnail_pending_rows.get(req_url, [])
            for row in rows:
                self._apply_thumbnail_to_row(row, req_url)
            self._cleanup_thumbnail_request(req_url)
            return

        # Fallback also failed: restore readable text instead of leaving "..."
        rows = self._thumbnail_pending_rows.get(req_url, [])
        for row in rows:
            if row < 0 or row >= self.videos_table.rowCount():
                continue
            item = self.videos_table.item(row, 1)
            if item is None:
                continue
            item.setData(Qt.ItemDataRole.DecorationRole, None)
            item.setText("N/A")
            item.setForeground(QColor("#666666"))
            if error_text:
                item.setToolTip(error_text[:160])
        self._cleanup_thumbnail_request(req_url)

    def _cleanup_thumbnail_request(self, req_url):
        if req_url in self._thumbnail_inflight:
            self._thumbnail_inflight.remove(req_url)
        if req_url in self._thumbnail_pending_rows:
            del self._thumbnail_pending_rows[req_url]

    def _apply_thumbnail_to_row(self, row, thumb_url):
        if row < 0 or row >= self.videos_table.rowCount():
            return
        pix = self._thumbnail_cache.get(thumb_url)
        if pix is None:
            return
        item = self.videos_table.item(row, 1)
        if item is None:
            return

        thumb = pix.scaled(
            self._thumbnail_size_px(),
            max(22, int(self._thumbnail_size_px() * 9 / 16)),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        item.setData(Qt.ItemDataRole.DecorationRole, thumb)
        item.setText("")
        item.setToolTip(thumb_url)

    def _refresh_visible_thumbnails(self):
        for row in range(self.videos_table.rowCount()):
            item = self.videos_table.item(row, 1)
            if item is None:
                continue
            url = item.toolTip().strip()
            if url and url in self._thumbnail_cache:
                self._apply_thumbnail_to_row(row, url)

    def _show_coming_soon(self, feature_name):
        QMessageBox.information(self, "Videos Tool", f"{feature_name} will be implemented in the next step.")

    def _collect_current_rows_for_analyze(self):
        rows = []
        for row in range(self.videos_table.rowCount()):
            rows.append(
                {
                    "Video ID": self.videos_table.item(row, 2).text().strip() if self.videos_table.item(row, 2) else "",
                    "Video Link": self.videos_table.item(row, 3).text().strip() if self.videos_table.item(row, 3) else "",
                    "Source": self.videos_table.item(row, 4).text().strip() if self.videos_table.item(row, 4) else "",
                    "Search Phrase": self.videos_table.item(row, 5).text().strip() if self.videos_table.item(row, 5) else "",
                    "Title": self.videos_table.item(row, 6).text().strip() if self.videos_table.item(row, 6) else "",
                    "Description": self.videos_table.item(row, 7).text().strip() if self.videos_table.item(row, 7) else "",
                }
            )
        return rows

    def _build_analyze_metrics(self, rows):
        total = len(rows)
        if total == 0:
            return {
                "total_videos": 0,
                "avg_title_len": "0 words",
                "missing_desc_ratio": "0.0%",
                "source_ratio_text": "-",
                "top_terms_text": "-",
            }

        title_words = []
        missing_desc = 0
        source_counter = Counter()
        terms = Counter()
        stop_words = {
            "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with", "is", "are",
            "video", "youtube", "official", "vs", "part", "episode",
        }

        for row in rows:
            title = str(row.get("Title", "")).strip()
            desc = str(row.get("Description", "")).strip()
            source = str(row.get("Source", "")).strip() or "Unknown"
            source_counter[source] += 1

            if not desc:
                missing_desc += 1
            if title:
                split_words = [w for w in re.findall(r"[A-Za-z0-9À-ỹ]+", title.lower()) if w]
                title_words.append(len(split_words))
                for w in split_words:
                    if len(w) >= 3 and w not in stop_words:
                        terms[w] += 1

        avg_words = (sum(title_words) / len(title_words)) if title_words else 0.0
        missing_ratio = (missing_desc / total) * 100.0
        source_ratio_parts = []
        for src, cnt in source_counter.most_common():
            pct = (cnt / total) * 100.0
            source_ratio_parts.append(f"{src}: {cnt} ({pct:.1f}%)")

        top_terms = terms.most_common(10)
        top_terms_text = ", ".join([f"{k} ({v})" for k, v in top_terms]) if top_terms else "-"

        return {
            "total_videos": total,
            "avg_title_len": f"{avg_words:.1f} words",
            "missing_desc_ratio": f"{missing_ratio:.1f}%",
            "source_ratio_text": "\n".join(source_ratio_parts) if source_ratio_parts else "-",
            "top_terms_text": top_terms_text,
        }

    def open_analyze_dialog(self):
        rows = self._collect_current_rows_for_analyze()
        if not rows:
            QMessageBox.warning(self, "Videos Analyze", "No data to analyze. Please load videos first.")
            return
        metrics = self._build_analyze_metrics(rows)
        dlg = VideosAnalyzeDialog(self, metrics=metrics)
        dlg.exec()

    def receive_keywords_for_video_search(self, keywords, source_tool=""):
        cleaned = []
        seen = set()
        for kw in keywords or []:
            text = str(kw).strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(text)

        if not cleaned:
            return False

        self.switch_mode("search")
        self.input_search_phrase.setText(cleaned[0])
        self.input_search_phrase.setFocus()

        src = source_tool.strip() if source_tool else "another tool"
        if len(cleaned) == 1:
            self._set_status(f"Received 1 keyword from {src}. Ready to search.")
        else:
            self._set_status(
                f"Received {len(cleaned)} keywords from {src}. Using first keyword for now."
            )
        return True
