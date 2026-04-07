import html
import re
import tempfile
from pathlib import Path
from urllib.parse import quote_plus

from PyQt6.QtCore import Qt, QItemSelectionModel, QTimer
from PyQt6.QtGui import QColor, QDesktopServices, QFont, QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QMenu,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QHeaderView,
    QWidget,
    QProgressBar,
    QMessageBox,
    QApplication,
)

from PyQt6.QtCore import QUrl

from core.channels_fetcher import ChannelImportWorker, ChannelsSearchWorker, normalize_channel_input
from ui.videos_tab import BrowseAndExtractDialog
from utils.constants import TABLE_SCROLLBAR_STYLE

CHANNEL_NUMERIC_FILTER_COLUMNS = {
    8: "Total Videos",
    9: "Total Views",
    10: "Subscribers",
}


class ChannelsTab(QWidget):
    SEARCH_COLUMNS = [
        "",
        "Image",
        "Channel ID",
        "Channel Link",
        "Source",
        "Search Phrase",
        "Title",
        "Description",
        "Total Videos",
        "Total Views",
        "Subscribers",
        "Date Joined",
        "Country",
        "Keywords",
        "External Links",
    ]

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._current_mode = "search"
        self._search_worker = None
        self._import_worker = None
        self._search_enrich_worker = None
        self._rows_cache = []
        self._search_results_count = 0
        self._row_index_by_channel = {}
        self._active_filter = self._default_filter_state()
        self._numeric_filter_rules = {}
        self._checkbox_syncing = False
        self._thumbnail_cache = {}
        self._thumbnail_failed = set()
        self._thumbnail_inflight = set()
        self._operation_token = 0
        self._table_dirty = False
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        shell = QFrame()
        shell.setStyleSheet("QFrame { background:#111111; }")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        top_modes = QFrame()
        top_modes.setStyleSheet("QFrame { background:#111111; border-bottom:1px solid #2e2e2e; }")
        top_modes_layout = QHBoxLayout(top_modes)
        top_modes_layout.setContentsMargins(28, 18, 28, 14)
        top_modes_layout.setSpacing(10)

        self.btn_mode_search = QPushButton("Search")
        self.btn_mode_browse = QPushButton("Browse or Import")
        for btn in (self.btn_mode_search, self.btn_mode_browse):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(40)
        self.btn_mode_search.clicked.connect(lambda: self._set_mode("search"))
        self.btn_mode_browse.clicked.connect(lambda: self._set_mode("browse"))
        top_modes_layout.addWidget(self.btn_mode_search)
        top_modes_layout.addWidget(self.btn_mode_browse)
        top_modes_layout.addStretch()
        shell_layout.addWidget(top_modes)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(28, 20, 28, 24)
        content_row.setSpacing(18)

        self.left_panel = QFrame()
        self.left_panel.setObjectName("input_frame")
        self.left_panel.setMinimumWidth(255)
        self.left_panel.setMaximumWidth(255)
        self.left_panel.setStyleSheet("QFrame#input_frame { background:#1a1a1a; border:1px solid #333333; border-radius:8px; }")
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(12)

        self.search_panel = self._build_search_panel()
        self.browse_panel = self._build_browse_panel()
        left_layout.addWidget(self.search_panel)
        left_layout.addWidget(self.browse_panel)
        content_row.addWidget(self.left_panel, stretch=0)

        self.right_panel = QFrame()
        self.right_panel.setObjectName("input_frame")
        self.right_panel.setStyleSheet("QFrame#input_frame { background:#1a1a1a; border:1px solid #333333; border-radius:8px; }")
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(10)

        self.search_action_row = QHBoxLayout()
        self.search_action_row.setSpacing(12)
        self.search_action_row.addStretch()
        self.btn_top_stop = QPushButton("Stop")
        self.btn_top_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_top_stop.setMinimumHeight(28)
        self.btn_top_stop.setMinimumWidth(80)
        self.btn_top_stop.setEnabled(False)
        self.btn_top_stop.setStyleSheet(
            "QPushButton { background:#e24a22; color:#ffffff; border:none; border-radius:4px; padding:6px 12px; font-weight:700; }"
            "QPushButton:disabled { background:#6d3125; color:#f2c7bb; }"
        )
        self.search_progress = QProgressBar()
        self.search_progress.setRange(0, 100)
        self.search_progress.setValue(0)
        self.search_progress.setTextVisible(False)
        self.search_progress.setFixedHeight(20)
        self.search_progress.setStyleSheet(
            "QProgressBar { background:#dfe6f2; border:none; border-radius:6px; }"
            "QProgressBar::chunk { background:#4a90e2; border-radius:6px; }"
        )
        self.search_action_row.addWidget(self.btn_top_stop)
        self.search_action_row.addWidget(self.search_progress, stretch=1)
        right_layout.addLayout(self.search_action_row)

        self.channels_table = QTableWidget()
        self.channels_table.setColumnCount(len(self.SEARCH_COLUMNS))
        self.channels_table.setHorizontalHeaderLabels(self.SEARCH_COLUMNS)
        self.channels_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.channels_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.channels_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.channels_table.setAlternatingRowColors(False)
        self.channels_table.setWordWrap(False)
        self.channels_table.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.channels_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.channels_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.channels_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.channels_table.verticalHeader().setVisible(False)
        self.channels_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.channels_table.horizontalHeader().sectionClicked.connect(self._on_channels_header_clicked)
        self.channels_table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.channels_table.customContextMenuRequested.connect(self._open_channels_context_menu)
        self.channels_table.itemChanged.connect(self._on_table_item_changed)
        self.channels_table.setStyleSheet(
            "QTableWidget { background:#ffffff; color:#111111; gridline-color:#d7d7d7; border:1px solid #bfc5d0; }"
            "QTableWidget::item { background:#ffffff; color:#111111; }"
            "QTableWidget::item:selected { background:#fde4e7; color:#111111; }"
            "QHeaderView::section { background:#f2f2f2; color:#111111; padding:6px; border:1px solid #d7d7d7; font-weight:700; }"
            + TABLE_SCROLLBAR_STYLE
        )
        self._thumbnail_manager = QNetworkAccessManager(self)
        self._thumbnail_manager.finished.connect(self._on_thumbnail_finished)
        self._rebuild_timer = QTimer(self)
        self._rebuild_timer.setSingleShot(True)
        self._rebuild_timer.setInterval(40)
        self._rebuild_timer.timeout.connect(self._flush_rebuild)
        right_layout.addWidget(self.channels_table, stretch=1)

        slider_row = QHBoxLayout()
        slider_row.setSpacing(10)
        self.lbl_image_size = QLabel("Image Size:")
        self.lbl_image_size.setStyleSheet("color:#d8d8d8;")
        self.slider_image_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_image_size.setRange(25, 120)
        self.slider_image_size.setValue(25)
        self.slider_image_size.valueChanged.connect(self._on_image_size_changed)
        self.slider_image_size.setStyleSheet(
            "QSlider::groove:horizontal { height:6px; background:#cfd7e5; border-radius:3px; }"
            "QSlider::handle:horizontal { width:14px; margin:-4px 0; border-radius:7px; background:#d94a2b; }"
        )
        self.lbl_image_value = QLabel("25 px")
        self.lbl_image_value.setStyleSheet("color:#d8d8d8; min-width:48px;")
        slider_row.addWidget(self.lbl_image_size)
        slider_row.addWidget(self.slider_image_size, stretch=1)
        slider_row.addWidget(self.lbl_image_value)
        right_layout.addLayout(slider_row)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)
        self.lbl_total_items = QLabel("Total Items: 0")
        self.lbl_status = QLabel("Ready.")
        for lbl in (self.lbl_total_items, self.lbl_status):
            lbl.setStyleSheet("color:#f0f0f0; font-size:13px;")
        bottom_row.addWidget(self.lbl_total_items)
        bottom_row.addStretch()
        bottom_row.addWidget(self.lbl_status)
        bottom_row.addStretch()
        self.btn_file = QPushButton("File")
        self.btn_filters = QPushButton("Filters")
        self.btn_clear = QPushButton("Clear")
        for btn in (self.btn_file, self.btn_filters, self.btn_clear):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(34)
            btn.setStyleSheet(
                "QPushButton { background:#e50914; color:#ffffff; border:none; border-radius:5px; padding:6px 18px; font-weight:700; }"
                "QPushButton:hover { background:#ff1a25; }"
            )
        bottom_row.addWidget(self.btn_file)
        bottom_row.addWidget(self.btn_filters)
        bottom_row.addWidget(self.btn_clear)
        self.btn_file.clicked.connect(self._open_file_menu)
        self.btn_filters.clicked.connect(self._open_filters_menu)
        self.btn_clear.clicked.connect(self._clear_table)
        right_layout.addLayout(bottom_row)

        content_row.addWidget(self.right_panel, stretch=1)
        shell_layout.addLayout(content_row)
        root.addWidget(shell)

        self._apply_table_widths()
        self._on_image_size_changed(self.slider_image_size.value())
        self._set_mode("search")

    def _build_search_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(self._make_label("Search Phrase:"))
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search phrase")
        self.search_input.setMinimumHeight(34)
        self.search_input.setStyleSheet(
            "QLineEdit { background:#ffffff; color:#111111; border:1px solid #c7c7c7; border-radius:3px; padding:6px 8px; }"
        )
        self.btn_search = QPushButton("Search")
        self.btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_search.setMinimumHeight(34)
        self.btn_search.setMinimumWidth(84)
        self.btn_search.setStyleSheet(
            "QPushButton { background:#e50914; color:#ffffff; border:none; border-radius:5px; padding:6px 14px; font-weight:700; }"
            "QPushButton:hover { background:#ff1a25; }"
        )
        self.btn_search.clicked.connect(self.start_search)
        search_row.addWidget(self.search_input, stretch=1)
        search_row.addWidget(self.btn_search)
        layout.addLayout(search_row)

        self.chk_youtube_first_page = QCheckBox("Youtube (first page results only)")
        self.chk_youtube_first_page.setChecked(True)
        self.chk_youtube_first_page.setStyleSheet("QCheckBox { color:#f0f0f0; }")
        layout.addWidget(self.chk_youtube_first_page)

        row_sort = QHBoxLayout()
        row_sort.setSpacing(8)
        lbl_sort = self._make_label("Sort Youtube results by:")
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Relevance", "Date", "View count", "Rating"])
        self.sort_combo.setMinimumHeight(32)
        self.sort_combo.setStyleSheet(
            "QComboBox { background:#ffffff; color:#111111; border:1px solid #c7c7c7; border-radius:3px; padding:4px 8px; }"
        )
        row_sort.addWidget(lbl_sort)
        row_sort.addWidget(self.sort_combo, stretch=1)
        layout.addLayout(row_sort)

        row_sources = QHBoxLayout()
        row_sources.setSpacing(10)
        self.chk_google = QCheckBox("Google")
        self.chk_bing = QCheckBox("Bing")
        self.chk_google.setChecked(True)
        self.chk_bing.setChecked(True)
        for chk in (self.chk_google, self.chk_bing):
            chk.setStyleSheet("QCheckBox { color:#f0f0f0; }")
            row_sources.addWidget(chk)
        row_sources.addStretch()
        row_sources.addWidget(self._make_label("Pages:"))
        self.pages_spin = QSpinBox()
        self.pages_spin.setRange(1, 50)
        self.pages_spin.setValue(1)
        self.pages_spin.setMinimumHeight(32)
        self.pages_spin.setStyleSheet(
            "QSpinBox { background:#ffffff; color:#111111; border:1px solid #c7c7c7; border-radius:3px; padding:4px 6px; }"
        )
        row_sources.addWidget(self.pages_spin)
        layout.addLayout(row_sources)
        layout.addStretch()
        return panel

    def _build_browse_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.btn_browse_analyze = QPushButton("Analyze")
        self.btn_browse_analyze.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse_analyze.setMinimumHeight(36)
        self.btn_browse_analyze.setStyleSheet(
            "QPushButton { background:#e50914; color:#ffffff; border:none; border-radius:5px; padding:6px 14px; font-weight:700; }"
            "QPushButton:hover { background:#ff1a25; }"
        )
        self.btn_browse_analyze.clicked.connect(self.start_import_analysis)
        layout.addWidget(self.btn_browse_analyze)

        layout.addWidget(self._make_label("Extract channel links by:"))
        methods = QHBoxLayout()
        methods.setSpacing(8)
        self.btn_browser = QPushButton("Browser")
        self.btn_content = QPushButton("Content")
        for btn in (self.btn_browser, self.btn_content):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(34)
            btn.setStyleSheet(
                "QPushButton { background:#e50914; color:#ffffff; border:none; border-radius:5px; padding:6px 12px; font-weight:700; }"
                "QPushButton:hover { background:#ff1a25; }"
            )
            methods.addWidget(btn)
        self.btn_browser.clicked.connect(self._open_browse_extract_dialog)
        self.btn_content.clicked.connect(lambda: QMessageBox.information(self, "Channels", "Content extract will be implemented in the next step."))
        layout.addLayout(methods)

        layout.addWidget(self._make_label("Youtube channel links: ( one per line )"))
        self.import_links_input = QTextEdit()
        self.import_links_input.setMinimumHeight(280)
        self.import_links_input.setStyleSheet(
            "QTextEdit { background:#ffffff; color:#111111; border:1px solid #c7c7c7; border-radius:3px; padding:6px 8px; }"
        )
        self.import_links_input.textChanged.connect(
            lambda: self.lbl_browse_total.setText(
                f"Total: {len([line for line in self.import_links_input.toPlainText().splitlines() if line.strip()])}"
            )
        )
        layout.addWidget(self.import_links_input)

        footer = QHBoxLayout()
        self.lbl_browse_total = QLabel("Total: 0")
        self.lbl_browse_total.setStyleSheet("color:#f0f0f0; font-size:13px;")
        self.btn_browse_file = QPushButton("File")
        self.btn_browse_clear = QPushButton("Clear")
        for btn in (self.btn_browse_file, self.btn_browse_clear):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(30)
            btn.setStyleSheet(
                "QPushButton { background:#e50914; color:#ffffff; border:none; border-radius:4px; padding:5px 12px; font-weight:700; }"
                "QPushButton:hover { background:#ff1a25; }"
            )
        footer.addWidget(self.lbl_browse_total)
        footer.addStretch()
        footer.addWidget(self.btn_browse_file)
        footer.addWidget(self.btn_browse_clear)
        self.btn_browse_file.clicked.connect(self._open_browse_file_menu)
        self.btn_browse_clear.clicked.connect(self.import_links_input.clear)
        layout.addLayout(footer)
        return panel

    def _make_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#f0f0f0; font-size:13px;")
        return lbl

    def _apply_table_widths(self):
        widths = {
            0: 28,
            1: 58,
            2: 180,
            3: 210,
            4: 100,
            5: 110,
            6: 190,
            7: 260,
            8: 96,
            9: 110,
            10: 110,
            11: 110,
            12: 110,
            13: 210,
            14: 240,
        }
        for col, width in widths.items():
            self.channels_table.setColumnWidth(col, width)

    def _auto_fit_column_widths(self):
        max_widths = {
            0: 36,
            1: 70,
            2: 240,
            3: 320,
            4: 120,
            5: 130,
            6: 280,
            7: 420,
            8: 120,
            9: 150,
            10: 150,
            11: 150,
            12: 150,
            13: 320,
            14: 360,
        }
        self.channels_table.resizeColumnsToContents()
        for col in range(self.channels_table.columnCount()):
            current = self.channels_table.columnWidth(col)
            limit = max_widths.get(col, 260)
            self.channels_table.setColumnWidth(col, min(current + 16, limit))
        self._set_status("Auto-fit column widths applied.")

    def _reset_column_widths(self):
        self._apply_table_widths()
        self._set_status("Column widths reset.")

    def _set_mode(self, mode):
        self._current_mode = "browse" if mode == "browse" else "search"
        is_search = self._current_mode == "search"
        self.search_panel.setVisible(is_search)
        self.browse_panel.setVisible(not is_search)
        self.lbl_image_size.setVisible(is_search)
        self.slider_image_size.setVisible(is_search)
        self.lbl_image_value.setVisible(is_search)
        self._set_top_search_controls_visible(is_search)
        self._apply_mode_columns()
        self._apply_mode_button_styles()

    def _set_top_search_controls_visible(self, visible):
        self.btn_top_stop.setVisible(visible)
        self.search_progress.setVisible(visible)

    def _apply_mode_button_styles(self):
        active = (
            "QPushButton { background:#e50914; color:#ffffff; border:none; border-radius:5px; padding:8px 18px; font-weight:700; }"
            "QPushButton:hover { background:#ff1a25; }"
        )
        inactive = (
            "QPushButton { background:#2a2a2a; color:#f0f0f0; border:1px solid #4a4a4a; border-radius:5px; padding:8px 18px; font-weight:600; }"
        )
        self.btn_mode_search.setStyleSheet(active if self._current_mode == "search" else inactive)
        self.btn_mode_browse.setStyleSheet(active if self._current_mode == "browse" else inactive)

    def _apply_mode_columns(self):
        visible = set(range(self.channels_table.columnCount()))
        if self._current_mode == "browse":
            visible.discard(5)  # Hide "Search Phrase" in Browse or Import mode.
        for col in range(self.channels_table.columnCount()):
            self.channels_table.setColumnHidden(col, col not in visible)

    def _set_status(self, text):
        self.lbl_status.setText(str(text or "").strip() or "Ready.")

    def _ensure_table_synced(self):
        if self._table_dirty:
            self._flush_rebuild()

    def _default_filter_state(self):
        return {
            "title_contains": "",
            "search_phrase_contains": "",
            "country_contains": "",
            "source_equals": "",
            "has_external_links": False,
            "has_keywords": False,
        }

    def _set_running_state(self, running, context="search"):
        is_running = bool(running)
        self.btn_top_stop.setEnabled(is_running)
        self.btn_search.setEnabled(not is_running)
        self.search_input.setReadOnly(is_running)
        self.chk_youtube_first_page.setEnabled(not is_running)
        self.chk_google.setEnabled(not is_running)
        self.chk_bing.setEnabled(not is_running)
        self.pages_spin.setEnabled(not is_running)
        self.sort_combo.setEnabled(not is_running)
        self.btn_browse_analyze.setEnabled(not is_running)
        self.import_links_input.setReadOnly(is_running)
        self.btn_browser.setEnabled(not is_running)
        self.btn_content.setEnabled(not is_running)
        self.btn_browse_file.setEnabled(not is_running)
        self.btn_browse_clear.setEnabled(not is_running)
        if not is_running:
            self.search_progress.setValue(0)
        try:
            self.btn_top_stop.clicked.disconnect()
        except Exception:
            pass
        if is_running:
            if context in {"search", "search_enrich"}:
                self.btn_top_stop.clicked.connect(self.stop_search)
            else:
                self.btn_top_stop.clicked.connect(self.stop_import_analysis)

    def _next_operation_token(self):
        self._operation_token += 1
        return self._operation_token

    def _is_current_operation(self, token):
        return token == self._operation_token

    def _stop_all_workers(self):
        for worker in (self._search_worker, self._search_enrich_worker, self._import_worker):
            try:
                if worker is not None and worker.isRunning():
                    worker.stop()
            except Exception:
                pass

    def _schedule_rebuild(self):
        self._table_dirty = True
        if not self._rebuild_timer.isActive():
            self._rebuild_timer.start()

    def _flush_rebuild(self):
        if not self._table_dirty:
            return
        self._table_dirty = False
        self._rebuild_table_from_cache()

    def _clear_table(self, invalidate_running=True, stop_workers=True):
        if stop_workers:
            self._stop_all_workers()
        if invalidate_running:
            self._next_operation_token()
        self._rebuild_timer.stop()
        self._table_dirty = False
        self._checkbox_syncing = True
        self.channels_table.setUpdatesEnabled(False)
        self.channels_table.setRowCount(0)
        self.channels_table.setUpdatesEnabled(True)
        self._checkbox_syncing = False
        self._rows_cache = []
        self._search_results_count = 0
        self._row_index_by_channel = {}
        self._active_filter = self._default_filter_state()
        self._numeric_filter_rules = {}
        self._thumbnail_inflight.clear()
        self._set_running_state(False, context=self._current_mode)
        self.lbl_total_items.setText("Total Items: 0")
        self._set_status("Cleared.")

    def _fill_row_items(self, row, payload):
        ordered = [
            payload.get("Channel ID", ""),
            payload.get("Channel Link", payload.get("input", "")),
            payload.get("Source", "youtube"),
            payload.get("Search Phrase", ""),
            payload.get("Title", ""),
            payload.get("Description", ""),
            payload.get("Total Videos", "not-given"),
            payload.get("Total Views", "not-given"),
            payload.get("Subscribers", "not-given"),
            payload.get("Date Joined", "not-given"),
            payload.get("Country", "not-given"),
            payload.get("Keywords", "not-given"),
            payload.get("External Links", "not-given"),
        ]
        for col, value in enumerate(ordered, start=2):
            item = QTableWidgetItem(str(value or ""))
            if col in {3, 14} and str(value or "").strip() not in {"", "not-given"}:
                item.setForeground(QColor("#1a73e8"))
                item.setToolTip(str(value))
            self.channels_table.setItem(row, col, item)

    def _channel_keys(self, payload):
        data = dict(payload or {})
        keys = []
        channel_id = str(data.get("Channel ID", "")).strip().lower()
        if channel_id and channel_id not in {"not-given", "n/a"}:
            keys.append(f"id:{channel_id}")
        for raw_link in (
            str(data.get("Channel Link", "")).strip(),
            str(data.get("input", "")).strip(),
        ):
            if not raw_link:
                continue
            normalized = normalize_channel_input(raw_link)
            if normalized and normalized.get("channel_url"):
                keys.append(f"url:{normalized['channel_url'].lower()}")
            else:
                keys.append(f"url:{raw_link.lower()}")
        seen = set()
        ordered = []
        for key in keys:
            if not key or key in seen:
                continue
            seen.add(key)
            ordered.append(key)
        return ordered

    def _channel_key(self, payload):
        keys = self._channel_keys(payload)
        return keys[0] if keys else ""

    def _create_checkbox_item(self):
        checkbox_item = QTableWidgetItem("")
        checkbox_item.setFlags(
            Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        )
        return checkbox_item

    def _create_thumb_item(self, payload):
        thumb_item = QTableWidgetItem("...")
        thumb_url = str(payload.get("Thumbnail URL", "")).strip()
        if thumb_url and thumb_url in self._thumbnail_cache:
            pix = self._thumbnail_cache.get(thumb_url)
            if pix is not None and not pix.isNull():
                thumb = pix.scaled(
                    self._thumbnail_size_px(),
                    self._thumbnail_size_px(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                thumb_item.setData(Qt.ItemDataRole.DecorationRole, thumb)
                thumb_item.setText("")
                thumb_item.setToolTip(thumb_url)
                return thumb_item
        if thumb_url:
            thumb_item.setForeground(QColor("#1a73e8"))
            thumb_item.setToolTip(thumb_url)
        else:
            thumb_item.setText("N/A")
            thumb_item.setForeground(QColor("#666666"))
        return thumb_item

    def _render_rows(self, rows):
        self._checkbox_syncing = True
        self.channels_table.setUpdatesEnabled(False)
        self.channels_table.setRowCount(0)
        for payload in rows:
            row = self.channels_table.rowCount()
            self.channels_table.insertRow(row)
            checkbox_item = self._create_checkbox_item()
            checkbox_item.setCheckState(Qt.CheckState.Checked if payload.get("_checked", False) else Qt.CheckState.Unchecked)
            self.channels_table.setItem(row, 0, checkbox_item)
            self.channels_table.setItem(row, 1, self._create_thumb_item(payload))
            self._fill_row_items(row, payload)
            thumb_url = str(payload.get("Thumbnail URL", "")).strip()
            if thumb_url:
                self._queue_thumbnail_load(row, thumb_url)
        self.channels_table.setUpdatesEnabled(True)
        self._checkbox_syncing = False
        self.lbl_total_items.setText(f"Total Items: {len(rows)}")
        self._refresh_visible_thumbnails()

    def _row_matches_filter(self, payload):
        data = dict(payload or {})
        title = str(data.get("Title", "")).lower()
        search_phrase = str(data.get("Search Phrase", "")).lower()
        country = str(data.get("Country", "")).lower()
        source = str(data.get("Source", "")).lower()
        ext = str(data.get("External Links", "")).strip().lower()
        keywords = str(data.get("Keywords", "")).strip().lower()

        flt = self._active_filter
        if flt["title_contains"] and flt["title_contains"] not in title:
            return False
        if flt["search_phrase_contains"] and flt["search_phrase_contains"] not in search_phrase:
            return False
        if flt["country_contains"] and flt["country_contains"] not in country:
            return False
        if flt["source_equals"] and flt["source_equals"] != source:
            return False
        if flt["has_external_links"] and ext in {"", "not-given"}:
            return False
        if flt["has_keywords"] and keywords in {"", "not-given"}:
            return False
        if self._numeric_filter_rules:
            for column, expression in self._numeric_filter_rules.items():
                key = CHANNEL_NUMERIC_FILTER_COLUMNS.get(column, "")
                if not key:
                    continue
                parsed_value = self._parse_numeric_value(data.get(key, ""))
                if parsed_value is None or self._evaluate_numeric_rule(parsed_value, expression) is not True:
                    return False
        return True

    def _filtered_rows(self):
        return [row for row in self._rows_cache if self._row_matches_filter(row)]

    def _rebuild_table_from_cache(self):
        try:
            selected_rows = self._selected_display_rows()
        except Exception:
            selected_rows = []
        selected_keys = set()
        for row in selected_rows:
            selected_keys.update(self._channel_keys(row))
        self._render_rows(self._filtered_rows())
        if not selected_keys:
            return
        model = self.channels_table.selectionModel()
        if model is None:
            return
        self.channels_table.clearSelection()
        filtered_rows = self._filtered_rows()
        for row_index, row in enumerate(filtered_rows):
            row_keys = set(self._channel_keys(row))
            if not row_keys.intersection(selected_keys):
                continue
            model.select(
                self.channels_table.model().index(row_index, 0),
                QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
            )

    def _append_row(self, row_dict, token=None):
        if token is not None and not self._is_current_operation(token):
            return
        payload = dict(row_dict or {})
        cache_index = len(self._rows_cache)
        self._rows_cache.append(payload)
        for row_key in self._channel_keys(payload):
            self._row_index_by_channel[row_key] = cache_index
        self._schedule_rebuild()

    def _append_search_result(self, row_dict, token=None):
        if token is not None and not self._is_current_operation(token):
            return
        payload = dict(row_dict or {})
        cache_index = len(self._rows_cache)
        self._rows_cache.append(payload)
        self._search_results_count += 1
        for row_key in self._channel_keys(payload):
            self._row_index_by_channel[row_key] = cache_index
        self._schedule_rebuild()

    def _update_search_row(self, row_dict, token=None):
        if token is not None and not self._is_current_operation(token):
            return
        payload = dict(row_dict or {})
        cache_index = None
        for row_key in self._channel_keys(payload):
            cache_index = self._row_index_by_channel.get(row_key)
            if cache_index is not None:
                break
        if cache_index is None or not (0 <= cache_index < len(self._rows_cache)):
            return
        merged = dict(self._rows_cache[cache_index])
        for key, value in payload.items():
            text = str(value or "").strip()
            if text and text not in {"not-given", "..."}:
                merged[key] = value
        self._rows_cache[cache_index] = merged
        for row_key in self._channel_keys(merged):
            self._row_index_by_channel[row_key] = cache_index
        self._schedule_rebuild()

    def _open_file_menu(self):
        self._ensure_table_synced()
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
        act_copy_visible_links = copy_menu.addAction("Copy VISIBLE channel links")
        act_copy_all_links = copy_menu.addAction("Copy ALL channel links")
        chosen = menu.exec(self.btn_file.mapToGlobal(self.btn_file.rect().bottomLeft()))
        if chosen is None:
            return
        visible_rows = self._filtered_rows()
        all_rows = list(self._rows_cache)
        if chosen == act_export_visible_csv:
            self._export_rows(visible_rows, as_txt=False)
        elif chosen == act_export_all_csv:
            self._export_rows(all_rows, as_txt=False)
        elif chosen == act_export_visible_txt:
            self._export_rows(visible_rows, as_txt=True)
        elif chosen == act_export_all_txt:
            self._export_rows(all_rows, as_txt=True)
        elif chosen == act_copy_visible_rows:
            self._copy_rows_to_clipboard(visible_rows)
        elif chosen == act_copy_all_rows:
            self._copy_rows_to_clipboard(all_rows)
        elif chosen == act_copy_visible_links:
            self._copy_channel_links_to_clipboard(visible_rows)
        elif chosen == act_copy_all_links:
            self._copy_channel_links_to_clipboard(all_rows)

    def _open_filters_menu(self):
        self._ensure_table_synced()
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#ffffff; color:#111111; border:1px solid #cfcfcf; }"
            "QMenu::item { padding:6px 16px; }"
            "QMenu::item:selected { background:#f3d0d3; color:#111111; }"
        )
        act_title = menu.addAction("Title contains...")
        act_search_phrase = menu.addAction("Search phrase contains...")
        act_country = menu.addAction("Country contains...")
        act_source = menu.addAction("Source equals...")
        menu.addSeparator()
        act_toggle_links = menu.addAction("Toggle Has External Links")
        act_toggle_keywords = menu.addAction("Toggle Has Keywords")
        menu.addSeparator()
        act_reset = menu.addAction("Reset Filters")
        chosen = menu.exec(self.btn_filters.mapToGlobal(self.btn_filters.rect().bottomLeft()))
        if chosen is None:
            return
        if chosen == act_title:
            self._set_text_filter("title_contains", "Title contains", self._active_filter["title_contains"])
        elif chosen == act_search_phrase:
            self._set_text_filter("search_phrase_contains", "Search phrase contains", self._active_filter["search_phrase_contains"])
        elif chosen == act_country:
            self._set_text_filter("country_contains", "Country contains", self._active_filter["country_contains"])
        elif chosen == act_source:
            self._set_text_filter("source_equals", "Source equals", self._active_filter["source_equals"])
        elif chosen == act_toggle_links:
            self._active_filter["has_external_links"] = not self._active_filter["has_external_links"]
            self._apply_filters_status()
        elif chosen == act_toggle_keywords:
            self._active_filter["has_keywords"] = not self._active_filter["has_keywords"]
            self._apply_filters_status()
        elif chosen == act_reset:
            self._active_filter = self._default_filter_state()
            self._apply_filters_status()

    def _apply_filters_menu_choice(self, chosen, actions):
        if chosen is None:
            return
        if chosen == actions["title"]:
            self._set_text_filter("title_contains", "Title contains", self._active_filter["title_contains"])
        elif chosen == actions["search_phrase"]:
            self._set_text_filter(
                "search_phrase_contains",
                "Search phrase contains",
                self._active_filter["search_phrase_contains"],
            )
        elif chosen == actions["country"]:
            self._set_text_filter("country_contains", "Country contains", self._active_filter["country_contains"])
        elif chosen == actions["source"]:
            self._set_text_filter("source_equals", "Source equals", self._active_filter["source_equals"])
        elif chosen == actions["toggle_links"]:
            self._active_filter["has_external_links"] = not self._active_filter["has_external_links"]
            self._apply_filters_status()
        elif chosen == actions["toggle_keywords"]:
            self._active_filter["has_keywords"] = not self._active_filter["has_keywords"]
            self._apply_filters_status()
        elif chosen == actions["reset"]:
            self._active_filter = self._default_filter_state()
            self._apply_filters_status()

    def _build_filters_menu(self, menu):
        act_title = menu.addAction("Title contains...")
        act_search_phrase = menu.addAction("Search phrase contains...")
        act_country = menu.addAction("Country contains...")
        act_source = menu.addAction("Source equals...")
        menu.addSeparator()
        act_toggle_links = menu.addAction("Toggle Has External Links")
        act_toggle_keywords = menu.addAction("Toggle Has Keywords")
        menu.addSeparator()
        act_reset = menu.addAction("Reset Filters")
        return {
            "title": act_title,
            "search_phrase": act_search_phrase,
            "country": act_country,
            "source": act_source,
            "toggle_links": act_toggle_links,
            "toggle_keywords": act_toggle_keywords,
            "reset": act_reset,
        }

    def _set_text_filter(self, key, title, current):
        text, ok = QInputDialog.getText(self, "Channels Filters", f"{title}:", text=str(current or ""))
        if not ok:
            return
        self._active_filter[key] = str(text or "").strip().lower()
        self._apply_filters_status()

    def _apply_filters_status(self):
        self._rebuild_table_from_cache()
        visible = len(self._filtered_rows())
        total = len(self._rows_cache)
        active_bits = []
        if self._active_filter["title_contains"]:
            active_bits.append(f"title~{self._active_filter['title_contains']}")
        if self._active_filter["search_phrase_contains"]:
            active_bits.append(f"search~{self._active_filter['search_phrase_contains']}")
        if self._active_filter["country_contains"]:
            active_bits.append(f"country~{self._active_filter['country_contains']}")
        if self._active_filter["source_equals"]:
            active_bits.append(f"source={self._active_filter['source_equals']}")
        if self._active_filter["has_external_links"]:
            active_bits.append("has links")
        if self._active_filter["has_keywords"]:
            active_bits.append("has keywords")
        for column, expression in sorted(self._numeric_filter_rules.items()):
            label = CHANNEL_NUMERIC_FILTER_COLUMNS.get(column, f"col{column}")
            active_bits.append(f"{label}{expression}")
        if active_bits:
            self._set_status(f"Filter applied: {visible} / {total} rows | " + ", ".join(active_bits))
        else:
            self._set_status(f"Filter cleared. Showing {visible} row(s).")

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
    def _evaluate_numeric_rule(value, expression):
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

    def _set_numeric_filter_dialog(self, column):
        column_name = CHANNEL_NUMERIC_FILTER_COLUMNS.get(column, f"Column {column}")
        current = str(self._numeric_filter_rules.get(column, "")).strip()
        text, ok = QInputDialog.getText(
            self,
            f"Filter {column_name}",
            f"{column_name} condition:\nExamples: >10, >=100, <5, =0, !=2",
            text=current,
        )
        if not ok:
            return
        expr = str(text or "").strip()
        if not expr:
            self._numeric_filter_rules.pop(column, None)
            self._apply_filters_status()
            return
        if self._evaluate_numeric_rule(1.0, expr) is None:
            QMessageBox.warning(
                self,
                "Filter",
                "Numeric filter format is invalid. Use examples like >10, >=100, <5, =0.",
            )
            return
        self._numeric_filter_rules[column] = expr
        self._apply_filters_status()

    def _on_channels_header_clicked(self, column):
        if column in CHANNEL_NUMERIC_FILTER_COLUMNS:
            self._set_numeric_filter_dialog(column)

    def _thumbnail_size_px(self):
        return max(25, int(self.slider_image_size.value()))

    def _on_image_size_changed(self, value):
        size_px = max(25, int(value))
        self.lbl_image_value.setText(f"{size_px} px")
        self.channels_table.verticalHeader().setDefaultSectionSize(size_px + 10)
        self.channels_table.setColumnWidth(1, max(58, size_px + 18))
        self._refresh_visible_thumbnails()

    def _queue_thumbnail_load(self, row, thumb_url):
        if not thumb_url:
            return
        if thumb_url in self._thumbnail_cache:
            self._apply_thumbnail_to_row(row, thumb_url)
            return
        if thumb_url in self._thumbnail_failed:
            return
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
            pix = QPixmap()
            if not reply.error():
                data = reply.readAll()
                pix.loadFromData(bytes(data))
            if not pix.isNull():
                self._thumbnail_cache[req_url] = pix
            else:
                self._thumbnail_failed.add(req_url)
            self._thumbnail_inflight.discard(req_url)
            self._refresh_visible_thumbnails()
        finally:
            reply.deleteLater()

    def _apply_thumbnail_to_row(self, row, thumb_url):
        if row < 0 or row >= self.channels_table.rowCount():
            return
        pix = self._thumbnail_cache.get(thumb_url)
        if pix is None or pix.isNull():
            return
        item = self.channels_table.item(row, 1)
        if item is None:
            return
        thumb = pix.scaled(
            self._thumbnail_size_px(),
            self._thumbnail_size_px(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        item.setData(Qt.ItemDataRole.DecorationRole, thumb)
        item.setText("")
        item.setToolTip(thumb_url)

    def _refresh_visible_thumbnails(self):
        for row in range(self.channels_table.rowCount()):
            item = self.channels_table.item(row, 1)
            if item is None:
                continue
            thumb_url = item.toolTip().strip()
            if thumb_url and thumb_url in self._thumbnail_cache:
                self._apply_thumbnail_to_row(row, thumb_url)
            elif thumb_url and thumb_url in self._thumbnail_failed:
                item.setData(Qt.ItemDataRole.DecorationRole, None)
                item.setText("N/A")
                item.setForeground(QColor("#666666"))

    def _serialize_rows(self, rows, as_txt=False):
        headers = self.SEARCH_COLUMNS[1:]
        lines = []
        if not as_txt:
            lines.append(",".join(f'"{header}"' for header in headers))
        for row in rows:
            values = [
                str(row.get("Thumbnail URL", "")),
                str(row.get("Channel ID", "")),
                str(row.get("Channel Link", row.get("input", ""))),
                str(row.get("Source", "")),
                str(row.get("Search Phrase", "")),
                str(row.get("Title", "")),
                str(row.get("Description", "")),
                str(row.get("Total Videos", "not-given")),
                str(row.get("Total Views", "not-given")),
                str(row.get("Subscribers", "not-given")),
                str(row.get("Date Joined", "not-given")),
                str(row.get("Country", "not-given")),
                str(row.get("Keywords", "not-given")),
                str(row.get("External Links", "not-given")),
            ]
            if as_txt:
                lines.append("\t".join(values))
            else:
                escaped = [f'"{value.replace("\"", "\"\"")}"' for value in values]
                lines.append(",".join(escaped))
        return "\n".join(lines)

    def _export_rows(self, rows, as_txt=False):
        if not rows:
            QMessageBox.information(self, "Channels", "There are no rows to export.")
            return
        suffix = "txt" if as_txt else "csv"
        filter_name = "TXT Files (*.txt)" if as_txt else "CSV Files (*.csv)"
        path, _ = QFileDialog.getSaveFileName(self, "Export Channels", f"channels_export.{suffix}", filter_name)
        if not path:
            return
        content = self._serialize_rows(rows, as_txt=as_txt)
        with open(path, "w", encoding="utf-8-sig") as fh:
            fh.write(content)
        self._set_status(f"Exported {len(rows)} row(s) to {path}.")

    def _copy_rows_to_clipboard(self, rows):
        if not rows:
            QMessageBox.information(self, "Channels", "There are no rows to copy.")
            return
        QApplication.clipboard().setText(self._serialize_rows(rows, as_txt=True))
        self._set_status(f"Copied {len(rows)} row(s) to clipboard.")

    def _copy_channel_links_to_clipboard(self, rows):
        links = [str(row.get("Channel Link", row.get("input", ""))).strip() for row in rows if str(row.get("Channel Link", row.get("input", ""))).strip()]
        if not links:
            QMessageBox.information(self, "Channels", "There are no channel links to copy.")
            return
        QApplication.clipboard().setText("\n".join(links))
        self._set_status(f"Copied {len(links)} channel link(s) to clipboard.")

    def _selected_display_rows(self):
        self._ensure_table_synced()
        filtered_rows = self._filtered_rows()
        selected_indexes = sorted({index.row() for index in self.channels_table.selectionModel().selectedRows()})
        return [filtered_rows[row] for row in selected_indexes if 0 <= row < len(filtered_rows)]

    def _copy_selected_rows_context(self):
        rows = self._selected_display_rows()
        if not rows:
            QMessageBox.warning(self, "Channels", "Please select at least one row.")
            return
        self._copy_rows_to_clipboard(rows)

    def _copy_selected_links_context(self):
        rows = self._selected_display_rows()
        if not rows:
            QMessageBox.warning(self, "Channels", "Please select at least one row.")
            return
        self._copy_channel_links_to_clipboard(rows)

    def _preview_source_rows(self):
        self._ensure_table_synced()
        selected = self._selected_display_rows()
        if selected:
            return selected, "selected"
        visible = self._filtered_rows()
        return visible, "visible"

    def _split_links_text(self, text):
        raw = str(text or "").strip()
        if not raw or raw == "not-given":
            return []
        parts = []
        for chunk in raw.replace("\n", ",").split(","):
            item = chunk.strip()
            if item:
                parts.append(item)
        return parts

    def _format_preview_metric(self, label, value):
        safe_label = html.escape(str(label))
        safe_value = html.escape(str(value or "not-given"))
        return (
            f"<div class='metric-box'>"
            f"<div class='metric-number'>{safe_value}</div>"
            f"<div class='metric-title'>{safe_label}</div>"
            f"</div>"
        )

    def _generate_preview_table_html(self, rows, scope_label):
        total = len(rows)
        header_titles = ["Image"] + self.SEARCH_COLUMNS[2:]
        header_html = "".join(f"<th>{html.escape(title)}</th>" for title in header_titles)
        body_rows = []
        for row in rows:
            thumb = html.escape(str(row.get("Thumbnail URL", "")).strip())
            channel_id = html.escape(str(row.get("Channel ID", "")))
            channel_link = html.escape(str(row.get("Channel Link", row.get("input", ""))))
            source = html.escape(str(row.get("Source", "")))
            search_phrase = html.escape(str(row.get("Search Phrase", "")))
            title = html.escape(str(row.get("Title", "")))
            description = html.escape(str(row.get("Description", "")))
            total_videos = html.escape(str(row.get("Total Videos", "not-given")))
            total_views = html.escape(str(row.get("Total Views", "not-given")))
            subscribers = html.escape(str(row.get("Subscribers", "not-given")))
            date_joined = html.escape(str(row.get("Date Joined", "not-given")))
            country = html.escape(str(row.get("Country", "not-given")))
            keywords = html.escape(str(row.get("Keywords", "not-given")))
            external_links = self._split_links_text(row.get("External Links", "not-given"))
            ext_html = (
                "<div class='link-stack'>"
                + "".join(
                    f"<a href='{html.escape(link)}' target='_blank' rel='noreferrer'>{html.escape(link)}</a>"
                    for link in external_links
                )
                + "</div>"
                if external_links
                else "not-given"
            )
            image_html = (
                f"<img src='{thumb}' alt='thumb' loading='lazy' />" if thumb else "<span class='na-pill'>N/A</span>"
            )
            body_rows.append(
                "<tr>"
                "<td class='actions'><a href='#' onclick='removeRow(this); return false;'>Remove</a></td>"
                f"<td class='image-cell'>{image_html}</td>"
                f"<td>{channel_id}</td>"
                f"<td><a href='{channel_link}' target='_blank' rel='noreferrer'>{channel_link}</a></td>"
                f"<td>{source}</td>"
                f"<td>{search_phrase}</td>"
                f"<td>{title}</td>"
                f"<td>{description}</td>"
                f"<td>{total_videos}</td>"
                f"<td>{total_views}</td>"
                f"<td>{subscribers}</td>"
                f"<td>{date_joined}</td>"
                f"<td>{country}</td>"
                f"<td>{keywords}</td>"
                f"<td>{ext_html}</td>"
                "</tr>"
            )
        body_html = "\n".join(body_rows)
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Channels Preview Report</title>
  <style>
    :root {{
      --bg:#f6f6f6;
      --panel:#ffffff;
      --line:#d7d7d7;
      --text:#111111;
      --muted:#676767;
      --accent:#e14b2d;
      --accent-deep:#d44622;
      --accent-soft:#fbe2db;
      --link:#364bb7;
      --header:#efefef;
      --row-alt:#eef0ff;
    }}
    * {{ box-sizing:border-box; }}
    html, body {{ height:100%; }}
    body {{
      margin:0;
      font-family:Segoe UI, Arial, sans-serif;
      background:var(--bg);
      color:var(--text);
      font-size:13px;
    }}
    .page {{
      min-height:100%;
      padding:10px 12px 14px;
    }}
    .report-shell {{
      background:var(--panel);
      border:1px solid #c8c8c8;
      min-height:calc(100vh - 24px);
      display:flex;
      flex-direction:column;
    }}
    .topbar {{
      display:flex;
      justify-content:space-between;
      align-items:center;
      gap:12px;
      padding:8px 10px;
      border-bottom:1px solid var(--line);
      background:#fbfbfb;
    }}
    .brand {{
      display:flex;
      flex-direction:column;
      gap:2px;
    }}
    .brand-title {{
      font-size:18px;
      font-weight:700;
    }}
    .brand-sub {{
      font-size:12px;
      color:var(--muted);
    }}
    .toolbar {{
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:16px;
      padding:10px;
      border-bottom:1px solid var(--line);
      background:#ffffff;
    }}
    .toolbar-left, .toolbar-right {{
      display:flex;
      align-items:center;
      gap:8px;
      flex-wrap:wrap;
    }}
    .toolbar label {{
      color:#333333;
      font-size:12px;
    }}
    .toolbar select,
    .toolbar input {{
      border:1px solid #c9c9c9;
      border-radius:2px;
      padding:5px 8px;
      font-size:12px;
      color:var(--text);
      background:#fff;
    }}
    .toolbar input {{
      width:220px;
    }}
    .summary-bar {{
      display:flex;
      justify-content:space-between;
      gap:10px;
      padding:0 10px 10px;
      background:#ffffff;
    }}
    .summary-card {{
      background:var(--accent);
      color:#ffffff;
      min-width:140px;
      padding:10px 12px;
      font-weight:700;
      line-height:1.25;
    }}
    .summary-card strong {{
      display:block;
      font-size:30px;
      margin-top:2px;
      line-height:1;
    }}
    .table-shell {{
      flex:1;
      overflow:auto;
      border-top:1px solid var(--line);
    }}
    table {{
      width:100%;
      min-width:1920px;
      border-collapse:collapse;
      table-layout:auto;
    }}
    thead th {{
      position:sticky;
      top:0;
      z-index:2;
      background:var(--header);
      text-align:left;
      padding:8px 10px;
      border-right:1px solid var(--line);
      border-bottom:1px solid var(--line);
      font-size:12px;
      font-weight:700;
      white-space:nowrap;
    }}
    tbody td {{
      padding:9px 10px;
      border-right:1px solid var(--line);
      border-bottom:1px solid var(--line);
      vertical-align:top;
      font-size:12px;
      line-height:1.35;
      word-break:break-word;
      background:#ffffff;
    }}
    tbody tr:nth-child(odd) td {{ background:#f7f8ff; }}
    tbody tr:hover td {{ background:#fff0ec; }}
    img {{
      width:52px;
      height:52px;
      object-fit:cover;
      border:1px solid #c8c8c8;
      background:#ffffff;
      display:block;
    }}
    a {{ color:var(--link); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .na-pill {{
      display:inline-block;
      padding:4px 8px;
      border-radius:2px;
      background:#efefef;
      color:#6f6f6f;
      font-size:11px;
      font-weight:600;
    }}
    .actions {{
      min-width:68px;
      white-space:nowrap;
    }}
    .actions a {{
      color:#3949b0;
      font-size:12px;
    }}
    .image-cell {{
      min-width:74px;
      width:74px;
    }}
    .link-stack {{
      display:flex;
      flex-direction:column;
      gap:4px;
      min-width:240px;
    }}
    .footer {{
      display:flex;
      justify-content:space-between;
      align-items:center;
      gap:12px;
      padding:8px 10px;
      border-top:1px solid var(--line);
      background:#fbfbfb;
      color:#4b4b4b;
      font-size:12px;
    }}
  </style>
</head>
<body>
  <div class="page">
    <div class="report-shell">
      <section class="topbar">
        <div class="brand">
          <div class="brand-title">Channels Preview Report</div>
          <div class="brand-sub">TubeVibe export of {total} {html.escape(scope_label)} row(s)</div>
        </div>
      </section>
      <section class="toolbar">
        <div class="toolbar-left">
          <label for="entriesBox">Show</label>
          <select id="entriesBox" onchange="applyEntries()">
            <option>25</option>
            <option>100</option>
            <option>250</option>
            <option selected>All</option>
          </select>
          <label for="entriesBox">entries</label>
        </div>
        <div class="toolbar-right">
          <label for="searchBox">Search:</label>
          <input id="searchBox" type="search" placeholder="Search report..." oninput="filterRows()" />
        </div>
      </section>
      <section class="summary-bar">
        <div class="summary-card">Total Rows<strong>{total}</strong></div>
        <div class="summary-card">Scope<strong>{html.escape(scope_label.title())}</strong></div>
      </section>
      <section class="table-shell">
        <table id="channelsTable">
          <thead>
            <tr>
              <th>Actions</th>
              {header_html}
            </tr>
          </thead>
          <tbody>
            {body_html}
          </tbody>
        </table>
      </section>
      <section class="footer">
        <div>Remove only affects this preview file.</div>
        <div id="visibleCounter">Visible rows: {total}</div>
      </section>
    </div>
  </div>
  <script>
    function visibleRows() {{
      return Array.from(document.querySelectorAll('#channelsTable tbody tr'))
        .filter((row) => row.style.display !== 'none');
    }}
    function updateCounter() {{
      document.getElementById('visibleCounter').textContent = `Visible rows: ${{visibleRows().length}}`;
    }}
    function filterRows() {{
      const query = document.getElementById('searchBox').value.toLowerCase().trim();
      document.querySelectorAll('#channelsTable tbody tr').forEach((row) => {{
        row.style.display = row.innerText.toLowerCase().includes(query) ? '' : 'none';
      }});
      applyEntries(false);
      updateCounter();
    }}
    function applyEntries(resetSearch = false) {{
      const mode = document.getElementById('entriesBox').value;
      let rows = visibleRows();
      if (mode !== 'All') {{
        const limit = parseInt(mode, 10);
        rows.forEach((row, index) => {{
          row.dataset.entryHidden = index >= limit ? '1' : '0';
          if (index >= limit) row.style.display = 'none';
        }});
      }}
      if (resetSearch) {{
        filterRows();
        return;
      }}
      updateCounter();
    }}
    function removeRow(button) {{
      const row = button.closest('tr');
      if (row) row.remove();
      updateCounter();
    }}
    updateCounter();
  </script>
</body>
</html>"""

    def _generate_preview_feed_html(self, rows, scope_label):
        total = len(rows)
        cards = []
        for row in rows:
            thumb = html.escape(str(row.get("Thumbnail URL", "")).strip())
            title = html.escape(str(row.get("Title", "Untitled channel")))
            channel_link = html.escape(str(row.get("Channel Link", row.get("input", ""))))
            description = html.escape(str(row.get("Description", "not-given")))
            search_phrase = html.escape(str(row.get("Search Phrase", "")))
            country = html.escape(str(row.get("Country", "not-given")))
            keywords = html.escape(str(row.get("Keywords", "not-given")))
            external_links = self._split_links_text(row.get("External Links", "not-given"))
            ext_html = (
                "".join(
                    f"<a class='chip' href='{html.escape(link)}' target='_blank' rel='noreferrer'>{html.escape(link)}</a>"
                    for link in external_links[:6]
                )
                if external_links
                else "<span class='muted'>No external links</span>"
            )
            image_html = (
                f"<img src='{thumb}' alt='thumbnail' loading='lazy' />"
                if thumb
                else "<div class='image-fallback'>No Image</div>"
            )
            metrics_html = (
                self._format_preview_metric("Total Videos", row.get("Total Videos", "not-given"))
                + self._format_preview_metric("Total Views", row.get("Total Views", "not-given"))
                + self._format_preview_metric("Subscribers", row.get("Subscribers", "not-given"))
            )
            cards.append(
                f"<article class='feed-card'>"
                f"<div class='card-top'>{image_html}</div>"
                f"<div class='metrics-strip'>{metrics_html}</div>"
                f"<div class='body'>"
                f"<div class='meta-note'>Search Phrase: {search_phrase or 'channel'}</div>"
                f"<a class='title' href='{channel_link}' target='_blank' rel='noreferrer'>{title}</a>"
                f"<p class='desc'>{description}</p>"
                f"<div class='meta-grid'>"
                f"<div><strong>Date Joined:</strong><span>{html.escape(str(row.get('Date Joined', 'not-given')))}</span></div>"
                f"<div><strong>Country:</strong><span>{country}</span></div>"
                f"</div>"
                f"<div class='keywords'><strong>Keywords:</strong> {keywords}</div>"
                f"<div class='ext-links'>{ext_html}</div>"
                f"</div>"
                f"</article>"
            )
        cards_html = "\n".join(cards)
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Channels Feed Preview</title>
  <style>
    :root {{
      --bg:#f5f5f5;
      --panel:#ffffff;
      --text:#111111;
      --muted:#6d6d6d;
      --line:#d7d7d7;
      --accent:#e14b2d;
      --accent-deep:#d44622;
      --chip:#eef1ff;
      --link:#364bb7;
    }}
    * {{ box-sizing:border-box; }}
    html, body {{ height:100%; }}
    body {{ margin:0; background:var(--bg); font-family:"Segoe UI",Arial,sans-serif; color:var(--text); }}
    .page {{ padding:10px 12px 14px; min-height:100%; }}
    .top {{
      display:flex; justify-content:space-between; align-items:center; gap:16px;
      margin-bottom:12px;
      padding:10px 12px;
      border:1px solid var(--line);
      background:#ffffff;
    }}
    .top h1 {{ margin:0; font-size:22px; }}
    .top p {{ margin:4px 0 0; color:var(--muted); font-size:12px; }}
    .summary {{
      background:#ffffff; border:1px solid var(--line); padding:10px 14px; color:var(--muted); font-size:12px;
    }}
    .feed {{
      display:grid;
      grid-template-columns:repeat(auto-fill,minmax(320px,1fr));
      gap:14px;
      align-items:start;
    }}
    .feed-card {{
      background:var(--panel);
      border:1px solid var(--line);
      overflow:hidden;
    }}
    .card-top {{
      background:#ffffff;
      min-height:240px;
      display:flex;
      align-items:center;
      justify-content:center;
      border-bottom:1px solid var(--line);
    }}
    .card-top img {{
      width:100%;
      height:240px;
      object-fit:cover;
      display:block;
    }}
    .image-fallback {{
      color:#888888;
      font-size:18px;
      font-weight:700;
      padding:40px 0;
    }}
    .metrics-strip {{
      display:grid;
      grid-template-columns:repeat(3,1fr);
      gap:1px;
      background:#ffffff;
      border-bottom:1px solid var(--line);
    }}
    .metric-box {{
      background:var(--accent);
      color:#ffffff;
      text-align:center;
      padding:10px 8px;
      min-height:64px;
    }}
    .metric-number {{
      font-size:18px;
      font-weight:800;
      line-height:1.1;
    }}
    .metric-title {{
      font-size:11px;
      margin-top:4px;
    }}
    .body {{ padding:12px 14px 14px; }}
    .meta-note {{
      color:#9b9b9b;
      font-size:12px;
      margin-bottom:8px;
    }}
    .title {{
      display:block;
      color:var(--text);
      text-decoration:none;
      font-size:18px;
      font-weight:700;
      line-height:1.3;
      margin-bottom:10px;
    }}
    .title:hover {{ color:var(--link); }}
    .desc {{
      color:#444444;
      line-height:1.45;
      min-height:74px;
      margin:0 0 10px;
      font-size:13px;
    }}
    .meta-grid {{
      display:grid;
      grid-template-columns:repeat(2,minmax(0,1fr));
      gap:8px 12px;
      margin-bottom:12px;
      font-size:12px;
    }}
    .meta-grid div {{
      display:flex;
      flex-direction:column;
      gap:2px;
    }}
    .keywords {{
      font-size:12px;
      line-height:1.45;
      margin-bottom:12px;
      color:#333333;
    }}
    .ext-links {{
      display:flex;
      flex-wrap:wrap;
      gap:6px;
    }}
    .chip {{
      display:inline-flex;
      align-items:center;
      gap:6px;
      padding:6px 8px;
      background:var(--chip);
      color:var(--link);
      text-decoration:none;
      font-size:11px;
      font-weight:700;
    }}
    .muted {{ color:var(--muted); font-size:13px; }}
  </style>
</head>
<body>
  <div class="page">
    <section class="top">
      <div>
        <h1>Channels Feed Preview</h1>
        <p>Showing {total} {html.escape(scope_label)} row(s) from the Channels tool.</p>
      </div>
      <div class="summary">Tube Atlas style feed preview for quick visual scanning.</div>
    </section>
    <section class="feed">
      {cards_html}
    </section>
  </div>
</body>
</html>"""

    def _open_html_preview(self, preview_type):
        rows, scope_label = self._preview_source_rows()
        if not rows:
            QMessageBox.information(self, "Channels", "There are no rows to preview.")
            return
        preview_type = str(preview_type or "table").lower()
        if preview_type == "feed":
            content = self._generate_preview_feed_html(rows, scope_label)
            filename = "channels-preview-feed.html"
            status_label = "HTML feed"
        else:
            content = self._generate_preview_table_html(rows, scope_label)
            filename = "channels-preview-table.html"
            status_label = "HTML table"
        preview_path = Path(tempfile.gettempdir()) / filename
        preview_path.write_text(content, encoding="utf-8")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(preview_path)))
        self._set_status(f"Opened {status_label} preview for {len(rows)} row(s).")

    def _rebuild_row_index(self):
        self._row_index_by_channel = {}
        for index, row in enumerate(self._rows_cache):
            for row_key in self._channel_keys(row):
                self._row_index_by_channel[row_key] = index

    def _delete_selected_rows_context(self):
        rows = self._selected_display_rows()
        if not rows:
            QMessageBox.warning(self, "Channels", "Please select at least one row.")
            return
        count = len(rows)
        answer = QMessageBox.question(
            self,
            "Delete Channels",
            f"Delete {count} selected row(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        row_keys = {self._channel_key(row) for row in rows if self._channel_key(row)}
        if row_keys:
            self._rows_cache = [row for row in self._rows_cache if self._channel_key(row) not in row_keys]
        else:
            filtered_rows = self._filtered_rows()
            remaining = []
            selected_ids = {id(row) for row in rows}
            for row in self._rows_cache:
                if row in filtered_rows and id(row) in selected_ids:
                    continue
                remaining.append(row)
            self._rows_cache = remaining
        self._search_results_count = len(self._rows_cache)
        self._rebuild_row_index()
        self._rebuild_table_from_cache()
        self.lbl_total_items.setText(f"Total Items: {len(self._filtered_rows())}")
        self._set_status(f"Deleted {count} row(s).")

    def _delete_all_rows_context(self):
        total = len(self._rows_cache)
        if total <= 0:
            QMessageBox.information(self, "Channels", "There are no rows to delete.")
            return
        answer = QMessageBox.question(
            self,
            "Delete Channels",
            f"Delete ALL {total} row(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._clear_table()
        self._set_status(f"Deleted all {total} row(s).")

    def _channel_rows_to_video_keywords(self, rows):
        keywords = []
        seen = set()
        for row in rows:
            candidates = [
                str(row.get("Title", "")).strip(),
                str(row.get("Search Phrase", "")).strip(),
                str(row.get("Channel ID", "")).strip(),
            ]
            for candidate in candidates:
                if not candidate or candidate.lower() in {"not-given", "n/a"}:
                    continue
                key = candidate.lower()
                if key in seen:
                    continue
                seen.add(key)
                keywords.append(candidate)
                break
        return keywords

    def _send_selected_to_videos_tool_context(self):
        rows = self._selected_display_rows()
        if not rows:
            QMessageBox.warning(self, "Channels", "Please select at least one row.")
            return
        keywords = self._channel_rows_to_video_keywords(rows)
        if not keywords:
            QMessageBox.warning(self, "Channels", "No usable channel titles found in the selected rows.")
            return
        if self.main_window and hasattr(self.main_window, "handle_send_to_videos"):
            self.main_window.handle_send_to_videos(keywords, source_tool="Channels tool")
            self._set_status(f"Sent {len(keywords)} selected channel row(s) to Videos tool.")

    def _send_channels_to_comments_context(self, all_rows=False):
        rows = list(self._rows_cache) if all_rows else self._selected_display_rows()
        if not rows:
            QMessageBox.warning(self, "Channels", "Please select at least one row.")
            return
        if self.main_window and hasattr(self.main_window, "handle_send_channels_to_comments"):
            label = "ALL rows from Channels tool" if all_rows else "SELECTED rows from Channels tool"
            if self.main_window.handle_send_channels_to_comments(rows, source_label=label):
                self._set_status(f"Sent {len(rows)} channel row(s) to Comments tool.")

    def _channel_search_terms(self, rows):
        terms = []
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            candidates = [
                str(row.get("Title", "")).strip(),
                str(row.get("Search Phrase", "")).strip(),
                str(row.get("Channel ID", "")).strip(),
            ]
            for candidate in candidates:
                lowered = candidate.lower()
                if not candidate or lowered in {"not-given", "n/a", "-", "none"}:
                    continue
                if lowered in seen:
                    continue
                seen.add(lowered)
                terms.append(candidate)
                break
        return terms

    def _open_channel_search_terms(self, rows, scope_label):
        search_terms = self._channel_search_terms(rows)
        if not search_terms:
            QMessageBox.warning(self, "Channels", "No usable search terms found in the selected rows.")
            return
        if len(search_terms) > 20:
            answer = QMessageBox.question(
                self,
                "Channels Search",
                f"You are about to open {len(search_terms)} browser tabs. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        for term in search_terms:
            url = f"https://www.youtube.com/results?search_query={quote_plus(term)}"
            QDesktopServices.openUrl(QUrl(url))
        self._set_status(f"Opened {len(search_terms)} YouTube search tab(s) for {scope_label}.")

    def _search_current_row_context(self):
        row = self.channels_table.currentRow()
        filtered_rows = self._filtered_rows()
        if row < 0 or row >= len(filtered_rows):
            QMessageBox.warning(self, "Channels", "Please choose a row first.")
            return
        self._open_channel_search_terms([filtered_rows[row]], "current row")

    def _search_selected_rows_context(self):
        rows = self._selected_display_rows()
        if not rows:
            QMessageBox.warning(self, "Channels", "Please select at least one row.")
            return
        self._open_channel_search_terms(rows, "selected rows")

    def _search_all_rows_context(self):
        if not self._rows_cache:
            QMessageBox.information(self, "Channels", "There are no rows to search.")
            return
        self._open_channel_search_terms(self._rows_cache, "all rows")

    def _on_table_item_changed(self, item):
        if self._checkbox_syncing or item is None or item.column() != 0:
            return
        row = item.row()
        filtered_rows = self._filtered_rows()
        if not (0 <= row < len(filtered_rows)):
            return
        filtered_rows[row]["_checked"] = item.checkState() == Qt.CheckState.Checked

    def _set_rows_checked(self, rows, checked):
        if not rows:
            return 0
        state = bool(checked)
        updated = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            if bool(row.get("_checked", False)) == state:
                continue
            row["_checked"] = state
            updated += 1
        if updated:
            self._rebuild_table_from_cache()
        return updated

    def _set_selected_rows_checked_context(self, checked):
        rows = self._selected_display_rows()
        if not rows:
            QMessageBox.warning(self, "Channels", "Please select at least one row.")
            return
        updated = self._set_rows_checked(rows, checked)
        action = "Checked" if checked else "Unchecked"
        self._set_status(f"{action} {updated} selected row(s).")

    def _set_all_rows_checked_context(self, checked):
        if not self._rows_cache:
            QMessageBox.information(self, "Channels", "There are no rows to update.")
            return
        updated = self._set_rows_checked(self._rows_cache, checked)
        action = "Checked" if checked else "Unchecked"
        self._set_status(f"{action} {updated} row(s).")

    def _open_browse_file_menu(self):
        menu = QMenu(self)
        act_load = menu.addAction("Load TXT")
        act_save = menu.addAction("Save TXT")
        chosen = menu.exec(self.btn_browse_file.mapToGlobal(self.btn_browse_file.rect().bottomLeft()))
        if chosen == act_load:
            path, _ = QFileDialog.getOpenFileName(self, "Load Channel Links", "", "Text Files (*.txt);;All Files (*.*)")
            if not path:
                return
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                self.import_links_input.setPlainText(fh.read())
            self._set_status(f"Loaded channel links from {path}.")
        elif chosen == act_save:
            content = self.import_links_input.toPlainText().strip()
            if not content:
                QMessageBox.information(self, "Channels", "There is no channel link content to save.")
                return
            path, _ = QFileDialog.getSaveFileName(self, "Save Channel Links", "channel_links.txt", "Text Files (*.txt)")
            if not path:
                return
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            self._set_status(f"Saved channel links to {path}.")

    def _show_next_steps_message(self, label="This feature"):
        QMessageBox.information(self, "Channels", f"{label} will be implemented soon.")

    def _sync_context_menu_selection(self, pos):
        clicked_item = self.channels_table.itemAt(pos)
        if clicked_item is None:
            return
        clicked_row = clicked_item.row()
        selected_rows = {index.row() for index in self.channels_table.selectionModel().selectedRows()}
        if clicked_row in selected_rows:
            self.channels_table.setCurrentItem(clicked_item, QItemSelectionModel.SelectionFlag.NoUpdate)
            return
        self.channels_table.selectRow(clicked_row)

    def _open_channels_context_menu(self, pos):
        self._ensure_table_synced()
        self._sync_context_menu_selection(pos)

        menu = QMenu(self.channels_table)
        menu.setStyleSheet(
            "QMenu { background:#f4f4f4; color:#222222; border:1px solid #a8a8a8; }"
            "QMenu::item { padding:6px 22px; margin:1px 4px; }"
            "QMenu::item:selected { background:#f1d5df; color:#111111; }"
            "QMenu::separator { height:1px; background:#d0d0d0; margin:4px 8px; }"
        )

        channels_tool_menu = menu.addMenu("Channels tool")
        channels_tool_menu.addAction("Send SELECTED to Videos tool", self._send_selected_to_videos_tool_context)
        channels_tool_menu.addAction("Send SELECTED to Comments tool", lambda: self._send_channels_to_comments_context(False))
        channels_tool_menu.addAction("Send ALL to Comments tool", lambda: self._send_channels_to_comments_context(True))

        checkboxes_menu = menu.addMenu("Checkboxes")
        checkboxes_menu.addAction("Check SELECTED rows", lambda: self._set_selected_rows_checked_context(True))
        checkboxes_menu.addAction("Uncheck SELECTED rows", lambda: self._set_selected_rows_checked_context(False))
        checkboxes_menu.addAction("Check ALL rows", lambda: self._set_all_rows_checked_context(True))
        checkboxes_menu.addAction("Uncheck ALL rows", lambda: self._set_all_rows_checked_context(False))

        filters_menu = menu.addMenu("Filters")
        context_filter_actions = self._build_filters_menu(filters_menu)

        copy_menu = menu.addMenu("Copy")
        copy_menu.addAction("Copy SELECTED rows to clipboard", self._copy_selected_rows_context)
        copy_menu.addAction("Copy ALL rows to clipboard", lambda: self._copy_rows_to_clipboard(self._rows_cache))
        copy_menu.addAction("Copy SELECTED channel links to clipboard", self._copy_selected_links_context)
        copy_menu.addAction("Copy ALL channel links to clipboard", lambda: self._copy_channel_links_to_clipboard(self._rows_cache))

        search_menu = menu.addMenu("Search")
        search_menu.addAction("Search current row", self._search_current_row_context)
        search_menu.addAction("Search SELECTED rows", self._search_selected_rows_context)
        search_menu.addAction("Search ALL rows", self._search_all_rows_context)

        preview_menu = menu.addMenu("Preview")
        preview_menu.addAction("Preview in HTML Table", lambda: self._open_html_preview("table"))
        preview_menu.addAction("Preview in HTML Feed", lambda: self._open_html_preview("feed"))

        menu.addSeparator()
        menu.addAction("Auto-fit column widths", self._auto_fit_column_widths)
        menu.addAction("Reset column widths", self._reset_column_widths)

        delete_menu = menu.addMenu("Delete")
        delete_menu.addAction("Delete SELECTED rows", self._delete_selected_rows_context)
        delete_menu.addAction("Delete ALL rows", self._delete_all_rows_context)

        chosen = menu.exec(self.channels_table.viewport().mapToGlobal(pos))
        self._apply_filters_menu_choice(chosen, context_filter_actions)

    def start_search(self):
        if self._search_worker is not None and self._search_worker.isRunning():
            QMessageBox.information(self, "Channels", "Channel search is already running.")
            return
        query = self.search_input.text().strip()
        if not query:
            QMessageBox.warning(self, "Channels", "Please enter a search phrase first.")
            return
        if not any((self.chk_youtube_first_page.isChecked(), self.chk_google.isChecked(), self.chk_bing.isChecked())):
            QMessageBox.warning(self, "Channels", "Select at least one search source.")
            return

        self._clear_table(invalidate_running=True, stop_workers=True)
        token = self._next_operation_token()
        self._set_mode("search")
        self.search_progress.setRange(0, 0)
        self._set_running_state(True, context="search")
        self._set_status(f"Searching channels for '{query}'...")
        proxy_payload = self.main_window.get_proxy_settings() if self.main_window and hasattr(self.main_window, "get_proxy_settings") else {"enabled": False, "proxies": []}
        self._search_worker = ChannelsSearchWorker(
            query=query,
            include_youtube=self.chk_youtube_first_page.isChecked(),
            include_google=self.chk_google.isChecked(),
            include_bing=self.chk_bing.isChecked(),
            pages=self.pages_spin.value(),
            use_proxies=proxy_payload.get("enabled", False),
            proxy_list=proxy_payload.get("proxies", []),
        )
        self._search_worker.item_signal.connect(lambda row, current_token=token: self._append_search_result(row, current_token))
        self._search_worker.status_signal.connect(
            lambda text, current_token=token: self._set_status(text) if self._is_current_operation(current_token) else None
        )
        self._search_worker.error_signal.connect(
            lambda text, current_token=token: QMessageBox.warning(self, "Channels", text)
            if self._is_current_operation(current_token)
            else None
        )
        self._search_worker.finished_signal.connect(
            lambda result, current_token=token: self._on_search_discovery_finished(result, current_token)
        )
        self._search_worker.start()

    def _on_search_discovery_finished(self, result, token=None):
        worker = self._search_worker
        self._search_worker = None
        if worker is not None:
            worker.deleteLater()
        if token is not None and not self._is_current_operation(token):
            return
        payload = dict(result or {})
        items = list(payload.get("items", []))
        stopped = bool(payload.get("stopped", False))
        if stopped and not items:
            self.search_progress.setRange(0, 100)
            self.search_progress.setValue(0)
            self._set_running_state(False, context="search")
            self._set_status("Channel search stopped.")
            return
        if not items:
            self.search_progress.setRange(0, 100)
            self.search_progress.setValue(0)
            self._set_running_state(False, context="search")
            self._set_status("No channels found.")
            return
        self.search_progress.setRange(0, 0)
        self._set_status(f"Search found {len(items)} channel(s). Enriching details...")
        self._start_search_enrich_pipeline(items, token)

    def _start_search_enrich_pipeline(self, inputs, token=None):
        if token is not None and not self._is_current_operation(token):
            return
        if self._search_enrich_worker is not None and self._search_enrich_worker.isRunning():
            return
        proxy_payload = self.main_window.get_proxy_settings() if self.main_window and hasattr(self.main_window, "get_proxy_settings") else {"enabled": False, "proxies": []}
        self._set_running_state(True, context="search_enrich")
        self._search_enrich_worker = ChannelImportWorker(
            inputs=inputs,
            use_proxies=proxy_payload.get("enabled", False),
            proxy_list=proxy_payload.get("proxies", []),
        )
        self._search_enrich_worker.row_signal.connect(
            lambda row, current_token=token: self._update_search_row(row, current_token)
        )
        self._search_enrich_worker.status_signal.connect(
            lambda text, current_token=token: self._set_status(text) if self._is_current_operation(current_token) else None
        )
        self._search_enrich_worker.error_signal.connect(
            lambda text, current_token=token: QMessageBox.warning(self, "Channels", text)
            if self._is_current_operation(current_token)
            else None
        )
        self._search_enrich_worker.finished_signal.connect(
            lambda result, current_token=token: self._on_search_enrich_finished(result, current_token)
        )
        self._search_enrich_worker.start()

    def _on_search_enrich_finished(self, result, token=None):
        worker = self._search_enrich_worker
        self._search_enrich_worker = None
        if worker is not None:
            worker.deleteLater()
        if token is not None and not self._is_current_operation(token):
            return
        self._flush_rebuild()
        self.search_progress.setRange(0, 100)
        self.search_progress.setValue(100)
        self._set_running_state(False, context="search")
        payload = dict(result or {})
        count = int(payload.get("count", 0))
        invalid = int(payload.get("invalid", 0))
        failed = int(payload.get("failed", 0))
        stopped = bool(payload.get("stopped", False))
        suffix = []
        if invalid:
            suffix.append(f"invalid: {invalid}")
        if failed:
            suffix.append(f"failed: {failed}")
        extra = f" ({', '.join(suffix)})" if suffix else ""
        if stopped:
            self._set_status(f"Channel search stopped after enriching {count} row(s){extra}.")
        else:
            self._set_status(f"Channel search finished. Enriched {count} row(s){extra}.")

    def stop_search(self):
        if self._search_worker is not None and self._search_worker.isRunning():
            self._search_worker.stop()
        if self._search_enrich_worker is not None and self._search_enrich_worker.isRunning():
            self._search_enrich_worker.stop()
        if self._import_worker is not None and self._import_worker.isRunning():
            self._import_worker.stop()
        self._set_status("Stopping...")

    def start_import_analysis(self):
        inputs = [line.strip() for line in self.import_links_input.toPlainText().splitlines() if line.strip()]
        if not inputs:
            QMessageBox.warning(self, "Channels", "Please paste at least one channel link, handle, or channel ID.")
            return
        self._clear_table(invalidate_running=True, stop_workers=True)
        token = self._next_operation_token()
        self._set_mode("browse")
        self._set_status(f"Analyzing {len(inputs)} channel input(s)...")
        self.search_progress.setRange(0, 0)
        self._start_import_pipeline(inputs, mode="browse", token=token)

    def _start_import_pipeline(self, inputs, mode="search", token=None):
        if token is not None and not self._is_current_operation(token):
            return
        if self._import_worker is not None and self._import_worker.isRunning():
            QMessageBox.information(self, "Channels", "Channel analysis is already running.")
            return
        self._set_running_state(True, context="import")
        proxy_payload = self.main_window.get_proxy_settings() if self.main_window and hasattr(self.main_window, "get_proxy_settings") else {"enabled": False, "proxies": []}
        self._import_worker = ChannelImportWorker(
            inputs=inputs,
            use_proxies=proxy_payload.get("enabled", False),
            proxy_list=proxy_payload.get("proxies", []),
        )
        self._import_worker.row_signal.connect(lambda row, current_token=token: self._append_row(row, current_token))
        self._import_worker.status_signal.connect(
            lambda text, current_token=token: self._set_status(text) if self._is_current_operation(current_token) else None
        )
        self._import_worker.error_signal.connect(
            lambda text, current_token=token: QMessageBox.warning(self, "Channels", text)
            if self._is_current_operation(current_token)
            else None
        )
        self._import_worker.finished_signal.connect(
            lambda result, source_mode=mode, current_token=token: self._on_import_finished(result, source_mode, current_token)
        )
        self._import_worker.start()

    def _on_import_finished(self, result, source_mode, token=None):
        worker = self._import_worker
        self._import_worker = None
        if worker is not None:
            worker.deleteLater()
        if token is not None and not self._is_current_operation(token):
            return
        self._flush_rebuild()
        self.search_progress.setRange(0, 100)
        self.search_progress.setValue(0)
        self._set_running_state(False, context=source_mode)
        payload = dict(result or {})
        count = int(payload.get("count", 0))
        invalid = int(payload.get("invalid", 0))
        failed = int(payload.get("failed", 0))
        stopped = bool(payload.get("stopped", False))
        suffix = []
        if invalid:
            suffix.append(f"invalid: {invalid}")
        if failed:
            suffix.append(f"failed: {failed}")
        extra = f" ({', '.join(suffix)})" if suffix else ""
        if stopped:
            self._set_status(f"Channel analysis stopped. Loaded {count} row(s){extra}.")
        else:
            self._set_status(f"Channel analysis finished. Loaded {count} row(s){extra}.")

    def stop_import_analysis(self):
        if self._import_worker is not None and self._import_worker.isRunning():
            self._import_worker.stop()
            self._set_status("Stopping channel analysis...")

    def _open_browse_extract_dialog(self):
        dialog = BrowseAndExtractDialog(self)
        try:
            dialog._set_link_mode("channel")
        except Exception:
            pass
        dialog.exec()

    def _on_cell_double_clicked(self, row, column):
        if column not in {3, 14}:
            return
        item = self.channels_table.item(row, column)
        if item is None:
            return
        text = item.text().strip().split(",", 1)[0].strip()
        if text.startswith("http"):
            QDesktopServices.openUrl(QUrl(text))

    def closeEvent(self, event):
        self._stop_all_workers()
        self._next_operation_token()
        self._rebuild_timer.stop()
        super().closeEvent(event)

    def receive_payload(self, text, hint_text=""):
        payload = str(text or "").strip()
        if payload:
            first_line = payload.splitlines()[0].strip()
            self.search_input.setText(first_line[:200])
        self.lbl_status.setText(str(hint_text or "Received data from another tool."))
        self._set_mode("search")

    def receive_links_for_import(self, links, hint_text=""):
        clean_links = [str(link).strip() for link in (links or []) if str(link).strip()]
        self.import_links_input.setPlainText("\n".join(clean_links))
        self.lbl_browse_total.setText(f"Total: {len(clean_links)}")
        self.lbl_status.setText(str(hint_text or f"Loaded {len(clean_links)} channel link(s) for import."))
        self._set_mode("browse")
