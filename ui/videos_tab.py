from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
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
import webbrowser
import re
from urllib.parse import parse_qs, urlparse

from core.videos_fetcher import ImportedLinksMetadataWorker, VideoSearchWorker


class VideosTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._mode = "search"
        self._checkbox_syncing = False
        self._search_worker = None
        self._import_worker = None
        self._invalid_import_count = 0
        self._invalid_import_rows = []
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
        self.btn_analyze.clicked.connect(lambda: self._show_coming_soon("Analyze"))

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
        self.btn_trending_videos = QPushButton("Trending Videos")
        self.btn_trending_videos.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_trending_videos.setStyleSheet(self._red_button_style)
        self.btn_trending_videos.clicked.connect(lambda: self._show_coming_soon("Trending Videos"))
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
        self.videos_table.verticalHeader().setVisible(False)
        self.videos_table.verticalHeader().setDefaultSectionSize(30)
        self.videos_table.itemChanged.connect(self._on_table_item_changed)
        self.videos_table.cellDoubleClicked.connect(self._on_table_cell_double_clicked)
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
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)

        self.videos_table.setColumnWidth(0, 26)
        self.videos_table.setColumnWidth(1, 58)
        self.videos_table.setColumnWidth(2, 100)
        self.videos_table.setColumnWidth(3, 210)
        self.videos_table.setColumnWidth(4, 76)
        self.videos_table.setColumnWidth(5, 120)
        self.videos_table.setColumnWidth(6, 250)
        self.videos_table.setColumnWidth(7, 320)

        v.addWidget(self.videos_table, stretch=1)

        slider_row = QHBoxLayout()
        slider_row.setContentsMargins(4, 0, 4, 0)
        slider_row.setSpacing(8)
        slider_label = QLabel("Image Size:")
        slider_label.setStyleSheet("QLabel { color:#f3f4f6; }")
        slider_row.addWidget(slider_label)
        self.slider_image_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_image_size.setRange(20, 80)
        self.slider_image_size.setValue(25)
        self.slider_image_size.valueChanged.connect(self._on_image_size_changed)
        self.lbl_image_size = QLabel("25 px")
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
        self.btn_filters.clicked.connect(lambda: self._show_coming_soon("Filters"))
        self.btn_clear.clicked.connect(self._clear_table_ui_only)

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
        self.videos_table.verticalHeader().setDefaultSectionSize(max(26, int(value) + 8))

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

    def _set_status(self, message):
        self.lbl_status.setText(message)
        if self.main_window is not None:
            self.main_window.statusBar().showMessage(message, 5000)

    def _set_search_running(self, running):
        self.btn_search.setEnabled(not running)
        self.btn_stop_search.setEnabled(running)

    def _set_import_running(self, running):
        self.btn_get_data.setEnabled(not running)
        self.btn_stop_import.setEnabled(running)

    def start_search(self):
        query = self.input_search_phrase.text().strip()
        if not query:
            QMessageBox.warning(self, "Videos Tool", "Please enter a search phrase first.")
            return

        if self._search_worker is not None and self._search_worker.isRunning():
            QMessageBox.information(self, "Videos Tool", "Search is already running.")
            return

        if not self.chk_youtube_first.isChecked():
            QMessageBox.information(
                self,
                "Videos Tool",
                "Step V3 currently uses YouTube source. Advanced multi-source will be added in the next step.",
            )

        target_pages = int(self.combo_pages.currentText() or "1")
        max_results = max(5, min(100, target_pages * 20))
        if self.chk_youtube_first.isChecked():
            max_results = min(max_results, 20)

        self._clear_table_ui_only()
        self._set_search_running(True)
        self._set_status(f"Searching '{query}'...")

        self._search_worker = VideoSearchWorker(query=query, max_results=max_results)
        self._search_worker.video_signal.connect(self._append_video_row)
        self._search_worker.status_signal.connect(self._set_status)
        self._search_worker.error_signal.connect(self._on_search_error)
        self._search_worker.finished_signal.connect(self._on_search_finished)
        self._search_worker.start()

    def stop_search(self):
        if self._search_worker is not None and self._search_worker.isRunning():
            self._search_worker.stop()
            self._set_status("Stopping search...")

    def stop_import(self):
        if self._import_worker is not None and self._import_worker.isRunning():
            self._import_worker.stop()
            self._set_status("Stopping import...")

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

        self._clear_table_ui_only()
        self._invalid_import_count = len(invalid_rows)
        self._invalid_import_rows = list(invalid_rows)
        self._set_import_running(True)
        self._set_status(f"Importing {len(parsed_rows)} links and fetching metadata...")

        self._import_worker = ImportedLinksMetadataWorker(parsed_rows)
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

    def _append_video_row(self, video):
        row = self.videos_table.rowCount()
        self.videos_table.insertRow(row)

        checkbox_item = QTableWidgetItem("")
        checkbox_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        checkbox_item.setCheckState(Qt.CheckState.Unchecked)
        self.videos_table.setItem(row, 0, checkbox_item)

        thumb_item = QTableWidgetItem("N/A")
        thumb_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_item.setForeground(QColor("#666666"))
        thumb_url = str(video.get("Thumbnail URL", "")).strip()
        if thumb_url:
            thumb_item.setText("IMG")
            thumb_item.setForeground(QColor("#1a73e8"))
            thumb_item.setToolTip(thumb_url)
        self.videos_table.setItem(row, 1, thumb_item)

        values = [
            video.get("Video ID", ""),
            video.get("Video Link", ""),
            video.get("Source", "YouTube"),
            video.get("Search Phrase", ""),
            video.get("Title", ""),
            video.get("Description", ""),
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
                    video_id = str(video.get("Video ID", "")).strip()
                    if video_id:
                        link_text = f"https://www.youtube.com/watch?v={video_id}"
                        item.setText(link_text)
                if link_text.startswith("http://") or link_text.startswith("https://"):
                    item.setForeground(QColor("#1a73e8"))
                    item.setToolTip(link_text)
            elif col_offset in (6, 7):
                item.setToolTip(str(text))
            self.videos_table.setItem(row, col_offset, item)

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

    def _show_coming_soon(self, feature_name):
        QMessageBox.information(self, "Videos Tool", f"{feature_name} will be implemented in the next step.")

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
