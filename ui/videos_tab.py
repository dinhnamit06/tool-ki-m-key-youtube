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
    QVBoxLayout,
    QWidget,
    QHeaderView,
)


class VideosTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._mode = "search"
        self._checkbox_syncing = False
        self._light_label_style = "QLabel { color: #111111; }"
        self._light_input_style = (
            "QLineEdit { background:#ffffff; color:#111111; border:1px solid #c7c7c7; border-radius:3px; padding:5px 8px; }"
            "QLineEdit:focus { border:1px solid #9c9c9c; }"
        )
        self._light_combo_style = (
            "QComboBox { background:#ffffff; color:#111111; border:1px solid #c7c7c7; border-radius:3px; padding:4px 8px; }"
            "QComboBox::drop-down { border: none; width: 20px; }"
            "QComboBox QAbstractItemView { background:#ffffff; color:#111111; border:1px solid #c7c7c7; selection-background-color:#e7e7e7; selection-color:#111111; }"
        )
        self._light_checkbox_style = "QCheckBox { color:#111111; }"
        self.setup_ui()

    def setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

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
        panel.setStyleSheet("QFrame { background-color: #f3f3f3; border: 1px solid #d0d0d0; }")
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
        page.setStyleSheet(self._light_label_style)
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        self.input_search_phrase = QLineEdit()
        self.input_search_phrase.setPlaceholderText("Search Phrase")
        self.input_search_phrase.setStyleSheet(self._light_input_style)

        self.btn_search = QPushButton("Search")
        self.btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_search.setStyleSheet(
            "QPushButton { background-color:#e50914; color:#ffffff; border:none; border-radius:4px; padding:6px 12px; font-weight:700; }"
            "QPushButton:hover { background-color:#ff1a25; }"
        )
        self.btn_search.clicked.connect(lambda: self._show_coming_soon("Search"))

        v.addWidget(QLabel("Search Phrase:"))
        v.addWidget(self.input_search_phrase)
        v.addWidget(self.btn_search)

        self.chk_youtube_first = QCheckBox("Youtube (first page results only)")
        self.chk_youtube_first.setChecked(True)
        self.chk_youtube_first.setStyleSheet(self._light_checkbox_style)
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
        self.chk_contains_subtitles.setStyleSheet(self._light_checkbox_style)
        self.chk_creative_commons.setStyleSheet(self._light_checkbox_style)
        v.addWidget(self.chk_contains_subtitles)
        v.addWidget(self.chk_creative_commons)

        row_source = QHBoxLayout()
        self.chk_google = QCheckBox("Google")
        self.chk_google.setChecked(True)
        self.chk_bing = QCheckBox("Bing")
        self.chk_bing.setChecked(True)
        self.chk_google.setStyleSheet(self._light_checkbox_style)
        self.chk_bing.setStyleSheet(self._light_checkbox_style)
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
        self.btn_trending_videos.setStyleSheet(
            "QPushButton { background-color:#e50914; color:#ffffff; border:none; border-radius:4px; padding:6px 12px; font-weight:700; }"
            "QPushButton:hover { background-color:#ff1a25; }"
        )
        self.btn_trending_videos.clicked.connect(lambda: self._show_coming_soon("Trending Videos"))
        v.addWidget(self.btn_trending_videos)
        v.addStretch()
        return page

    def _build_browse_left_page(self):
        page = QWidget()
        page.setStyleSheet(self._light_label_style)
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        self.btn_get_data = QPushButton("Get Data")
        self.btn_get_data.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_get_data.setStyleSheet(
            "QPushButton { background-color:#e50914; color:#ffffff; border:none; border-radius:4px; padding:6px 12px; font-weight:700; }"
            "QPushButton:hover { background-color:#ff1a25; }"
        )
        self.btn_get_data.clicked.connect(lambda: self._show_coming_soon("Get Data"))
        v.addWidget(self.btn_get_data)

        v.addWidget(QLabel("Extract video links by:"))
        row_type = QHBoxLayout()
        self.btn_browser_links = QPushButton("Browser")
        self.btn_content_links = QPushButton("Content")
        for btn in (self.btn_browser_links, self.btn_content_links):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background-color:#e50914; color:#ffffff; border:none; border-radius:4px; padding:5px 10px; font-weight:600; }"
                "QPushButton:hover { background-color:#ff1a25; }"
            )
        row_type.addWidget(self.btn_browser_links)
        row_type.addWidget(self.btn_content_links)
        v.addLayout(row_type)

        v.addWidget(QLabel("Youtube video links: ( one per line )"))
        self.input_video_links = QLineEdit()
        self.input_video_links.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self.input_video_links.setStyleSheet(self._light_input_style)
        v.addWidget(self.input_video_links)

        self.text_links_block = QFrame()
        self.text_links_block.setStyleSheet("QFrame { background-color:#ffffff; border:1px solid #c7c7c7; border-radius:3px; }")
        links_layout = QVBoxLayout(self.text_links_block)
        links_layout.setContentsMargins(6, 6, 6, 6)
        links_layout.setSpacing(4)
        for sample in (
            "https://www.youtube.com/watch?v=abc123",
            "https://www.youtube.com/watch?v=def456",
            "https://www.youtube.com/watch?v=ghi789",
            "https://www.youtube.com/watch?v=jkl012",
            "https://www.youtube.com/watch?v=mno345",
        ):
            line = QLabel(sample)
            line.setStyleSheet("color:#333333;")
            links_layout.addWidget(line)
        links_layout.addStretch()
        v.addWidget(self.text_links_block, stretch=1)
        return page

    def _build_right_panel(self):
        panel = QFrame()
        panel.setStyleSheet("QFrame { background-color: #f8f8f8; border: 1px solid #d0d0d0; }")
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
        self.videos_table.setStyleSheet(
            "QTableWidget { background-color:#ffffff; color:#111111; gridline-color:#dddddd; border:1px solid #cfcfcf; }"
            "QHeaderView::section { background-color:#f0f0f0; color:#111111; border:1px solid #d0d0d0; font-weight:700; padding:4px; }"
        )

        header = self.videos_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)

        self.videos_table.setColumnWidth(0, 28)
        self.videos_table.setColumnWidth(1, 42)
        self.videos_table.setColumnWidth(2, 90)
        self.videos_table.setColumnWidth(3, 170)
        self.videos_table.setColumnWidth(4, 80)
        self.videos_table.setColumnWidth(5, 110)
        self.videos_table.setColumnWidth(6, 180)

        v.addWidget(self.videos_table, stretch=1)

        slider_row = QHBoxLayout()
        slider_row.setContentsMargins(4, 0, 4, 0)
        slider_row.setSpacing(8)
        slider_row.addWidget(QLabel("Image Size:"))
        self.slider_image_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_image_size.setRange(20, 80)
        self.slider_image_size.setValue(25)
        self.slider_image_size.valueChanged.connect(self._on_image_size_changed)
        self.lbl_image_size = QLabel("25 px")
        self.lbl_image_size.setMinimumWidth(44)
        slider_row.addWidget(self.slider_image_size, stretch=1)
        slider_row.addWidget(self.lbl_image_size)
        v.addLayout(slider_row)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(4, 0, 4, 0)
        bottom.setSpacing(8)

        self.lbl_total_items = QLabel("Total Items: 0")
        self.lbl_selected_rows = QLabel("Selected rows: 0")
        self.lbl_total_items.setStyleSheet("color:#333333; font-weight:700;")
        self.lbl_selected_rows.setStyleSheet("color:#555555; font-weight:600;")

        self.btn_file = QPushButton("File")
        self.btn_filters = QPushButton("Filters")
        self.btn_clear = QPushButton("Clear")
        for btn in (self.btn_file, self.btn_filters, self.btn_clear):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background-color:#e50914; color:#ffffff; border:none; border-radius:4px; padding:6px 12px; font-weight:700; }"
                "QPushButton:hover { background-color:#ff1a25; }"
            )
        self.btn_file.clicked.connect(lambda: self._show_coming_soon("File"))
        self.btn_filters.clicked.connect(lambda: self._show_coming_soon("Filters"))
        self.btn_clear.clicked.connect(self._clear_table_ui_only)

        bottom.addWidget(self.lbl_total_items)
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

    def _show_coming_soon(self, feature_name):
        QMessageBox.information(self, "Videos Tool", f"{feature_name} will be implemented in the next step.")
