from PyQt6.QtCore import Qt, QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPixmap, QTextOption
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QSplitter,
)
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
import os
import webbrowser
import re
from collections import Counter
from html import unescape
from urllib.parse import parse_qs, urlparse, urljoin

from core.videos_fetcher import (
    ImportedLinksMetadataWorker,
    TrendingVideosWorker,
    VideoDownloadWorker,
    VideoMetadataEnrichWorker,
    VideoSearchWorker,
    fetch_video_page_details,
)
from ui.video_title_generator_dialog import VideoTitleGeneratorDialog
from utils.constants import REQUESTS_INSTALLED, TABLE_SCROLLBAR_STYLE

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


VIDEO_TABLE_COLUMNS = [
    "",
    "Image",
    "Video ID",
    "Video Link",
    "Source",
    "Search Phrase",
    "Title",
    "Description",
    "Rating",
    "Comments",
    "View Count",
    "Length Seconds",
    "Published",
    "Published Age (Days)",
    "Avg. Views per Day",
    "Category",
    "Subtitles",
    "Channel",
    "Channel Link",
    "Subscribers",
    "Tags",
]

VIDEO_COLUMN_INDEX = {name: idx for idx, name in enumerate(VIDEO_TABLE_COLUMNS)}
VIDEO_TEXT_COLUMNS = [name for name in VIDEO_TABLE_COLUMNS[2:]]
VIDEO_DEFAULT_COLUMN_WIDTHS = {
    0: 26,
    1: 94,
    2: 112,
    3: 240,
    4: 90,
    5: 130,
    6: 300,
    7: 240,
    8: 82,
    9: 100,
    10: 118,
    11: 110,
    12: 120,
    13: 130,
    14: 138,
    15: 120,
    16: 86,
    17: 180,
    18: 210,
    19: 110,
    20: 260,
}
VIDEO_NUMERIC_FILTERABLE_COLUMNS = {
    "Rating",
    "Comments",
    "View Count",
    "Length Seconds",
    "Published Age (Days)",
    "Avg. Views per Day",
    "Subscribers",
}


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


class VideoNumericFilterDialog(QDialog):
    def __init__(self, parent=None, column_name="", current_expression=""):
        super().__init__(parent)
        self.column_name = str(column_name or "").strip()
        self._clear_requested = False
        self.setWindowTitle(f"Filter {self.column_name}")
        self.setModal(True)
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        title = QLabel(f"Numeric filter for: {self.column_name}")
        title.setStyleSheet("QLabel { color:#ffffff; font-size:14px; font-weight:700; }")
        root.addWidget(title)

        hint = QLabel("Examples: `>500000`, `>=10000`, `<60`, `=0`, `!=100`")
        hint.setStyleSheet("QLabel { color:#aab3c5; font-size:12px; }")
        root.addWidget(hint)

        self.input_expression = QLineEdit()
        self.input_expression.setPlaceholderText("Enter numeric condition...")
        self.input_expression.setText(str(current_expression or "").strip())
        root.addWidget(self.input_expression)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_clear = QPushButton("Clear Filter")
        self.btn_clear.clicked.connect(self._clear_filter)
        btn_row.addWidget(self.btn_clear)
        btn_row.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        btn_row.addWidget(buttons)
        root.addLayout(btn_row)

        self.setStyleSheet(
            "QDialog { background-color:#181b22; color:#f3f4f6; }"
            "QLabel { color:#f3f4f6; }"
            "QLineEdit { background:#ffffff; color:#111111; border:1px solid #c7c7c7; border-radius:4px; padding:6px 8px; }"
            "QPushButton { background-color:#2d3342; color:#ffffff; border:none; border-radius:4px; padding:6px 12px; }"
            "QPushButton:hover { background-color:#3c4356; }"
            "QDialogButtonBox QPushButton { background-color:#e50914; color:#ffffff; border:none; border-radius:4px; padding:6px 14px; font-weight:700; }"
            "QDialogButtonBox QPushButton:hover { background-color:#ff1a25; }"
        )

    def _clear_filter(self):
        self._clear_requested = True
        self.accept()

    def selected_expression(self):
        if self._clear_requested:
            return None
        return self.input_expression.text().strip()


class VideoTagsAnalyzeWorker(QThread):
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal(dict)

    def __init__(self, rows=None):
        super().__init__()
        self.rows = [dict(row) for row in (rows or []) if isinstance(row, dict)]
        self._running = True

    def stop(self):
        self._running = False

    @staticmethod
    def _parse_number(raw_value):
        text = str(raw_value or "").strip()
        if not text:
            return 0.0
        match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", "").replace("+", ""))
        if not match:
            return 0.0
        try:
            return float(match.group(0))
        except Exception:
            return 0.0

    @staticmethod
    def _split_tags(tag_text):
        parts = re.split(r"[,;\n\r]+", str(tag_text or ""))
        seen = set()
        ordered = []
        for part in parts:
            tag = re.sub(r"\s+", " ", str(part).strip()).strip("# ").strip()
            if not tag:
                continue
            key = tag.lower()
            if key in seen:
                continue
            seen.add(key)
            ordered.append((key, tag))
        return ordered

    def run(self):
        total_videos = len(self.rows)
        if total_videos == 0:
            self.finished_signal.emit({"total_videos": 0, "total_channels": 0, "total_occurrences": 0, "rows": []})
            return

        unique_channels = set()
        aggregates = {}
        total_occurrences = 0

        for index, row in enumerate(self.rows, start=1):
            if not self._running:
                break

            channel_name = str(row.get("Channel", "")).strip()
            if channel_name:
                unique_channels.add(channel_name.lower())

            view_count = self._parse_number(row.get("View Count", ""))
            likes_count = self._parse_number(row.get("Likes", ""))
            tags = self._split_tags(row.get("Tags", ""))

            for tag_key, tag_label in tags:
                entry = aggregates.setdefault(
                    tag_key,
                    {"tag": tag_label, "occurrences": 0, "view_sum": 0.0, "likes_sum": 0.0},
                )
                entry["occurrences"] += 1
                entry["view_sum"] += view_count
                entry["likes_sum"] += likes_count
                total_occurrences += 1

            self.progress_signal.emit(index, total_videos)

        rows = []
        for entry in aggregates.values():
            occurrences = int(entry["occurrences"])
            percentage = (occurrences / total_videos) * 100.0 if total_videos else 0.0
            avg_views = entry["view_sum"] / max(1, occurrences)
            avg_likes = entry["likes_sum"] / max(1, occurrences)
            rows.append(
                {
                    "tag": entry["tag"],
                    "occurrences": occurrences,
                    "percentage": percentage,
                    "avg_views": avg_views,
                    "avg_likes": avg_likes,
                }
            )

        rows.sort(key=lambda item: (-item["occurrences"], item["tag"].lower()))
        self.finished_signal.emit(
            {
                "total_videos": total_videos,
                "total_channels": len(unique_channels),
                "total_occurrences": total_occurrences,
                "rows": rows,
            }
        )


class AnalyzeVideoTagsDialog(QDialog):
    TABLE_COLUMNS = [
        "",
        "Tags",
        "Occurrences in Listings",
        "Percentage in Listings",
        "Avg. Views per Tag",
        "Avg. Likes per Tag",
    ]
    NUMERIC_COLUMNS = {
        "Occurrences in Listings",
        "Percentage in Listings",
        "Avg. Views per Tag",
        "Avg. Likes per Tag",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._all_tag_rows = []
        self._numeric_filters = {}
        self.setWindowTitle("Analyze Video Tags")
        self.setModal(True)
        self.resize(980, 640)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.card_total_videos = self._make_metric_card("Total\nVideos:", "0")
        self.card_total_channels = self._make_metric_card("Total\nChannels:", "0")
        top_row.addWidget(self.card_total_videos)
        top_row.addWidget(self.card_total_channels)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(18)
        self.progress.setStyleSheet(
            "QProgressBar { background:#e8edf5; border:1px solid #d0d7e2; border-radius:4px; }"
            "QProgressBar::chunk { background:#4a90e2; border-radius:4px; }"
        )
        top_row.addWidget(self.progress, stretch=1)
        root.addLayout(top_row)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.TABLE_COLUMNS))
        self.table.setHorizontalHeaderLabels(self.TABLE_COLUMNS)
        self.table.setRowCount(0)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setStyleSheet(
            "QTableWidget { background:#ffffff; color:#111111; gridline-color:#d8d8d8; border:1px solid #cfcfcf; }"
            "QHeaderView::section { background:#f0f0f0; color:#111111; border:1px solid #d0d0d0; font-weight:700; padding:4px; }"
            + TABLE_SCROLLBAR_STYLE
        )
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.sectionClicked.connect(self._on_header_clicked)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 26)
        self.table.setColumnWidth(1, 210)
        self.table.setColumnWidth(2, 170)
        self.table.setColumnWidth(3, 170)
        self.table.setColumnWidth(4, 170)
        self.table.setColumnWidth(5, 160)
        root.addWidget(self.table, stretch=1)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        self.lbl_total = QLabel("Total: 0")
        self.lbl_total.setStyleSheet("QLabel { color:#111111; font-size:12px; }")
        bottom_row.addWidget(self.lbl_total)
        bottom_row.addStretch()

        self.btn_file = QPushButton("File")
        self.btn_clear_filters = QPushButton("Clear Filters")
        self.btn_clear = QPushButton("Clear")
        self.btn_close = QPushButton("Close")
        for btn in (self.btn_file, self.btn_clear_filters, self.btn_clear, self.btn_close):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background-color:#e50914; color:#ffffff; border:none; border-radius:4px; padding:6px 14px; font-weight:700; }"
                "QPushButton:hover { background-color:#ff1a25; }"
            )
        self.btn_close.clicked.connect(self.accept)
        bottom_row.addWidget(self.btn_file)
        bottom_row.addWidget(self.btn_clear_filters)
        bottom_row.addWidget(self.btn_clear)
        bottom_row.addWidget(self.btn_close)
        root.addLayout(bottom_row)

        self.setStyleSheet("QDialog { background:#ffffff; }")
        self._refresh_header_filter_tooltips()

    def _make_metric_card(self, title, value):
        frame = QFrame()
        frame.setFixedWidth(150)
        frame.setStyleSheet("QFrame { background:#e24a22; border:1px solid #c73a16; }")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("QLabel { color:#ffffff; font-size:14px; font-weight:700; }")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(lbl_title, stretch=1)

        lbl_value = QLabel(value)
        lbl_value.setStyleSheet("QLabel { color:#ffffff; font-size:24px; font-weight:700; }")
        lbl_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(lbl_value)

        frame._value_label = lbl_value
        return frame

    def set_metric_values(self, total_videos=0, total_channels=0):
        self.card_total_videos._value_label.setText(str(int(total_videos)))
        self.card_total_channels._value_label.setText(str(int(total_channels)))

    def set_progress(self, current, total):
        total_value = max(1, int(total or 0))
        current_value = max(0, int(current or 0))
        self.progress.setValue(int((current_value / total_value) * 100))

    def populate_rows(self, payload):
        data = dict(payload or {})
        rows = list(data.get("rows", []))
        self._all_tag_rows = rows
        self.set_metric_values(data.get("total_videos", 0), data.get("total_channels", 0))
        self.progress.setValue(100 if rows else 0)
        self._render_rows(self._filtered_rows(rows))
        self.lbl_total.setText(f"Total: {int(data.get('total_occurrences', 0)):,}")

    def _render_rows(self, rows):
        self.table.setRowCount(0)
        for row_data in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)

            checkbox_item = QTableWidgetItem("")
            checkbox_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            checkbox_item.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, checkbox_item)

            values = [
                str(row_data.get("tag", "")),
                f"{int(row_data.get('occurrences', 0)):,}",
                f"{float(row_data.get('percentage', 0.0)):.1f}",
                f"{float(row_data.get('avg_views', 0.0)):,.1f}",
                f"{float(row_data.get('avg_likes', 0.0)):,.1f}",
            ]
            for offset, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                if offset >= 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, offset, item)

    def clear_results(self):
        self.set_metric_values(0, 0)
        self.progress.setValue(0)
        self.table.setRowCount(0)
        self._all_tag_rows = []
        self._numeric_filters = {}
        self._refresh_header_filter_tooltips()
        self.lbl_total.setText("Total: 0")

    def reset_filters(self):
        self._numeric_filters = {}
        self._refresh_header_filter_tooltips()
        self._render_rows(self._all_tag_rows)

    @staticmethod
    def _parse_number(raw_value):
        text = str(raw_value or "").strip()
        if not text:
            return None
        match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", "").replace("+", ""))
        if not match:
            return None
        try:
            return float(match.group(0))
        except Exception:
            return None

    @staticmethod
    def _evaluate_expression(value, expression):
        expr = str(expression or "").strip()
        if not expr:
            return True
        match = re.fullmatch(r"(>=|<=|!=|==|=|>|<)\s*(-?\d+(?:\.\d+)?)", expr)
        if not match:
            return None
        operator = match.group(1)
        target = float(match.group(2))
        if operator == ">":
            return value > target
        if operator == "<":
            return value < target
        if operator == ">=":
            return value >= target
        if operator == "<=":
            return value <= target
        if operator in {"=", "=="}:
            return value == target
        if operator == "!=":
            return value != target
        return None

    def _filtered_rows(self, rows):
        results = []
        for row in rows:
            matched = True
            for column_name, expression in self._numeric_filters.items():
                if column_name == "Occurrences in Listings":
                    value = self._parse_number(row.get("occurrences", 0))
                elif column_name == "Percentage in Listings":
                    value = self._parse_number(row.get("percentage", 0.0))
                elif column_name == "Avg. Views per Tag":
                    value = self._parse_number(row.get("avg_views", 0.0))
                elif column_name == "Avg. Likes per Tag":
                    value = self._parse_number(row.get("avg_likes", 0.0))
                else:
                    value = None
                if value is None or self._evaluate_expression(value, expression) is not True:
                    matched = False
                    break
            if matched:
                results.append(row)
        return results

    def _refresh_header_filter_tooltips(self):
        for index, column_name in enumerate(self.TABLE_COLUMNS):
            item = self.table.horizontalHeaderItem(index)
            if item is None:
                continue
            if column_name in self.NUMERIC_COLUMNS:
                expr = str(self._numeric_filters.get(column_name, "")).strip()
                item.setToolTip(f"Active filter: {expr}" if expr else "Click to filter this numeric column")
            else:
                item.setToolTip("")

    def _on_header_clicked(self, section):
        if section < 0 or section >= len(self.TABLE_COLUMNS):
            return
        column_name = self.TABLE_COLUMNS[section]
        if column_name not in self.NUMERIC_COLUMNS:
            return

        dlg = VideoNumericFilterDialog(
            self,
            column_name=column_name,
            current_expression=self._numeric_filters.get(column_name, ""),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        expression = dlg.selected_expression()
        if expression is None or not str(expression).strip():
            self._numeric_filters.pop(column_name, None)
        else:
            if self._evaluate_expression(1.0, expression) is None:
                QMessageBox.warning(
                    self,
                    "Analyze Video Tags",
                    "Numeric filter format is invalid. Use examples like >500000, >=1000, <60, =0.",
                )
                return
            self._numeric_filters[column_name] = str(expression).strip()

        self._refresh_header_filter_tooltips()
        self._render_rows(self._filtered_rows(self._all_tag_rows))

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(1000)
        super().closeEvent(event)


DEFAULT_STOP_WORDS = [
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "could", "did", "do", "does",
    "doing", "down", "during", "each", "few", "for", "from", "further", "had", "has",
    "have", "having", "he", "her", "here", "hers", "herself", "him", "himself", "his",
    "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just",
    "me", "more", "most", "my", "myself", "no", "nor", "not", "now", "of",
    "off", "on", "once", "only", "or", "other", "our", "ours", "ourselves", "out",
    "over", "own", "same", "she", "should", "so", "some", "such", "than", "that",
    "the", "their", "theirs", "them", "themselves", "then", "there", "these", "they", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "we",
    "were", "what", "when", "where", "which", "while", "who", "whom", "why", "with",
    "would", "you", "your", "yours", "yourself", "yourselves",
]


class StopWordsDialog(QDialog):
    def __init__(self, parent=None, stop_words=None):
        super().__init__(parent)
        self.setWindowTitle("Stop Words")
        self.setModal(True)
        self.resize(520, 520)

        words = [str(word).strip() for word in (stop_words or DEFAULT_STOP_WORDS) if str(word).strip()]

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        lbl_help = QLabel(
            "These are words or word phrases you do not want to\n"
            "appear in your word analysis data. Enter one word or\n"
            "word phrase per line."
        )
        lbl_help.setStyleSheet("QLabel { color:#111111; font-size:13px; }")
        root.addWidget(lbl_help)

        self.text_words = QTextEdit()
        self.text_words.setPlainText("\n".join(words))
        self.text_words.setStyleSheet(
            "QTextEdit { background:#ffffff; color:#111111; border:1px solid #cfcfcf; border-radius:2px; padding:6px; }"
        )
        root.addWidget(self.text_words, stretch=1)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        self.lbl_total = QLabel(f"Total: {len(words)}")
        self.lbl_total.setStyleSheet("QLabel { color:#111111; font-size:12px; }")
        bottom_row.addWidget(self.lbl_total)
        bottom_row.addStretch()

        self.btn_file = QPushButton("File")
        self.btn_ok = QPushButton("Ok")
        self.btn_cancel = QPushButton("Cancel")
        for btn in (self.btn_file, self.btn_ok, self.btn_cancel):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background-color:#e50914; color:#ffffff; border:none; border-radius:4px; padding:6px 14px; font-weight:700; }"
                "QPushButton:hover { background-color:#ff1a25; }"
            )

        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        self.text_words.textChanged.connect(self._refresh_total)

        bottom_row.addWidget(self.btn_file)
        bottom_row.addWidget(self.btn_ok)
        bottom_row.addWidget(self.btn_cancel)
        root.addLayout(bottom_row)

        self.setStyleSheet("QDialog { background:#ffffff; }")

    def _refresh_total(self):
        count = len([line for line in self.text_words.toPlainText().splitlines() if line.strip()])
        self.lbl_total.setText(f"Total: {count}")

    def stop_words(self):
        ordered = []
        seen = set()
        for raw_line in self.text_words.toPlainText().splitlines():
            text = re.sub(r"\s+", " ", str(raw_line).strip()).strip().lower()
            if not text or text in seen:
                continue
            seen.add(text)
            ordered.append(text)
        return ordered


class VideoTitleKeywordsAnalyzeWorker(QThread):
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal(dict)

    def __init__(self, rows=None, word_count=1, use_stop_words=True, stop_words=None):
        super().__init__()
        self.rows = [dict(row) for row in (rows or []) if isinstance(row, dict)]
        self.word_count = max(1, int(word_count or 1))
        self.use_stop_words = bool(use_stop_words)
        self.stop_words = [str(word).strip().lower() for word in (stop_words or []) if str(word).strip()]
        self._running = True

    def stop(self):
        self._running = False

    @staticmethod
    def _parse_number(raw_value):
        text = str(raw_value or "").strip()
        if not text:
            return 0.0
        lowered = text.lower()
        if lowered in {"not-given", "n/a", "-", "none"}:
            return 0.0
        cleaned = text.replace(",", "").replace("+", "").strip()
        match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
        if not match:
            return 0.0
        try:
            return float(match.group(0))
        except Exception:
            return 0.0

    @staticmethod
    def _tokenize_title(title_text):
        return [
            token.lower()
            for token in re.findall(r"[^\W_]+", str(title_text or ""), flags=re.UNICODE)
            if token and not token.isdigit()
        ]

    @staticmethod
    def _normalize_phrase(text):
        return re.sub(r"\s+", " ", str(text or "").strip()).strip().lower()

    def _is_blocked_phrase(self, tokens, stop_single, stop_phrases):
        phrase = " ".join(tokens).strip().lower()
        if not phrase:
            return True
        if phrase in stop_phrases:
            return True
        return any(token in stop_single for token in tokens)

    def run(self):
        total_titles = len(self.rows)
        if total_titles <= 0:
            self.finished_signal.emit({"total_titles": 0, "rows": []})
            return

        stop_single = {word for word in self.stop_words if " " not in word}
        stop_phrases = {word for word in self.stop_words if " " in word}
        aggregates = {}

        for index, row in enumerate(self.rows, start=1):
            if not self._running:
                break

            title_text = str(row.get("Title", "")).strip()
            if not title_text:
                self.progress_signal.emit(index, total_titles)
                continue

            tokens = self._tokenize_title(title_text)
            if len(tokens) < self.word_count:
                self.progress_signal.emit(index, total_titles)
                continue

            view_count = self._parse_number(row.get("View Count", ""))
            likes_count = self._parse_number(row.get("Likes", ""))
            seen_in_title = set()

            for start in range(0, len(tokens) - self.word_count + 1):
                phrase_tokens = tokens[start:start + self.word_count]
                phrase = " ".join(phrase_tokens).strip()
                if not phrase:
                    continue
                if self.use_stop_words and self._is_blocked_phrase(phrase_tokens, stop_single, stop_phrases):
                    continue
                if phrase in seen_in_title:
                    continue
                seen_in_title.add(phrase)

                entry = aggregates.setdefault(
                    phrase,
                    {
                        "phrase": phrase,
                        "occurrences": 0,
                        "view_sum": 0.0,
                        "likes_sum": 0.0,
                        "word_count": self.word_count,
                    },
                )
                entry["occurrences"] += 1
                entry["view_sum"] += view_count
                entry["likes_sum"] += likes_count

            self.progress_signal.emit(index, total_titles)

        rows = []
        for entry in aggregates.values():
            occurrences = int(entry["occurrences"])
            rows.append(
                {
                    "phrase": entry["phrase"],
                    "occurrences": occurrences,
                    "percentage": (occurrences / total_titles) * 100.0 if total_titles else 0.0,
                    "avg_views": entry["view_sum"] / max(1, occurrences),
                    "avg_likes": entry["likes_sum"] / max(1, occurrences),
                    "word_count": int(entry["word_count"]),
                }
            )

        rows.sort(key=lambda item: (-item["occurrences"], item["phrase"]))
        self.finished_signal.emit({"total_titles": total_titles, "rows": rows})


class AnalyzeVideoTitleKeywordsDialog(QDialog):
    TABLE_COLUMNS = [
        "",
        "Word Combination",
        "Occurrences in Titles",
        "Percentage in Titles",
        "Avg. Views",
        "Avg. Likes",
        "Number of Words",
    ]
    NUMERIC_COLUMNS = {
        "Occurrences in Titles",
        "Percentage in Titles",
        "Avg. Views",
        "Avg. Likes",
        "Number of Words",
    }

    def __init__(self, parent=None, stop_words=None):
        super().__init__(parent)
        self._worker = None
        self._all_word_rows = []
        self._numeric_filters = {}
        self._stop_words = [str(word).strip().lower() for word in (stop_words or DEFAULT_STOP_WORDS) if str(word).strip()]
        self.setWindowTitle("Analyze Titles")
        self.setModal(True)
        self.resize(1120, 650)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        lbl_words = QLabel("Number of words:")
        lbl_words.setStyleSheet("QLabel { color:#111111; font-size:13px; }")
        top_row.addWidget(lbl_words)

        self.combo_word_count = QComboBox()
        self.combo_word_count.addItems([str(i) for i in range(1, 7)])
        self.combo_word_count.setCurrentText("1")
        self.combo_word_count.setFixedWidth(64)
        self.combo_word_count.setStyleSheet(
            "QComboBox { background:#ffffff; color:#111111; border:1px solid #c7c7c7; border-radius:3px; padding:4px 8px; }"
            "QComboBox::drop-down { border:none; width:18px; }"
        )
        top_row.addWidget(self.combo_word_count)

        self.chk_use_stop_words = QCheckBox("Use stop words")
        self.chk_use_stop_words.setChecked(True)
        self.chk_use_stop_words.setStyleSheet("QCheckBox { color:#111111; font-size:13px; }")
        top_row.addWidget(self.chk_use_stop_words)

        self.btn_stop_words = QPushButton("Stop Words")
        self.btn_stop_words.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop_words.setStyleSheet(
            "QPushButton { background-color:#e50914; color:#ffffff; border:none; border-radius:4px; padding:6px 12px; font-weight:700; }"
            "QPushButton:hover { background-color:#ff1a25; }"
        )
        top_row.addWidget(self.btn_stop_words)

        top_row.addStretch()

        self.btn_generate = QPushButton("Generate Word Stats")
        self.btn_generate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_generate.setStyleSheet(
            "QPushButton { background-color:#e50914; color:#ffffff; border:none; border-radius:4px; padding:6px 14px; font-weight:700; }"
            "QPushButton:hover { background-color:#ff1a25; }"
        )
        top_row.addWidget(self.btn_generate)
        root.addLayout(top_row)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.TABLE_COLUMNS))
        self.table.setHorizontalHeaderLabels(self.TABLE_COLUMNS)
        self.table.setRowCount(0)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setStyleSheet(
            "QTableWidget { background:#ffffff; color:#111111; gridline-color:#d8d8d8; border:1px solid #cfcfcf; }"
            "QHeaderView::section { background:#f0f0f0; color:#111111; border:1px solid #d0d0d0; font-weight:700; padding:4px; }"
            + TABLE_SCROLLBAR_STYLE
        )
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.sectionClicked.connect(self._on_header_clicked)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        for column in range(1, len(self.TABLE_COLUMNS)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 26)
        self.table.setColumnWidth(1, 230)
        self.table.setColumnWidth(2, 170)
        self.table.setColumnWidth(3, 165)
        self.table.setColumnWidth(4, 150)
        self.table.setColumnWidth(5, 150)
        self.table.setColumnWidth(6, 130)
        root.addWidget(self.table, stretch=1)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        self.lbl_total = QLabel("Total: 0")
        self.lbl_total.setStyleSheet("QLabel { color:#111111; font-size:12px; }")
        bottom_row.addWidget(self.lbl_total)
        bottom_row.addStretch()

        self.btn_file = QPushButton("File")
        self.btn_clear_filters = QPushButton("Clear Filters")
        self.btn_clear = QPushButton("Clear")
        self.btn_close = QPushButton("Close")
        for btn in (self.btn_file, self.btn_clear_filters, self.btn_clear, self.btn_close):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background-color:#e50914; color:#ffffff; border:none; border-radius:4px; padding:6px 14px; font-weight:700; }"
                "QPushButton:hover { background-color:#ff1a25; }"
            )
        self.btn_close.clicked.connect(self.accept)
        bottom_row.addWidget(self.btn_file)
        bottom_row.addWidget(self.btn_clear_filters)
        bottom_row.addWidget(self.btn_clear)
        bottom_row.addWidget(self.btn_close)
        root.addLayout(bottom_row)

        self.setStyleSheet("QDialog { background:#ffffff; }")
        self._refresh_header_filter_tooltips()

    def stop_words(self):
        return list(self._stop_words)

    def set_stop_words(self, stop_words):
        self._stop_words = [str(word).strip().lower() for word in (stop_words or []) if str(word).strip()]

    def selected_word_count(self):
        try:
            return max(1, int(self.combo_word_count.currentText().strip()))
        except Exception:
            return 1

    def set_progress(self, current, total):
        total_value = max(1, int(total or 0))
        current_value = max(0, int(current or 0))
        self.lbl_total.setText(f"Processing: {current_value}/{total_value}")

    def populate_rows(self, payload):
        data = dict(payload or {})
        rows = list(data.get("rows", []))
        self._all_word_rows = rows
        self._render_rows(self._filtered_rows(rows))
        self.lbl_total.setText(f"Total: {len(rows):,}")
        self.btn_generate.setText("Generate Word Stats")
        self.btn_generate.setEnabled(True)

    def _render_rows(self, rows):
        self.table.setRowCount(0)
        for row_data in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)

            checkbox_item = QTableWidgetItem("")
            checkbox_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            checkbox_item.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, checkbox_item)

            values = [
                str(row_data.get("phrase", "")),
                f"{int(row_data.get('occurrences', 0)):,}",
                f"{float(row_data.get('percentage', 0.0)):.1f}",
                f"{float(row_data.get('avg_views', 0.0)):,.1f}",
                f"{float(row_data.get('avg_likes', 0.0)):,.1f}",
                f"{int(row_data.get('word_count', 0))}",
            ]
            for offset, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                if offset >= 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, offset, item)

    def clear_results(self):
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(1000)
        self._worker = None
        self.table.setRowCount(0)
        self._all_word_rows = []
        self._numeric_filters = {}
        self._refresh_header_filter_tooltips()
        self.lbl_total.setText("Total: 0")
        self.btn_generate.setText("Generate Word Stats")
        self.btn_generate.setEnabled(True)

    def reset_filters(self):
        self._numeric_filters = {}
        self._refresh_header_filter_tooltips()
        self._render_rows(self._all_word_rows)
        self.lbl_total.setText(f"Total: {len(self._filtered_rows(self._all_word_rows)):,}")

    @staticmethod
    def _parse_number(raw_value):
        text = str(raw_value or "").strip()
        if not text:
            return None
        match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", "").replace("+", ""))
        if not match:
            return None
        try:
            return float(match.group(0))
        except Exception:
            return None

    @staticmethod
    def _evaluate_expression(value, expression):
        expr = str(expression or "").strip()
        if not expr:
            return True
        match = re.fullmatch(r"(>=|<=|!=|==|=|>|<)\s*(-?\d+(?:\.\d+)?)", expr)
        if not match:
            return None
        operator = match.group(1)
        target = float(match.group(2))
        if operator == ">":
            return value > target
        if operator == "<":
            return value < target
        if operator == ">=":
            return value >= target
        if operator == "<=":
            return value <= target
        if operator in {"=", "=="}:
            return value == target
        if operator == "!=":
            return value != target
        return None

    def _filtered_rows(self, rows):
        results = []
        for row in rows:
            matched = True
            for column_name, expression in self._numeric_filters.items():
                if column_name == "Occurrences in Titles":
                    value = self._parse_number(row.get("occurrences", 0))
                elif column_name == "Percentage in Titles":
                    value = self._parse_number(row.get("percentage", 0.0))
                elif column_name == "Avg. Views":
                    value = self._parse_number(row.get("avg_views", 0.0))
                elif column_name == "Avg. Likes":
                    value = self._parse_number(row.get("avg_likes", 0.0))
                elif column_name == "Number of Words":
                    value = self._parse_number(row.get("word_count", 0))
                else:
                    value = None
                if value is None or self._evaluate_expression(value, expression) is not True:
                    matched = False
                    break
            if matched:
                results.append(row)
        return results

    def _refresh_header_filter_tooltips(self):
        for index, column_name in enumerate(self.TABLE_COLUMNS):
            item = self.table.horizontalHeaderItem(index)
            if item is None:
                continue
            if column_name in self.NUMERIC_COLUMNS:
                expr = str(self._numeric_filters.get(column_name, "")).strip()
                item.setToolTip(f"Active filter: {expr}" if expr else "Click to filter this numeric column")
            else:
                item.setToolTip("")

    def _on_header_clicked(self, section):
        if section < 0 or section >= len(self.TABLE_COLUMNS):
            return
        column_name = self.TABLE_COLUMNS[section]
        if column_name not in self.NUMERIC_COLUMNS:
            return

        dlg = VideoNumericFilterDialog(
            self,
            column_name=column_name,
            current_expression=self._numeric_filters.get(column_name, ""),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        expression = dlg.selected_expression()
        if expression is None or not str(expression).strip():
            self._numeric_filters.pop(column_name, None)
        else:
            if self._evaluate_expression(1.0, expression) is None:
                QMessageBox.warning(
                    self,
                    "Analyze Titles",
                    "Numeric filter format is invalid. Use examples like >500000, >=1000, <60, =0.",
                )
                return
            self._numeric_filters[column_name] = str(expression).strip()

        self._refresh_header_filter_tooltips()
        filtered_rows = self._filtered_rows(self._all_word_rows)
        self._render_rows(filtered_rows)
        self.lbl_total.setText(f"Total: {len(filtered_rows):,}")

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(1000)
        super().closeEvent(event)


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


class ConfirmAddLinksDialog(QDialog):
    def __init__(self, parent=None, link_count=0):
        super().__init__(parent)
        self.setWindowTitle("Confirm")
        self.setModal(True)
        self.setFixedSize(420, 150)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        message = QLabel(
            f"{int(link_count)} links have been added. Click 'Yes' to CLOSE the browser,\n"
            "or click 'No' to continue browsing."
        )
        message.setWordWrap(True)
        message.setStyleSheet("QLabel { color:#111111; font-size:13px; }")
        root.addWidget(message)

        row = QHBoxLayout()
        row.addStretch()
        self.btn_yes = QPushButton("Yes")
        self.btn_no = QPushButton("No")
        for btn in (self.btn_yes, self.btn_no):
            btn.setFixedWidth(84)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background-color:#f1f3f6; color:#111111; border:1px solid #b7bdc9; border-radius:3px; padding:4px 10px; }"
                "QPushButton:hover { background-color:#e4e8ef; }"
            )
        self.btn_yes.clicked.connect(self.accept)
        self.btn_no.clicked.connect(self.reject)
        row.addWidget(self.btn_yes)
        row.addWidget(self.btn_no)
        root.addLayout(row)

        self.setStyleSheet("QDialog { background:#ffffff; }")


class BookmarkDialog(QDialog):
    def __init__(self, parent=None, initial_label="", initial_link="", folder_options=None, initial_folder=""):
        super().__init__(parent)
        self.setWindowTitle("Bookmark")
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setMinimumWidth(420)
        self.setMaximumWidth(480)
        self.setMinimumHeight(150)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.input_label = QLineEdit(str(initial_label or "").strip())
        self.input_link = QLineEdit(str(initial_link or "").strip())
        self.combo_folder = QComboBox()
        self.combo_folder.addItem("")
        for folder_name in folder_options or []:
            text = str(folder_name or "").strip()
            if text and self.combo_folder.findText(text) < 0:
                self.combo_folder.addItem(text)
        if initial_folder and self.combo_folder.findText(initial_folder) >= 0:
            self.combo_folder.setCurrentText(initial_folder)

        field_style = (
            "QLineEdit, QComboBox { background:#ffffff; color:#111111; border:1px solid #bfc7d5; "
            "border-radius:3px; padding:5px 8px; }"
            "QComboBox::drop-down { border:none; width:18px; }"
        )
        self.input_label.setStyleSheet(field_style)
        self.input_link.setStyleSheet(field_style)
        self.combo_folder.setStyleSheet(field_style)

        form.addRow("Bookmark Label:", self.input_label)
        form.addRow("Bookmark Link:", self.input_link)
        form.addRow("Folder (optional):", self.combo_folder)
        root.addLayout(form)

        button_row = QHBoxLayout()
        button_row.addStretch()
        self.btn_create = QPushButton("Create Bookmark")
        self.btn_close = QPushButton("Close")
        for btn in (self.btn_create, self.btn_close):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background-color:#e24a22; color:#ffffff; border:none; border-radius:4px; padding:6px 14px; font-weight:700; }"
                "QPushButton:hover { background-color:#f05a31; }"
            )
        self.btn_create.clicked.connect(self.accept)
        self.btn_close.clicked.connect(self.reject)
        button_row.addWidget(self.btn_create)
        button_row.addWidget(self.btn_close)
        root.addLayout(button_row)

        self.setStyleSheet(
            "QDialog { background:#ffffff; }"
            "QLabel { color:#111111; font-size:12px; }"
        )

    def bookmark_payload(self):
        return {
            "label": self.input_label.text().strip(),
            "link": self.input_link.text().strip(),
            "folder": self.combo_folder.currentText().strip(),
        }


class BrowseAndExtractDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Browse and Extract Tool")
        self.setModal(True)
        self.resize(1100, 680)
        self._active_link_mode = "video"
        self._links_hidden = False
        self._video_links = []
        self._channel_links = []
        self._bookmark_roots = {}
        self._webengine_view_class = None
        self._browser_view = None
        self._closing = False
        self._screen_fit_applied = False
        self._extract_scan_timer = QTimer(self)
        self._extract_scan_timer.setInterval(1500)
        self._extract_scan_timer.timeout.connect(self._schedule_dom_extract)
        self._autoscroll_timer = QTimer(self)
        self._autoscroll_timer.setInterval(900)
        self._autoscroll_timer.timeout.connect(self._autoscroll_step)
        self._post_scroll_extract_timer = QTimer(self)
        self._post_scroll_extract_timer.setSingleShot(True)
        self._post_scroll_extract_timer.setInterval(650)
        self._post_scroll_extract_timer.timeout.connect(self._schedule_dom_extract)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.addWidget(self._build_left_sources_panel())
        self._main_splitter.addWidget(self._build_center_browser_panel())
        self._main_splitter.addWidget(self._build_right_links_panel())
        self._main_splitter.setStretchFactor(0, 0)
        self._main_splitter.setStretchFactor(1, 1)
        self._main_splitter.setStretchFactor(2, 0)
        self._main_splitter.setSizes([170, 720, 220])
        root.addWidget(self._main_splitter, stretch=1)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(8)

        self.btn_controls = QPushButton("Controls")
        self.btn_controls.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_controls.setStyleSheet(
            "QPushButton { background-color:#d94a22; color:#ffffff; border:none; border-radius:4px; padding:6px 12px; font-weight:700; }"
            "QPushButton:hover { background-color:#f05a31; }"
        )
        bottom.addWidget(self.btn_controls)
        bottom.addStretch()

        self.btn_autoscroll = QPushButton("Start Autoscroll")
        self.btn_autoscroll.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_autoscroll.setStyleSheet(
            "QPushButton { background-color:#e50914; color:#ffffff; border:none; border-radius:4px; padding:6px 16px; font-weight:700; }"
            "QPushButton:hover { background-color:#ff1a25; }"
        )
        self.btn_autoscroll.clicked.connect(self._toggle_autoscroll)
        bottom.addWidget(self.btn_autoscroll)
        bottom.addStretch()

        self.btn_add_links = QPushButton("Add Links")
        self.btn_hide_links = QPushButton("Hide Links")
        self.btn_close = QPushButton("Close")
        for btn in (self.btn_add_links, self.btn_hide_links, self.btn_close):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background-color:#e50914; color:#ffffff; border:none; border-radius:4px; padding:6px 14px; font-weight:700; }"
                "QPushButton:hover { background-color:#ff1a25; }"
            )
        self.btn_add_links.clicked.connect(self._open_add_links_menu)
        self.btn_hide_links.clicked.connect(self._toggle_links_panel)
        self.btn_close.clicked.connect(self.accept)
        bottom.addWidget(self.btn_add_links)
        bottom.addWidget(self.btn_hide_links)
        bottom.addWidget(self.btn_close)
        root.addLayout(bottom)

        self.setStyleSheet(
            "QDialog { background:#ffffff; }"
            "QLabel { color:#111111; }"
            "QTreeWidget, QTextEdit, QLineEdit { background:#ffffff; color:#111111; }"
        )
        self._wire_browser_actions()
        self._refresh_link_panel()
        QTimer.singleShot(0, self._fit_to_available_screen)
        QTimer.singleShot(0, self._initialize_live_browser)

    def _fit_to_available_screen(self):
        screen = self.screen()
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        max_width = max(980, min(available.width() - 24, 1360))
        max_height = max(620, min(available.height() - 24, 860))
        self.resize(max_width, max_height)

        center_x = available.x() + (available.width() - self.width()) // 2
        center_y = available.y() + (available.height() - self.height()) // 2
        self.move(max(available.x(), center_x), max(available.y(), center_y))

        if hasattr(self, "_main_splitter") and self._main_splitter is not None:
            total_width = max_width - 28
            left_width = min(190, max(160, int(total_width * 0.14)))
            right_width = min(280, max(210, int(total_width * 0.18)))
            center_width = max(480, total_width - left_width - right_width)
            self._main_splitter.setSizes([left_width, center_width, right_width])

        self._screen_fit_applied = True

    def showEvent(self, event):
        super().showEvent(event)
        if not self._screen_fit_applied:
            QTimer.singleShot(0, self._fit_to_available_screen)

    def _build_left_sources_panel(self):
        panel = QFrame()
        panel.setMinimumWidth(170)
        panel.setMaximumWidth(210)
        panel.setStyleSheet("QFrame { background:#ffffff; border:1px solid #cfcfcf; }")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self.source_tree = QTreeWidget()
        self.source_tree.setHeaderHidden(True)
        self.source_tree.setStyleSheet(
            "QTreeWidget { background:#ffffff; color:#111111; border:none; }"
            "QTreeWidget::item:selected { background:#9dc6f3; color:#111111; }"
        )

        root_yt = self._make_source_root("YouTube")
        self._make_source_item(root_yt, "Trends", "https://www.youtube.com/feed/trending")
        self._make_source_item(root_yt, "Login", "https://accounts.google.com/")
        root_google = self._make_source_root("Google")
        self._make_source_item(root_google, "Search", "https://www.google.com/")
        root_bing = self._make_source_root("Bing")
        self._make_source_item(root_bing, "Search", "https://www.bing.com/")
        self.source_tree.expandAll()
        self.source_tree.setCurrentItem(root_yt.child(0))
        self.source_tree.itemClicked.connect(self._on_source_item_clicked)
        layout.addWidget(self.source_tree, stretch=1)
        return panel

    def _make_source_root(self, label):
        name = str(label or "").strip()
        item = QTreeWidgetItem([name])
        item.setData(0, Qt.ItemDataRole.UserRole, {"type": "folder", "name": name})
        self.source_tree.addTopLevelItem(item)
        self._bookmark_roots[name] = item
        return item

    def _make_source_item(self, parent_item, label, url, item_type="source"):
        label_text = str(label or "").strip()
        url_text = str(url or "").strip()
        item = QTreeWidgetItem([label_text])
        item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            {
                "type": str(item_type or "source").strip(),
                "label": label_text,
                "url": url_text,
            },
        )
        if parent_item is not None:
            parent_item.addChild(item)
        return item

    def _wire_browser_actions(self):
        self.input_browser_url.returnPressed.connect(self._navigate_to_input_url)
        self.btn_go.clicked.connect(self._navigate_to_input_url)
        self.btn_paste_go.clicked.connect(self._paste_and_go)
        self.btn_back.clicked.connect(self._go_back)
        self.btn_next.clicked.connect(self._go_forward)
        self.btn_stop.clicked.connect(self._stop_loading)
        self.btn_refresh.clicked.connect(self._refresh_browser)
        self.btn_bookmark.clicked.connect(self._bookmark_current_url)
        self.btn_user_pass.clicked.connect(
            lambda: QMessageBox.information(
                self,
                "User/Pass",
                "This browser login helper will be connected in the next backend step.",
            )
        )
        self.btn_extract_video_links.clicked.connect(self._extract_video_links_now)
        self.btn_extract_channel_links.clicked.connect(self._extract_channel_links_now)

    def _build_center_browser_panel(self):
        panel = QFrame()
        panel.setStyleSheet("QFrame { background:#ffffff; border:1px solid #cfcfcf; }")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        nav_row = QHBoxLayout()
        nav_row.setSpacing(6)
        self.btn_bookmark = QPushButton("+ Bookmark")
        self.btn_bookmark.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_bookmark.setStyleSheet(
            "QPushButton { background-color:#e24a22; color:#ffffff; border:none; border-radius:4px; padding:6px 10px; font-weight:700; }"
            "QPushButton:hover { background-color:#f05a31; }"
        )
        nav_row.addWidget(self.btn_bookmark)

        self.input_browser_url = QLineEdit("https://www.youtube.com/feed/trending")
        self.input_browser_url.setStyleSheet(
            "QLineEdit { background:#ffffff; color:#111111; border:1px solid #cfcfcf; border-radius:12px; padding:6px 12px; }"
        )
        nav_row.addWidget(self.input_browser_url, stretch=1)

        self.btn_paste_go = QPushButton("Paste & Go")
        self.btn_go = QPushButton("Go")
        self.btn_back = QPushButton("Back")
        self.btn_next = QPushButton("Next")
        self.btn_stop = QPushButton("Stop")
        self.btn_refresh = QPushButton("Refresh")
        self.btn_user_pass = QPushButton("User/Pass")
        for btn in (
            self.btn_paste_go,
            self.btn_go,
            self.btn_back,
            self.btn_next,
            self.btn_stop,
            self.btn_refresh,
            self.btn_user_pass,
        ):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background-color:#e24a22; color:#ffffff; border:none; border-radius:4px; padding:6px 10px; font-weight:700; }"
                "QPushButton:hover { background-color:#f05a31; }"
            )
            nav_row.addWidget(btn)
        layout.addLayout(nav_row)

        browser_mock = QFrame()
        browser_mock.setStyleSheet("QFrame { background:#ffffff; border:1px solid #d7d7d7; }")
        browser_layout = QVBoxLayout(browser_mock)
        browser_layout.setContentsMargins(18, 12, 18, 12)
        browser_layout.setSpacing(12)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)
        youtube_mark = QLabel("YouTube")
        youtube_mark.setStyleSheet("QLabel { color:#111111; font-size:26px; font-weight:700; }")
        top_bar.addWidget(youtube_mark)
        self.input_mock_search = QLineEdit("knife making")
        self.input_mock_search.setStyleSheet(
            "QLineEdit { background:#ffffff; color:#111111; border:1px solid #d0d0d0; border-radius:3px; padding:6px 8px; }"
        )
        top_bar.addSpacing(20)
        top_bar.addWidget(self.input_mock_search, stretch=1)
        browser_layout.addLayout(top_bar)

        self.lbl_browser_heading = QLabel("Trending")
        self.lbl_browser_heading.setStyleSheet("QLabel { color:#111111; font-size:18px; font-weight:700; }")
        browser_layout.addWidget(self.lbl_browser_heading)

        self.browser_content = QTextEdit()
        self.browser_content.setReadOnly(True)
        self.browser_content.setStyleSheet(
            "QTextEdit { background:#ffffff; color:#222222; border:1px solid #ececec; padding:10px; }"
        )
        self.browser_content.setPlainText(
            "Making a Super Sharp and Hard Knife Blade by our Village Blacksmith\n"
            "6.2K views · 2 weeks ago\n\n"
            "Making a Folding Knife\n"
            "353 views · 6 days ago\n\n"
            "Making a carpentry / bushcraft knife\n"
            "5.3K views · 1 week ago\n\n"
            "This area is UI-only for now. In backend step, this will become the live browser/extract area."
        )
        browser_layout.addWidget(self.browser_content, stretch=1)
        self.browser_stack = QStackedWidget()
        self.browser_stack.addWidget(browser_mock)
        layout.addWidget(self.browser_stack, stretch=1)
        return panel

    def _build_right_links_panel(self):
        panel = QFrame()
        panel.setMinimumWidth(210)
        panel.setMaximumWidth(250)
        panel.setStyleSheet("QFrame { background:#ffffff; border:1px solid #cfcfcf; }")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.btn_extract_video_links = QPushButton("Extract Video Links")
        self.btn_extract_channel_links = QPushButton("Extract Channel Links")
        self.btn_clear_all_links = QPushButton("Clear all links")
        for btn in (self.btn_extract_video_links, self.btn_extract_channel_links, self.btn_clear_all_links):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background-color:#e24a22; color:#ffffff; border:none; border-radius:4px; padding:8px 10px; font-weight:700; }"
                "QPushButton:hover { background-color:#f05a31; }"
            )
        self.btn_extract_video_links.clicked.connect(lambda: self._set_link_mode("video"))
        self.btn_extract_channel_links.clicked.connect(lambda: self._set_link_mode("channel"))
        self.btn_clear_all_links.clicked.connect(self._clear_mock_links)
        layout.addWidget(self.btn_extract_video_links)
        layout.addWidget(self.btn_extract_channel_links)
        layout.addWidget(self.btn_clear_all_links)

        self.lbl_total_videos = QLabel("Total Videos: 0")
        self.lbl_total_channels = QLabel("Total Channels: 0")
        self.lbl_total_videos.setStyleSheet("QLabel { color:#111111; font-size:12px; font-weight:700; }")
        self.lbl_total_channels.setStyleSheet("QLabel { color:#111111; font-size:12px; font-weight:700; }")
        layout.addWidget(self.lbl_total_videos)
        layout.addWidget(self.lbl_total_channels)

        self.text_extracted_links = QTextEdit()
        self.text_extracted_links.setReadOnly(True)
        self.text_extracted_links.setStyleSheet(
            "QTextEdit { background:#ffffff; color:#111111; border:1px solid #cfcfcf; padding:6px; }"
        )
        layout.addWidget(self.text_extracted_links, stretch=1)

        self.links_panel = panel
        return panel

    def _normalize_browser_url(self, raw_url):
        text = str(raw_url or "").strip()
        if not text:
            return ""
        if "://" not in text:
            if text.startswith("/"):
                text = urljoin("https://www.youtube.com", text)
            elif text.startswith("www."):
                text = f"https://{text}"
            else:
                text = f"https://{text}"
        return text

    def _initialize_live_browser(self):
        self._navigate_to_input_url()

    def _ensure_browser_view(self):
        if self._browser_view is not None:
            return True
        if self._webengine_view_class is None:
            try:
                from PyQt6.QtWebEngineWidgets import QWebEngineView as ImportedWebEngineView
                self._webengine_view_class = ImportedWebEngineView
            except Exception as exc:
                self.browser_content.append(f"\n\nLive browser unavailable:\n{exc}")
                return False
        try:
            self._browser_view = self._webengine_view_class()
            self._browser_view.urlChanged.connect(self._on_browser_url_changed)
            self._browser_view.loadFinished.connect(self._on_browser_load_finished)
            self.browser_stack.addWidget(self._browser_view)
            self.browser_stack.setCurrentWidget(self._browser_view)
            self._extract_scan_timer.start()
            return True
        except Exception as exc:
            self._browser_view = None
            self.browser_content.append(f"\n\nFailed to create embedded browser:\n{exc}")
            return False

    def _navigate_to_input_url(self):
        target_url = self._normalize_browser_url(self.input_browser_url.text())
        if not target_url:
            return
        self.input_browser_url.setText(target_url)
        if self._ensure_browser_view():
            self._browser_view.setUrl(QUrl(target_url))
        else:
            self.lbl_browser_heading.setText(target_url)

    def _paste_and_go(self):
        pasted = QApplication.clipboard().text().strip()
        if pasted:
            self.input_browser_url.setText(pasted)
        self._navigate_to_input_url()

    def _go_back(self):
        if self._browser_view is not None:
            self._browser_view.back()

    def _go_forward(self):
        if self._browser_view is not None:
            self._browser_view.forward()

    def _stop_loading(self):
        if self._browser_view is not None:
            self._browser_view.stop()

    def _refresh_browser(self):
        if self._browser_view is not None:
            self._browser_view.reload()
        else:
            self._navigate_to_input_url()

    def _bookmark_current_url(self):
        current_url = self.input_browser_url.text().strip()
        if not current_url:
            return
        current_item = self.source_tree.currentItem()
        current_folder = self._folder_name_for_item(current_item) or "YouTube"
        dlg = BookmarkDialog(
            self,
            initial_label=self._suggest_bookmark_label(current_url),
            initial_link=current_url,
            folder_options=list(self._bookmark_roots.keys()),
            initial_folder=current_folder,
        )
        dlg.move(self.geometry().center() - dlg.rect().center())
        dlg.raise_()
        dlg.activateWindow()
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        payload = dlg.bookmark_payload()
        label = str(payload.get("label", "")).strip()
        link = self._normalize_browser_url(payload.get("link", ""))
        folder_name = str(payload.get("folder", "")).strip() or "YouTube"

        if not label:
            QMessageBox.warning(self, "Bookmark", "Bookmark label is required.")
            return
        if not link:
            QMessageBox.warning(self, "Bookmark", "Bookmark link is invalid.")
            return

        folder_item = self._bookmark_roots.get(folder_name)
        if folder_item is None:
            folder_item = self._make_source_root(folder_name)

        existing = self._find_existing_bookmark(folder_item, label=label, link=link)
        if existing is not None:
            self.source_tree.setCurrentItem(existing)
            QMessageBox.information(self, "Bookmark", "This bookmark already exists.")
            return

        bookmark_item = self._make_source_item(folder_item, label, link, item_type="bookmark")
        folder_item.setExpanded(True)
        self.source_tree.setCurrentItem(bookmark_item)
        self.input_browser_url.setText(link)
        self._set_browser_heading(label)

    def _set_browser_heading(self, text):
        value = str(text or "").strip()
        self.lbl_browser_heading.setText(value or "Browser")

    def _folder_name_for_item(self, item):
        if item is None:
            return ""
        data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        if data.get("type") == "folder":
            return str(data.get("name", "")).strip()
        parent_item = item.parent()
        if parent_item is None:
            return ""
        parent_data = parent_item.data(0, Qt.ItemDataRole.UserRole) or {}
        if parent_data.get("type") == "folder":
            return str(parent_data.get("name", "")).strip()
        return ""

    def _suggest_bookmark_label(self, url_text):
        url_value = str(url_text or "").strip()
        current_heading = self.lbl_browser_heading.text().strip()
        if current_heading and "http" not in current_heading.lower():
            lowered = current_heading.lower()
            if lowered not in {"youtube", "google", "bing", "browser"}:
                return current_heading
        parsed = urlparse(url_value)
        path = str(parsed.path or "").strip("/")
        if path:
            label = path.split("/")[-1].replace("-", " ").replace("_", " ").strip()
            if label:
                return label.title()
        host = parsed.netloc.replace("www.", "").strip()
        return host or "Bookmark"

    def _find_existing_bookmark(self, folder_item, label="", link=""):
        if folder_item is None:
            return None
        target_label = str(label or "").strip().lower()
        target_link = str(link or "").strip().lower()
        for idx in range(folder_item.childCount()):
            child = folder_item.child(idx)
            if child is None:
                continue
            data = child.data(0, Qt.ItemDataRole.UserRole) or {}
            if data.get("type") != "bookmark":
                continue
            child_label = str(data.get("label", child.text(0))).strip().lower()
            child_link = str(data.get("url", "")).strip().lower()
            if child_label == target_label or child_link == target_link:
                return child
        return None

    def _on_browser_url_changed(self, qurl):
        url_text = qurl.toString().strip()
        if not url_text:
            return
        self.input_browser_url.setText(url_text)
        host_text = urlparse(url_text).netloc or url_text
        self._set_browser_heading(host_text)

    def _on_browser_load_finished(self, ok):
        if ok and self._browser_view is not None and not self._closing:
            self._schedule_dom_extract()

    @staticmethod
    def _normalize_video_link(raw_link, base_url="https://www.youtube.com"):
        text = unescape(str(raw_link or "").strip().strip('"').strip("'"))
        if not text:
            return ""
        if text.startswith("//"):
            text = "https:" + text
        elif text.startswith("/"):
            text = urljoin(base_url, text)
        parsed = urlparse(text)
        if not parsed.scheme:
            text = urljoin(base_url, text)
            parsed = urlparse(text)
        host = parsed.netloc.lower()
        path = parsed.path or ""
        if "youtu.be" in host:
            short_id = path.strip("/").split("/", 1)[0]
            return f"https://www.youtube.com/watch?v={short_id}" if short_id else ""
        if "youtube.com" not in host and "youtube-nocookie.com" not in host:
            return ""
        query = parse_qs(parsed.query)
        if "/watch" in path and query.get("v"):
            return f"https://www.youtube.com/watch?v={query['v'][0]}"
        if path.startswith("/shorts/"):
            short_id = path.split("/shorts/", 1)[1].split("/", 1)[0]
            return f"https://www.youtube.com/shorts/{short_id}" if short_id else ""
        return ""

    @staticmethod
    def _normalize_channel_link(raw_link, base_url="https://www.youtube.com"):
        text = unescape(str(raw_link or "").strip().strip('"').strip("'"))
        if not text:
            return ""
        if text.startswith("//"):
            text = "https:" + text
        elif text.startswith("/"):
            text = urljoin(base_url, text)
        parsed = urlparse(text)
        if not parsed.scheme:
            text = urljoin(base_url, text)
            parsed = urlparse(text)
        host = parsed.netloc.lower()
        path = parsed.path or ""
        if "youtube.com" not in host and "youtube-nocookie.com" not in host:
            return ""
        if path.startswith("/channel/") or path.startswith("/@") or path.startswith("/c/") or path.startswith("/user/"):
            return f"https://www.youtube.com{path.rstrip('/')}" if path.strip("/") else ""
        return ""

    def _extract_links_from_html(self, html_text):
        html = str(html_text or "")
        base_url = self.input_browser_url.text().strip() or "https://www.youtube.com"
        found_urls = set(re.findall(r'https?://[^\s"\'<>]+', html, flags=re.IGNORECASE))
        found_urls.update(re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE))
        found_urls.update(re.findall(r'src=["\']([^"\']+)["\']', html, flags=re.IGNORECASE))

        existing_videos = {link.lower() for link in self._video_links}
        existing_channels = {link.lower() for link in self._channel_links}
        new_videos = []
        new_channels = []

        for raw_url in found_urls:
            video_link = self._normalize_video_link(raw_url, base_url=base_url)
            if video_link and video_link.lower() not in existing_videos:
                existing_videos.add(video_link.lower())
                new_videos.append(video_link)
            channel_link = self._normalize_channel_link(raw_url, base_url=base_url)
            if channel_link and channel_link.lower() not in existing_channels:
                existing_channels.add(channel_link.lower())
                new_channels.append(channel_link)

        changed = False
        if new_videos:
            self._video_links.extend(new_videos[:500])
            self._video_links = self._video_links[:5000]
            changed = True
        if new_channels:
            self._channel_links.extend(new_channels[:500])
            self._channel_links = self._channel_links[:5000]
            changed = True
        if changed:
            self._refresh_link_panel()

    def _on_browser_html_ready(self, html_text):
        self._extract_links_from_html(html_text)

    def _extract_video_links_now(self):
        self._active_link_mode = "video"
        self._schedule_dom_extract()
        self._refresh_link_panel()

    def _extract_channel_links_now(self):
        self._active_link_mode = "channel"
        self._schedule_dom_extract()
        self._refresh_link_panel()

    def _schedule_dom_extract(self):
        if self._browser_view is None or self._closing or not self.isVisible():
            return
        js_code = """
            (() => {
                const values = new Set();
                const pushValue = (value) => {
                    const text = String(value || '').trim();
                    if (text) values.add(text);
                };

                document.querySelectorAll('a[href], a[title], ytd-thumbnail a, a#video-title').forEach((node) => {
                    pushValue(node.href);
                    pushValue(node.getAttribute('href'));
                });

                document.querySelectorAll('[src]').forEach((node) => {
                    pushValue(node.getAttribute('src'));
                });

                pushValue(window.location.href || '');
                return { hrefs: Array.from(values), url: window.location.href || '' };
            })();
        """
        self._browser_view.page().runJavaScript(js_code, self._on_dom_links_ready)

    def _on_dom_links_ready(self, payload):
        if self._closing or not isinstance(payload, dict):
            return
        hrefs = payload.get("hrefs", [])
        current_url = str(payload.get("url", "")).strip()
        if current_url:
            self.input_browser_url.setText(current_url)
        if hrefs:
            self._extract_links_from_html("\n".join(str(href) for href in hrefs))

    def _toggle_autoscroll(self):
        if self._autoscroll_timer.isActive():
            self._autoscroll_timer.stop()
            self._post_scroll_extract_timer.stop()
            self.btn_autoscroll.setText("Start Autoscroll")
            return
        self._autoscroll_timer.start()
        self._schedule_dom_extract()
        self.btn_autoscroll.setText("Stop Autoscroll")

    def _autoscroll_step(self):
        if self._browser_view is None or self._closing or not self.isVisible():
            self._autoscroll_timer.stop()
            self._post_scroll_extract_timer.stop()
            self.btn_autoscroll.setText("Start Autoscroll")
            return
        js_code = """
            (() => {
                const values = new Set();
                const pushValue = (value) => {
                    const text = String(value || '').trim();
                    if (text) values.add(text);
                };

                const root = document.scrollingElement || document.documentElement || document.body;
                const step = Math.max(520, Math.floor(window.innerHeight * 0.92));
                if (root) {
                    root.scrollTop = Math.min(root.scrollTop + step, root.scrollHeight);
                } else {
                    window.scrollBy(0, step);
                }

                document.querySelectorAll('a[href], ytd-thumbnail a, a#video-title').forEach((node) => {
                    pushValue(node.href);
                    pushValue(node.getAttribute('href'));
                });

                return {
                    hrefs: Array.from(values),
                    url: window.location.href || '',
                    scrollTop: root ? root.scrollTop : 0,
                    scrollHeight: root ? root.scrollHeight : 0
                };
            })();
        """
        self._browser_view.page().runJavaScript(js_code, self._on_dom_links_ready)
        self._post_scroll_extract_timer.start()

    def _on_source_item_clicked(self, item, _column):
        if item is None:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        item_type = str(data.get("type", "")).strip()
        if item_type == "folder":
            return

        target_url = str(data.get("url", "")).strip()
        heading_text = str(data.get("label", item.text(0))).strip() or item.text(0).strip()
        if not target_url:
            text = item.text(0).strip()
            if text == "Trends":
                target_url = "https://www.youtube.com/feed/trending"
            elif text == "Login":
                target_url = "https://accounts.google.com/"
            elif text == "Search":
                target_url = "https://www.youtube.com/results?search_query=knife+making"
                heading_text = "Search Results"
            else:
                target_url = "https://www.youtube.com/"
        self.input_browser_url.setText(target_url)
        self._set_browser_heading(heading_text)
        self._navigate_to_input_url()

    def _set_link_mode(self, mode):
        self._active_link_mode = "channel" if mode == "channel" else "video"
        self._refresh_link_panel()

    def _refresh_link_panel(self):
        video_count = len(self._video_links)
        channel_count = len(self._channel_links)
        self.lbl_total_videos.setText(f"Total Videos: {video_count}")
        self.lbl_total_channels.setText(f"Total Channels: {channel_count}")
        if self._active_link_mode == "channel":
            self.text_extracted_links.setPlainText("\n".join(self._channel_links))
        else:
            self.text_extracted_links.setPlainText("\n".join(self._video_links))

    def _clear_mock_links(self):
        self._video_links = []
        self._channel_links = []
        self._refresh_link_panel()

    def _toggle_links_panel(self):
        self._links_hidden = not self._links_hidden
        self.links_panel.setVisible(not self._links_hidden)
        self.btn_hide_links.setText("Show Links" if self._links_hidden else "Hide Links")

    def _open_add_links_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#ffffff; color:#111111; border:1px solid #cfcfcf; }"
            "QMenu::item { padding:6px 16px; }"
            "QMenu::item:selected { background:#f3d0d3; color:#111111; }"
        )
        act_add_videos = menu.addAction("Add links to Videos Tool")
        act_add_channels = menu.addAction("Add links to Channels Tool")
        chosen = menu.exec(self.btn_add_links.mapToGlobal(self.btn_add_links.rect().bottomLeft()))
        if chosen == act_add_videos:
            self._confirm_add_links("Videos Tool")
        elif chosen == act_add_channels:
            self._confirm_add_links("Channels Tool")

    def _add_links_to_target(self, target_name):
        owner = self.parent()
        if owner is None:
            return 0

        if target_name == "Channels Tool":
            links = list(self._channel_links)
            if not links:
                return 0
            main_window = getattr(owner, "main_window", None)
            if main_window is not None and hasattr(main_window, "tab_channels"):
                target_tab = main_window.tab_channels
                if hasattr(target_tab, "receive_links_for_import"):
                    target_tab.receive_links_for_import(links)
                elif hasattr(target_tab, "receive_payload"):
                    target_tab.receive_payload(
                        "\n".join(links),
                        f"Received {len(links)} channel link(s) from Browse and Extract Tool.",
                    )
                if hasattr(main_window, "switch_tab"):
                    main_window.switch_tab(4)
            return len(links)

        links = list(self._video_links)
        if not links:
            return 0

        if hasattr(owner, "switch_mode"):
            owner.switch_mode("browse")
        if hasattr(owner, "input_video_links"):
            existing = [line.strip() for line in owner.input_video_links.toPlainText().splitlines() if line.strip()]
            seen = {line.lower() for line in existing}
            merged = list(existing)
            for link in links:
                if link.lower() in seen:
                    continue
                seen.add(link.lower())
                merged.append(link)
            owner.input_video_links.setPlainText("\n".join(merged))
        if hasattr(owner, "_set_status"):
            owner._set_status(f"Added {len(links)} extracted video link(s) to Browse or Import.")
        return len(links)

    def _confirm_add_links(self, target_name):
        link_count = self._add_links_to_target(target_name)
        if link_count <= 0:
            QMessageBox.warning(self, "Browse and Extract Tool", f"No links available for {target_name}.")
            return
        dlg = ConfirmAddLinksDialog(self, link_count=link_count)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.accept()

    def closeEvent(self, event):
        self._closing = True
        self._extract_scan_timer.stop()
        self._autoscroll_timer.stop()
        self._post_scroll_extract_timer.stop()
        try:
            if self._browser_view is not None:
                self._browser_view.stop()
        except Exception:
            pass
        super().closeEvent(event)


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
        self._metadata_worker = None
        self._invalid_import_count = 0
        self._invalid_import_rows = []
        self._all_rows_cache = []
        self._active_filter = self._default_filter_state()
        self._default_column_widths = dict(VIDEO_DEFAULT_COLUMN_WIDTHS)
        self._table_search_dialog = None
        self._search_hits = []
        self._search_hit_index = -1
        self._search_term = ""
        self._thumbnail_cache = {}
        self._thumbnail_pending_rows = {}
        self._thumbnail_inflight = set()
        self._thumbnail_fallback_workers = {}
        self._max_thumbnail_fallback_workers = 2
        self._thumbnail_manager = QNetworkAccessManager(self)
        self._thumbnail_manager.finished.connect(self._on_thumbnail_finished)
        self._scrollbar_tune_timer = QTimer(self)
        self._scrollbar_tune_timer.setSingleShot(True)
        self._scrollbar_tune_timer.setInterval(80)
        self._scrollbar_tune_timer.timeout.connect(self._tune_horizontal_scrollbar)
        self._status_flush_timer = QTimer(self)
        self._status_flush_timer.setSingleShot(True)
        self._status_flush_timer.setInterval(120)
        self._status_flush_timer.timeout.connect(self._flush_status_message)
        self._pending_status_message = ""
        self._title_analysis_stop_words = list(DEFAULT_STOP_WORDS)
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

    @staticmethod
    def _empty_video_row_dict():
        return {
            "Video ID": "",
            "Video Link": "",
            "Source": "YouTube",
            "Search Phrase": "",
            "Title": "",
            "Description": "",
            "Thumbnail URL": "",
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

    @staticmethod
    def _default_filter_state():
        return {
            "source": "All Sources",
            "phrase": "",
            "title": "",
            "description": "",
            "numeric": {},
        }

    def _normalize_video_row(self, video):
        row_dict = self._empty_video_row_dict()
        for key in row_dict.keys():
            if key in video:
                row_dict[key] = str(video.get(key, "")).strip()
        row_dict["Source"] = row_dict["Source"] or "YouTube"
        row_dict["Video ID"] = row_dict["Video ID"].strip()
        row_dict["Video Link"] = row_dict["Video Link"].strip()
        if row_dict["Video Link"].startswith("www.youtube.com/"):
            row_dict["Video Link"] = f"https://{row_dict['Video Link']}"
        if row_dict["Video ID"] and "youtube.com/watch?v=" not in row_dict["Video Link"]:
            row_dict["Video Link"] = f"https://www.youtube.com/watch?v={row_dict['Video ID']}"
        row_dict["Thumbnail URL"] = str(video.get("Thumbnail URL", row_dict["Thumbnail URL"])).strip()
        return row_dict

    def _set_table_text_item(self, row, column_name, text):
        col = VIDEO_COLUMN_INDEX[column_name]
        item = QTableWidgetItem(str(text))
        if column_name in {"Video ID", "Source", "Rating", "Comments", "View Count", "Length Seconds", "Published Age (Days)", "Avg. Views per Day", "Subtitles", "Subscribers"}:
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        if column_name in {"Video Link", "Channel Link"}:
            link_text = str(text).strip()
            if link_text.startswith("http://") or link_text.startswith("https://"):
                item.setForeground(QColor("#1a73e8"))
                item.setToolTip(link_text)
        elif column_name in {"Title", "Description", "Tags", "Channel"}:
            item.setToolTip(str(text))
        self.videos_table.setItem(row, col, item)

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
        self._refresh_header_filter_tooltips()
        self._update_status_labels()

    def _build_mode_bar(self, parent_layout):
        bar = QFrame()
        bar.setStyleSheet("QFrame { background-color: transparent; }")
        h = QHBoxLayout(bar)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)

        self.btn_mode_search = QPushButton("Search")
        self.btn_mode_browse = QPushButton("Browse or Import")
        self.btn_tools = QPushButton("Tools")
        self.btn_analyze = QPushButton("Analyze")

        for btn in (self.btn_mode_search, self.btn_mode_browse, self.btn_tools):
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
        self._setup_tools_menu()

        h.addWidget(self.btn_mode_search)
        h.addWidget(self.btn_mode_browse)
        h.addWidget(self.btn_tools)
        h.addStretch()
        h.addWidget(self.btn_analyze)
        parent_layout.addWidget(bar)

    def _setup_tools_menu(self):
        menu = QMenu(self.btn_tools)
        menu.setStyleSheet(
            "QMenu { background-color:#ffffff; color:#111111; border:1px solid #c7c7c7; }"
            "QMenu::item { padding:6px 16px; }"
            "QMenu::item:selected { background-color:#f1d5df; color:#111111; }"
        )

        act_spinner = menu.addAction("Content Spinner Tool")
        act_title_generator = menu.addAction("Video Title Generator Tool")
        act_ke = menu.addAction("Keywords Everywhere Tool")
        act_download = menu.addAction("Download Youtube Video Tool")

        act_spinner.triggered.connect(lambda: self._show_coming_soon("Content Spinner Tool"))
        act_title_generator.triggered.connect(self._open_video_title_generator_tool)
        act_ke.triggered.connect(lambda: self._show_coming_soon("Keywords Everywhere Tool"))
        act_download.triggered.connect(lambda: self._show_coming_soon("Download Youtube Video Tool"))

        self.btn_tools.setMenu(menu)

    def _open_video_title_generator_tool(self):
        seed_keyword = self.input_search_phrase.text().strip()
        dlg = VideoTitleGeneratorDialog(self, initial_keyword=seed_keyword)
        dlg.exec()

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
        self.btn_browser_links.clicked.connect(self._open_browse_extract_dialog)
        self.btn_content_links.clicked.connect(lambda: self._show_coming_soon("Browse or Import -> Content extract"))
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
        self.videos_table.setColumnCount(len(VIDEO_TABLE_COLUMNS))
        self.videos_table.setHorizontalHeaderLabels(VIDEO_TABLE_COLUMNS)
        self.videos_table.setAlternatingRowColors(False)
        self.videos_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.videos_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.videos_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.videos_table.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.videos_table.setWordWrap(False)
        self.videos_table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.videos_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.videos_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
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
            + TABLE_SCROLLBAR_STYLE
        )

        header = self.videos_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.sectionClicked.connect(self._on_header_section_clicked)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        for col in range(2, len(VIDEO_TABLE_COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)

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
        self._defer_scrollbar_tune()
        return panel

    def _tune_horizontal_scrollbar(self):
        if not hasattr(self, "videos_table"):
            return
        scrollbar = self.videos_table.horizontalScrollBar()
        if scrollbar is None:
            return
        viewport_width = max(240, self.videos_table.viewport().width())
        page_step = max(120, int(viewport_width * 0.24))
        scrollbar.setPageStep(page_step)
        scrollbar.setSingleStep(max(24, page_step // 4))

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
            if worker.isRunning():
                worker.requestInterruption()
                worker.wait(700)
        self._thumbnail_fallback_workers.clear()

    def _clear_all_video_data(self):
        if self._metadata_worker is not None and self._metadata_worker.isRunning():
            self._metadata_worker.stop()
        self._all_rows_cache = []
        self._active_filter = self._default_filter_state()
        self._clear_table_ui_only()

    def _set_status(self, message):
        self._pending_status_message = str(message or "").strip()
        if not self._pending_status_message:
            return
        if not self._status_flush_timer.isActive():
            self._status_flush_timer.start()

    def _flush_status_message(self):
        message = str(self._pending_status_message or "").strip()
        if not message:
            return
        self.lbl_status.setText(message)
        if self.main_window is not None:
            self.main_window.statusBar().showMessage(message, 4000)

    def _defer_scrollbar_tune(self):
        if not self._scrollbar_tune_timer.isActive():
            self._scrollbar_tune_timer.start()

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

    def _start_metadata_enrichment(self):
        if self._metadata_worker is not None and self._metadata_worker.isRunning():
            self._metadata_worker.stop()
            self._metadata_worker.wait(1000)

        if not self._all_rows_cache:
            return

        proxy_payload = self._current_proxy_payload()
        proxy_url = proxy_payload["proxies"][0] if proxy_payload.get("enabled") and proxy_payload.get("proxies") else ""
        self._metadata_worker = VideoMetadataEnrichWorker(self._all_rows_cache, proxy_url=proxy_url)
        self._metadata_worker.row_enriched_signal.connect(self._apply_enriched_video_row)
        self._metadata_worker.status_signal.connect(self._set_status)
        self._metadata_worker.error_signal.connect(lambda _msg: None)
        self._metadata_worker.finished_signal.connect(self._on_metadata_enrich_finished)
        self._metadata_worker.start()

    def _find_cache_index_by_video_id(self, video_id):
        key = str(video_id or "").strip()
        if not key:
            return -1
        for idx, row in enumerate(self._all_rows_cache):
            if str(row.get("Video ID", "")).strip() == key:
                return idx
        return -1

    def _find_table_row_by_video_id(self, video_id):
        key = str(video_id or "").strip()
        if not key:
            return -1
        col = VIDEO_COLUMN_INDEX["Video ID"]
        for row in range(self.videos_table.rowCount()):
            item = self.videos_table.item(row, col)
            if item is not None and item.text().strip() == key:
                return row
        return -1

    def _apply_enriched_video_row(self, video_id, details):
        idx = self._find_cache_index_by_video_id(video_id)
        if idx < 0:
            return
        merged = dict(self._all_rows_cache[idx])
        for key, value in dict(details or {}).items():
            text = str(value or "").strip()
            if text:
                merged[key] = text
        self._all_rows_cache[idx] = merged

        row = self._find_table_row_by_video_id(video_id)
        if row < 0:
            return
        thumb_url = str(merged.get("Thumbnail URL", "")).strip()
        if thumb_url:
            thumb_item = self.videos_table.item(row, VIDEO_COLUMN_INDEX["Image"])
            if thumb_item is not None:
                thumb_item.setToolTip(thumb_url)
            if thumb_url in self._thumbnail_cache:
                self._apply_thumbnail_to_row(row, thumb_url)
            else:
                self._queue_thumbnail_load(row, thumb_url)

        for column_name in VIDEO_TEXT_COLUMNS:
            self._set_table_text_item(row, column_name, merged.get(column_name, ""))

    def _on_metadata_enrich_finished(self, result):
        updated = int((result or {}).get("updated", 0))
        stopped = bool((result or {}).get("stopped", False))
        if stopped:
            self._set_status(f"Metadata enrich stopped. Updated {updated} row(s).")
        elif updated > 0:
            self._set_status(f"Metadata enrich finished. Updated {updated} row(s).")
        self._metadata_worker = None

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
        if self._metadata_worker is not None and self._metadata_worker.isRunning():
            self._metadata_worker.stop()

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
        if self._metadata_worker is not None and self._metadata_worker.isRunning():
            self._metadata_worker.stop()

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
                    **self._empty_video_row_dict(),
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
        if count > 0:
            self._start_metadata_enrichment()

    def _on_search_finished(self, result):
        self._set_search_running(False)
        count = int((result or {}).get("count", 0))
        if count > 0:
            self._set_status(f"Done. Loaded {count} videos.")
        else:
            self._set_status("Search finished.")
        self._search_worker = None
        if count > 0:
            self._start_metadata_enrichment()

    def _on_trending_finished(self, result):
        self._set_search_running(False)
        count = int((result or {}).get("count", 0))
        if count > 0:
            self._set_status(f"Done. Loaded {count} trending videos.")
        else:
            self._set_status("Trending load finished.")
        self._trending_worker = None
        if count > 0:
            self._start_metadata_enrichment()

    def _append_video_row(self, video):
        if video is None:
            return
        row_dict = self._normalize_video_row(video)
        self._all_rows_cache.append(dict(row_dict))
        if not self._row_matches_filter(row_dict, self._active_filter):
            return

        scrollbar = self.videos_table.verticalScrollBar()
        keep_bottom = (
            scrollbar is None
            or scrollbar.maximum() <= 0
            or scrollbar.value() >= max(0, scrollbar.maximum() - 24)
        )

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

        for column_name in VIDEO_TEXT_COLUMNS:
            self._set_table_text_item(row, column_name, row_dict.get(column_name, ""))

        if keep_bottom:
            self.videos_table.scrollToBottom()
        self._defer_scrollbar_tune()
        self._update_status_labels()

    def _on_table_cell_double_clicked(self, row, column):
        if column != VIDEO_COLUMN_INDEX["Video Link"]:
            return
        item = self.videos_table.item(row, column)
        if item is None:
            return
        link = item.text().strip()
        if link.startswith("http://") or link.startswith("https://"):
            webbrowser.open_new_tab(link)

    @staticmethod
    def _parse_numeric_value(raw_value):
        text = str(raw_value or "").strip()
        if not text:
            return None
        lowered = text.lower()
        if lowered in {"not-given", "n/a", "-", "none"}:
            return None
        cleaned = text.replace(",", "").replace("+", "").strip()
        match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
        if not match:
            return None
        try:
            return float(match.group(0))
        except Exception:
            return None

    @staticmethod
    def _evaluate_numeric_expression(value, expression):
        expr = str(expression or "").strip()
        if not expr:
            return True
        match = re.fullmatch(r"(>=|<=|!=|==|=|>|<)\s*(-?\d+(?:\.\d+)?)", expr)
        if not match:
            return None
        operator = match.group(1)
        target = float(match.group(2))
        if operator == ">":
            return value > target
        if operator == "<":
            return value < target
        if operator == ">=":
            return value >= target
        if operator == "<=":
            return value <= target
        if operator in {"=", "=="}:
            return value == target
        if operator == "!=":
            return value != target
        return None

    @classmethod
    def _row_matches_filter(cls, row, flt):
        source = str((flt or {}).get("source", "All Sources")).strip()
        phrase = str((flt or {}).get("phrase", "")).strip().lower()
        title = str((flt or {}).get("title", "")).strip().lower()
        desc = str((flt or {}).get("description", "")).strip().lower()
        numeric = dict((flt or {}).get("numeric", {}) or {})

        if source and source != "All Sources":
            if str(row.get("Source", "")).strip() != source:
                return False
        if phrase and phrase not in str(row.get("Search Phrase", "")).lower():
            return False
        if title and title not in str(row.get("Title", "")).lower():
            return False
        if desc and desc not in str(row.get("Description", "")).lower():
            return False
        for column_name, expression in numeric.items():
            expr = str(expression or "").strip()
            if not expr:
                continue
            parsed_value = cls._parse_numeric_value(row.get(column_name, ""))
            if parsed_value is None:
                return False
            matched = cls._evaluate_numeric_expression(parsed_value, expr)
            if matched is not True:
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

        for column_name in VIDEO_TEXT_COLUMNS:
            self._set_table_text_item(row, column_name, row_dict.get(column_name, ""))

    def _rebuild_table_from_cache(self):
        self._reset_table_search_state()
        self.videos_table.setUpdatesEnabled(False)
        self.videos_table.setRowCount(0)
        self._thumbnail_pending_rows.clear()
        self._thumbnail_inflight.clear()
        for row_dict in self._all_rows_cache:
            if self._row_matches_filter(row_dict, self._active_filter):
                self._draw_row_without_caching(row_dict)
        self.videos_table.setUpdatesEnabled(True)
        self._update_status_labels()
        self._refresh_header_filter_tooltips()
        self._defer_scrollbar_tune()
        self._set_status(f"Filter applied: {self.videos_table.rowCount()} / {len(self._all_rows_cache)} rows.")

    def open_filters_dialog(self):
        dlg = VideosFilterDialog(self, sources=self._sources_from_cache(), preset=self._active_filter)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        next_filter = dlg.filter_values()
        next_filter["numeric"] = dict(self._active_filter.get("numeric", {}) or {})
        self._active_filter = next_filter
        self._rebuild_table_from_cache()

    def reset_video_filters(self):
        self._active_filter = self._default_filter_state()
        self._rebuild_table_from_cache()

    def _refresh_header_filter_tooltips(self):
        for index, column_name in enumerate(VIDEO_TABLE_COLUMNS):
            item = self.videos_table.horizontalHeaderItem(index)
            if item is None:
                continue
            if column_name in VIDEO_NUMERIC_FILTERABLE_COLUMNS:
                current_expr = str(self._active_filter.get("numeric", {}).get(column_name, "")).strip()
                if current_expr:
                    item.setToolTip(f"Active filter: {current_expr}")
                else:
                    item.setToolTip("Click to filter this numeric column. Examples: >500000, >=1000, <60, =0")
            else:
                item.setToolTip("")

    def _on_header_section_clicked(self, section):
        if section < 0 or section >= len(VIDEO_TABLE_COLUMNS):
            return
        column_name = VIDEO_TABLE_COLUMNS[section]
        if column_name not in VIDEO_NUMERIC_FILTERABLE_COLUMNS:
            return

        current_expr = str(self._active_filter.get("numeric", {}).get(column_name, "")).strip()
        dlg = VideoNumericFilterDialog(self, column_name=column_name, current_expression=current_expr)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        expression = dlg.selected_expression()
        next_numeric = dict(self._active_filter.get("numeric", {}) or {})
        if expression is None or not str(expression).strip():
            next_numeric.pop(column_name, None)
        else:
            probe = self._evaluate_numeric_expression(1.0, expression)
            if probe is None:
                QMessageBox.warning(
                    self,
                    "Videos Tool",
                    "Numeric filter format is invalid. Use examples like >500000, >=1000, <60, =0.",
                )
                return
            next_numeric[column_name] = str(expression).strip()

        self._active_filter["numeric"] = next_numeric
        self._refresh_header_filter_tooltips()
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
        self._defer_scrollbar_tune()
        self._set_status("Auto-fit column widths applied.")

    def reset_column_widths(self):
        if self.videos_table.columnCount() == 0:
            return
        header = self.videos_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        for col in range(2, self.videos_table.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        for col, width in self._default_column_widths.items():
            self.videos_table.setColumnWidth(col, width)
        self._defer_scrollbar_tune()
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
        item = self.videos_table.item(row, VIDEO_COLUMN_INDEX["Video Link"])
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
        payload = {"Thumbnail URL": thumb_url, "Thumbnail Pixmap": thumb_pixmap}
        for column_name in VIDEO_TEXT_COLUMNS:
            col = VIDEO_COLUMN_INDEX[column_name]
            item = self.videos_table.item(row, col)
            payload[column_name] = item.text().strip() if item is not None else ""
        return payload

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

    def _open_analyze_video_tags_dialog(self):
        rows = self._collect_current_rows_for_tag_analysis()
        if not rows:
            QMessageBox.warning(self, "Analyze Video Tags", "No videos available to analyze.")
            return

        dlg = AnalyzeVideoTagsDialog(self)
        dlg.btn_file.clicked.connect(lambda: self._open_analyze_video_tags_file_menu(dlg))
        dlg.btn_clear_filters.clicked.connect(dlg.reset_filters)
        dlg.btn_clear.clicked.connect(dlg.clear_results)
        worker = VideoTagsAnalyzeWorker(rows)
        worker.progress_signal.connect(dlg.set_progress)
        worker.finished_signal.connect(dlg.populate_rows)
        worker.finished.connect(worker.deleteLater)
        dlg._worker = worker
        worker.start()
        dlg.exec()

    def _generate_title_word_stats(self, dialog, rows):
        if dialog is None:
            return
        if dialog._worker is not None and dialog._worker.isRunning():
            QMessageBox.information(self, "Analyze Titles", "Word stats generation is already running.")
            return

        target_rows = [dict(row) for row in (rows or []) if isinstance(row, dict)]
        if not target_rows:
            QMessageBox.warning(self, "Analyze Titles", "No rows available to analyze.")
            return

        dialog.btn_generate.setEnabled(False)
        dialog.btn_generate.setText("Generating...")
        dialog.lbl_total.setText(f"Processing: 0/{len(target_rows)}")
        dialog.table.setRowCount(0)

        worker = VideoTitleKeywordsAnalyzeWorker(
            rows=target_rows,
            word_count=dialog.selected_word_count(),
            use_stop_words=dialog.chk_use_stop_words.isChecked(),
            stop_words=dialog.stop_words(),
        )
        worker.progress_signal.connect(dialog.set_progress)
        worker.finished_signal.connect(dialog.populate_rows)
        worker.finished.connect(lambda: setattr(dialog, "_worker", None))
        worker.finished.connect(worker.deleteLater)
        dialog._worker = worker
        worker.start()

    def _analyze_video_tags_visible_rows(self, dialog):
        if dialog is None:
            return []
        return list(dialog._filtered_rows(dialog._all_tag_rows))

    def _export_analyze_video_tags_rows(self, dialog, rows=None, as_txt=False):
        if dialog is None:
            return
        rows = list(rows) if rows is not None else self._analyze_video_tags_visible_rows(dialog)
        if not rows:
            QMessageBox.warning(self, "Analyze Video Tags", "No tag rows to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Video Tag Stats",
            "analyze_video_tags.txt" if as_txt else "analyze_video_tags.csv",
            "Text Files (*.txt)" if as_txt else "CSV Files (*.csv)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8-sig") as handle:
                if as_txt:
                    handle.write(
                        "Tags\tOccurrences in Listings\tPercentage in Listings\tAvg. Views per Tag\tAvg. Likes per Tag\n"
                    )
                else:
                    handle.write(
                        "Tags,Occurrences in Listings,Percentage in Listings,Avg. Views per Tag,Avg. Likes per Tag\n"
                    )
                for row in rows:
                    cells = [
                        str(row.get("tag", "")),
                        str(int(row.get("occurrences", 0))),
                        f"{float(row.get('percentage', 0.0)):.1f}",
                        f"{float(row.get('avg_views', 0.0)):.1f}",
                        f"{float(row.get('avg_likes', 0.0)):.1f}",
                    ]
                    if as_txt:
                        handle.write("\t".join(cells) + "\n")
                    else:
                        escaped = [cell.replace('"', '""') for cell in cells]
                        quoted = ['"' + cell + '"' for cell in escaped]
                        handle.write(",".join(quoted) + "\n")
        except Exception as exc:
            QMessageBox.warning(self, "Analyze Video Tags", f"Failed to export file:\n{exc}")
            return

        self._set_status(f"Exported {len(rows)} tag row(s).")

    def _copy_analyze_video_tags_rows_to_clipboard(self, dialog, rows=None, tags_only=False):
        if dialog is None:
            return
        rows = list(rows) if rows is not None else self._analyze_video_tags_visible_rows(dialog)
        if not rows:
            QMessageBox.warning(self, "Analyze Video Tags", "No tag rows to copy.")
            return

        if tags_only:
            text = "\n".join(
                str(row.get("tag", "")).strip()
                for row in rows
                if str(row.get("tag", "")).strip()
            )
        else:
            lines = [
                "\t".join(
                    [
                        "Tags",
                        "Occurrences in Listings",
                        "Percentage in Listings",
                        "Avg. Views per Tag",
                        "Avg. Likes per Tag",
                    ]
                )
            ]
            for row in rows:
                lines.append(
                    "\t".join(
                        [
                            str(row.get("tag", "")),
                            str(int(row.get("occurrences", 0))),
                            f"{float(row.get('percentage', 0.0)):.1f}",
                            f"{float(row.get('avg_views', 0.0)):.1f}",
                            f"{float(row.get('avg_likes', 0.0)):.1f}",
                        ]
                    )
                )
            text = "\n".join(lines)

        if not text.strip():
            QMessageBox.warning(self, "Analyze Video Tags", "No tag rows to copy.")
            return

        QApplication.clipboard().setText(text)
        self._set_status(f"Copied {len(rows)} tag row(s) to clipboard.")

    def _open_analyze_video_tags_file_menu(self, dialog):
        if dialog is None:
            return

        visible_rows = self._analyze_video_tags_visible_rows(dialog)
        all_rows = list(dialog._all_tag_rows)

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#ffffff; color:#111111; border:1px solid #cfcfcf; }"
            "QMenu::item { padding:6px 16px; }"
            "QMenu::item:selected { background:#f3d0d3; color:#111111; }"
        )

        act_export_visible_csv = menu.addAction("Export VISIBLE rows to CSV")
        act_export_all_csv = menu.addAction("Export ALL rows to CSV")
        act_export_visible_txt = menu.addAction("Export VISIBLE rows to TXT")
        act_export_all_txt = menu.addAction("Export ALL rows to TXT")
        menu.addSeparator()

        copy_menu = menu.addMenu("Copy")
        act_copy_visible_rows = copy_menu.addAction("Copy VISIBLE rows to clipboard")
        act_copy_all_rows = copy_menu.addAction("Copy ALL rows to clipboard")
        act_copy_visible_tags = copy_menu.addAction("Copy VISIBLE tags")
        act_copy_all_tags = copy_menu.addAction("Copy ALL tags")

        chosen = menu.exec(dialog.btn_file.mapToGlobal(dialog.btn_file.rect().bottomLeft()))
        if chosen is None:
            return

        if chosen == act_export_visible_csv:
            self._export_analyze_video_tags_rows(dialog, rows=visible_rows, as_txt=False)
        elif chosen == act_export_all_csv:
            self._export_analyze_video_tags_rows(dialog, rows=all_rows, as_txt=False)
        elif chosen == act_export_visible_txt:
            self._export_analyze_video_tags_rows(dialog, rows=visible_rows, as_txt=True)
        elif chosen == act_export_all_txt:
            self._export_analyze_video_tags_rows(dialog, rows=all_rows, as_txt=True)
        elif chosen == act_copy_visible_rows:
            self._copy_analyze_video_tags_rows_to_clipboard(dialog, rows=visible_rows, tags_only=False)
        elif chosen == act_copy_all_rows:
            self._copy_analyze_video_tags_rows_to_clipboard(dialog, rows=all_rows, tags_only=False)
        elif chosen == act_copy_visible_tags:
            self._copy_analyze_video_tags_rows_to_clipboard(dialog, rows=visible_rows, tags_only=True)
        elif chosen == act_copy_all_tags:
            self._copy_analyze_video_tags_rows_to_clipboard(dialog, rows=all_rows, tags_only=True)

    def _analyze_titles_visible_rows(self, dialog):
        if dialog is None:
            return []
        return list(dialog._filtered_rows(dialog._all_word_rows))

    def _export_analyze_titles_rows(self, dialog, rows=None, as_txt=False):
        if dialog is None:
            return
        rows = list(rows) if rows is not None else self._analyze_titles_visible_rows(dialog)
        if not rows:
            QMessageBox.warning(self, "Analyze Titles", "No title keyword rows to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Title Word Stats",
            "analyze_titles.txt" if as_txt else "analyze_titles.csv",
            "Text Files (*.txt)" if as_txt else "CSV Files (*.csv)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8-sig") as handle:
                if as_txt:
                    handle.write(
                        "Word Combination\tOccurrences in Titles\tPercentage in Titles\tAvg. Views\tAvg. Likes\tNumber of Words\n"
                    )
                else:
                    handle.write(
                        "Word Combination,Occurrences in Titles,Percentage in Titles,Avg. Views,Avg. Likes,Number of Words\n"
                    )
                for row in rows:
                    cells = [
                        str(row.get("phrase", "")),
                        str(int(row.get("occurrences", 0))),
                        f"{float(row.get('percentage', 0.0)):.1f}",
                        f"{float(row.get('avg_views', 0.0)):.1f}",
                        f"{float(row.get('avg_likes', 0.0)):.1f}",
                        str(int(row.get("word_count", 0))),
                    ]
                    if as_txt:
                        handle.write("\t".join(cells) + "\n")
                    else:
                        escaped = [cell.replace('"', '""') for cell in cells]
                        quoted = ['"' + cell + '"' for cell in escaped]
                        handle.write(",".join(quoted) + "\n")
        except Exception as exc:
            QMessageBox.warning(self, "Analyze Titles", f"Failed to export file:\n{exc}")
            return

        self._set_status(f"Exported {len(rows)} title keyword rows.")

    def _copy_analyze_titles_rows_to_clipboard(self, dialog, rows=None, words_only=False):
        if dialog is None:
            return
        rows = list(rows) if rows is not None else self._analyze_titles_visible_rows(dialog)
        if not rows:
            QMessageBox.warning(self, "Analyze Titles", "No title keyword rows to copy.")
            return

        if words_only:
            text = "\n".join(
                str(row.get("phrase", "")).strip()
                for row in rows
                if str(row.get("phrase", "")).strip()
            )
        else:
            lines = [
                "\t".join(
                    [
                        "Word Combination",
                        "Occurrences in Titles",
                        "Percentage in Titles",
                        "Avg. Views",
                        "Avg. Likes",
                        "Number of Words",
                    ]
                )
            ]
            for row in rows:
                lines.append(
                    "\t".join(
                        [
                            str(row.get("phrase", "")),
                            str(int(row.get("occurrences", 0))),
                            f"{float(row.get('percentage', 0.0)):.1f}",
                            f"{float(row.get('avg_views', 0.0)):.1f}",
                            f"{float(row.get('avg_likes', 0.0)):.1f}",
                            str(int(row.get("word_count", 0))),
                        ]
                    )
                )
            text = "\n".join(lines)

        if not text.strip():
            QMessageBox.warning(self, "Analyze Titles", "No title keyword rows to copy.")
            return

        QApplication.clipboard().setText(text)
        self._set_status(f"Copied {len(rows)} title keyword row(s) to clipboard.")

    def _open_analyze_titles_file_menu(self, dialog):
        if dialog is None:
            return

        visible_rows = self._analyze_titles_visible_rows(dialog)
        all_rows = list(dialog._all_word_rows)

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#ffffff; color:#111111; border:1px solid #cfcfcf; }"
            "QMenu::item { padding:6px 16px; }"
            "QMenu::item:selected { background:#f3d0d3; color:#111111; }"
        )

        act_export_visible_csv = menu.addAction("Export VISIBLE rows to CSV")
        act_export_all_csv = menu.addAction("Export ALL rows to CSV")
        act_export_visible_txt = menu.addAction("Export VISIBLE rows to TXT")
        act_export_all_txt = menu.addAction("Export ALL rows to TXT")
        menu.addSeparator()

        copy_menu = menu.addMenu("Copy")
        act_copy_visible_rows = copy_menu.addAction("Copy VISIBLE rows to clipboard")
        act_copy_all_rows = copy_menu.addAction("Copy ALL rows to clipboard")
        act_copy_visible_words = copy_menu.addAction("Copy VISIBLE word combinations")
        act_copy_all_words = copy_menu.addAction("Copy ALL word combinations")

        chosen = menu.exec(dialog.btn_file.mapToGlobal(dialog.btn_file.rect().bottomLeft()))
        if chosen is None:
            return

        if chosen == act_export_visible_csv:
            self._export_analyze_titles_rows(dialog, rows=visible_rows, as_txt=False)
        elif chosen == act_export_all_csv:
            self._export_analyze_titles_rows(dialog, rows=all_rows, as_txt=False)
        elif chosen == act_export_visible_txt:
            self._export_analyze_titles_rows(dialog, rows=visible_rows, as_txt=True)
        elif chosen == act_export_all_txt:
            self._export_analyze_titles_rows(dialog, rows=all_rows, as_txt=True)
        elif chosen == act_copy_visible_rows:
            self._copy_analyze_titles_rows_to_clipboard(dialog, rows=visible_rows, words_only=False)
        elif chosen == act_copy_all_rows:
            self._copy_analyze_titles_rows_to_clipboard(dialog, rows=all_rows, words_only=False)
        elif chosen == act_copy_visible_words:
            self._copy_analyze_titles_rows_to_clipboard(dialog, rows=visible_rows, words_only=True)
        elif chosen == act_copy_all_words:
            self._copy_analyze_titles_rows_to_clipboard(dialog, rows=all_rows, words_only=True)

    def _open_stop_words_file_menu(self, dialog):
        if dialog is None:
            return
        menu = QMenu(self)
        act_load = menu.addAction("Load TXT")
        act_save = menu.addAction("Save TXT")
        chosen = menu.exec(dialog.btn_file.mapToGlobal(dialog.btn_file.rect().bottomLeft()))
        if chosen == act_load:
            self._load_stop_words_from_txt(dialog)
        elif chosen == act_save:
            self._save_stop_words_to_txt(dialog)

    def _load_stop_words_from_txt(self, dialog):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Stop Words TXT",
            "",
            "Text Files (*.txt);;All Files (*.*)",
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8-sig") as handle:
                text_data = handle.read()
        except Exception:
            try:
                with open(file_path, "r", encoding="utf-8") as handle:
                    text_data = handle.read()
            except Exception as exc:
                QMessageBox.warning(self, "Stop Words", f"Failed to read file:\n{exc}")
                return

        dialog.text_words.setPlainText(str(text_data or "").strip())

    def _save_stop_words_to_txt(self, dialog):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Stop Words TXT",
            "stop_words.txt",
            "Text Files (*.txt);;All Files (*.*)",
        )
        if not file_path:
            return
        try:
            with open(file_path, "w", encoding="utf-8-sig") as handle:
                handle.write(dialog.text_words.toPlainText())
        except Exception as exc:
            QMessageBox.warning(self, "Stop Words", f"Failed to save file:\n{exc}")

    def _open_analyze_title_keywords_dialog(self):
        rows = self._collect_current_rows_for_title_analysis()
        if not rows:
            QMessageBox.warning(self, "Analyze Titles", "No videos available to analyze.")
            return

        dlg = AnalyzeVideoTitleKeywordsDialog(self, stop_words=self._title_analysis_stop_words)
        dlg.btn_generate.clicked.connect(lambda: self._generate_title_word_stats(dlg, rows))
        dlg.btn_stop_words.clicked.connect(lambda: self._open_stop_words_dialog(dlg))
        dlg.btn_file.clicked.connect(lambda: self._open_analyze_titles_file_menu(dlg))
        dlg.btn_clear_filters.clicked.connect(dlg.reset_filters)
        dlg.btn_clear.clicked.connect(dlg.clear_results)
        dlg.exec()

    def _open_stop_words_dialog(self, owner_dialog=None):
        current_words = (
            owner_dialog.stop_words()
            if owner_dialog is not None and hasattr(owner_dialog, "stop_words")
            else list(self._title_analysis_stop_words)
        )
        dlg = StopWordsDialog(self, stop_words=current_words)
        dlg.btn_file.clicked.connect(lambda: self._open_stop_words_file_menu(dlg))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        updated_words = dlg.stop_words()
        self._title_analysis_stop_words = list(updated_words)
        if owner_dialog is not None and hasattr(owner_dialog, "set_stop_words"):
            owner_dialog.set_stop_words(updated_words)

    def _open_browse_extract_dialog(self):
        dlg = BrowseAndExtractDialog(self)
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
            col_indices = list(range(2, self.videos_table.columnCount()))
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
        act_analyze_tags.triggered.connect(self._open_analyze_video_tags_dialog)
        act_analyze_keywords = videos_tool_menu.addAction("Analyze keywords in video titles")
        act_analyze_keywords.triggered.connect(self._open_analyze_title_keywords_dialog)

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
        if len(self._thumbnail_fallback_workers) >= self._max_thumbnail_fallback_workers:
            rows = self._thumbnail_pending_rows.get(req_url, [])
            for row in rows:
                if row < 0 or row >= self.videos_table.rowCount():
                    continue
                item = self.videos_table.item(row, 1)
                if item is None:
                    continue
                item.setText("N/A")
                item.setForeground(QColor("#666666"))
            self._cleanup_thumbnail_request(req_url)
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
            rows.append(self._row_payload(row))
        return rows

    def _collect_current_rows_for_tag_analysis(self):
        rows = []
        wanted_keys = {"Channel", "Tags", "View Count"}
        for row in range(self.videos_table.rowCount()):
            payload = self._row_payload(row)
            if not payload:
                continue
            rows.append({key: str(payload.get(key, "")).strip() for key in wanted_keys})
        return rows

    def _collect_current_rows_for_title_analysis(self):
        rows = []
        wanted_keys = {"Title", "View Count", "Likes"}
        for row in range(self.videos_table.rowCount()):
            payload = self._row_payload(row)
            if not payload:
                continue
            rows.append({key: str(payload.get(key, "")).strip() for key in wanted_keys})
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

    def closeEvent(self, event):
        for worker_name in (
            "_search_worker",
            "_trending_worker",
            "_import_worker",
            "_download_worker",
            "_metadata_worker",
        ):
            worker = getattr(self, worker_name, None)
            if worker is None:
                continue
            try:
                if worker.isRunning():
                    if hasattr(worker, "stop"):
                        worker.stop()
                    worker.wait(1200)
            except Exception:
                pass

        for worker in list(self._thumbnail_fallback_workers.values()):
            try:
                if worker is not None and worker.isRunning():
                    worker.requestInterruption()
                    worker.wait(500)
            except Exception:
                pass
        self._thumbnail_fallback_workers.clear()
        self._thumbnail_inflight.clear()
        self._thumbnail_pending_rows.clear()
        self._scrollbar_tune_timer.stop()
        self._status_flush_timer.stop()
        super().closeEvent(event)
