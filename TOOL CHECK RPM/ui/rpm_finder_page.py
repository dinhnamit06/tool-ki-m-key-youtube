from __future__ import annotations

from typing import Sequence

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QToolButton, QVBoxLayout, QWidget

from core.rpm_data import ChannelRecord, build_sample_channels
from core.rpm_service import RPMFilterState, RPMFinderService, categories_from_channels
from ui.channel_card import ChannelCard
from ui.filter_dialog import AdvancedFiltersDialog


class RPMFinderPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.channels = build_sample_channels()
        self.service = RPMFinderService(self.channels)
        self.filter_state = RPMFilterState()
        self.current_search_mode = "Keyword"

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = self._build_sidebar()
        root.addWidget(self.sidebar)

        main_wrap = QWidget()
        main_layout = QVBoxLayout(main_wrap)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(18)

        topbar = self._build_topbar()
        topbar.setObjectName("topbar")
        main_layout.addWidget(topbar)

        title_row = QHBoxLayout()
        lbl_title = QLabel("RPM Finder")
        lbl_title.setObjectName("app_title")
        title_row.addWidget(lbl_title)
        title_row.addStretch()
        main_layout.addLayout(title_row)

        self.banner = QLabel("Highlighted channels are picked by AI.")
        self.banner.setStyleSheet("QLabel { background:#ddff26; color:#18202a; border-radius:10px; padding:10px 14px; font-weight:700; }")
        main_layout.addWidget(self.banner)

        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.results_host = QWidget()
        self.results_layout = QVBoxLayout(self.results_host)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(18)
        self.results_scroll.setWidget(self.results_host)
        main_layout.addWidget(self.results_scroll, 1)

        self.footer_label = QLabel("")
        self.footer_label.setObjectName("muted_label")
        main_layout.addWidget(self.footer_label)

        root.addWidget(main_wrap, 1)
        self._render_results(self.service.all_channels())

    def _build_sidebar(self):
        frame = QFrame(); frame.setObjectName("sidebar"); frame.setFixedWidth(104)
        layout = QVBoxLayout(frame); layout.setContentsMargins(18, 16, 18, 16); layout.setSpacing(8)
        logo = QLabel("nex\nLev"); logo.setObjectName("sidebar_logo"); logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)
        sidebar_items = [("AI Niche Finder", True), ("Dashboard", False), ("Keywords", False), ("Custom Keywords", False), ("Channels", False), ("Saved", False), ("RPM Predictor", False), ("NexLev AI", False)]
        for text, active in sidebar_items:
            btn = QToolButton(); btn.setObjectName("sidebar_btn"); btn.setProperty("active", active); btn.setText(text); btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            layout.addWidget(btn)
            btn.style().unpolish(btn); btn.style().polish(btn)
        layout.addStretch()
        return frame

    def _build_topbar(self):
        container = QFrame()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        search_row = QHBoxLayout(); search_row.setSpacing(12)
        self.cmb_search_mode = QComboBox(); self.cmb_search_mode.addItems(["Keyword", "Channel"]); self.cmb_search_mode.currentTextChanged.connect(self._on_search_mode_changed); self.cmb_search_mode.setFixedWidth(130)
        search_row.addWidget(self.cmb_search_mode)
        self.search_input = QLineEdit(); self.search_input.setPlaceholderText("Search a keyword..."); self.search_input.returnPressed.connect(self._apply_filters)
        search_row.addWidget(self.search_input, 1)
        self.btn_search = QPushButton("Search"); self.btn_search.setObjectName("primary_btn"); self.btn_search.clicked.connect(self._apply_filters); search_row.addWidget(self.btn_search)
        self.btn_advanced = QPushButton("Advanced Filters"); self.btn_advanced.setObjectName("ghost_btn"); self.btn_advanced.clicked.connect(self._open_advanced_filters); search_row.addWidget(self.btn_advanced)
        self.btn_reset = QPushButton("Reset Filters"); self.btn_reset.setObjectName("ghost_btn"); self.btn_reset.clicked.connect(self._reset_filters); search_row.addWidget(self.btn_reset)
        layout.addLayout(search_row)

        controls_row = QHBoxLayout(); controls_row.setSpacing(16)
        self.chk_hide_revealed = QCheckBox("Hide Revealed Channels"); self.chk_hide_revealed.toggled.connect(self._toggle_hide_revealed); controls_row.addWidget(self.chk_hide_revealed)
        self.lbl_scope = QLabel("Mode: AI niche finder"); self.lbl_scope.setObjectName("muted_label"); controls_row.addWidget(self.lbl_scope)
        controls_row.addStretch(); layout.addLayout(controls_row)
        return container

    def _on_search_mode_changed(self, value: str):
        self.current_search_mode = value
        self.search_input.setPlaceholderText("Search a keyword..." if value == "Keyword" else "Search a channel...")
        self._apply_filters()

    def _toggle_hide_revealed(self, checked: bool):
        self.filter_state.hide_revealed_channels = checked
        self._apply_filters()

    def _open_advanced_filters(self):
        dialog = AdvancedFiltersDialog(categories_from_channels(self.channels), self.filter_state, self)
        if dialog.exec():
            new_state = dialog.build_state()
            new_state.hide_revealed_channels = self.chk_hide_revealed.isChecked()
            self.filter_state = new_state
            self._apply_filters()

    def _reset_filters(self):
        self.filter_state = RPMFilterState()
        self.chk_hide_revealed.setChecked(False)
        self.cmb_search_mode.setCurrentText("Keyword")
        self.search_input.clear()
        self._apply_filters()

    def _apply_filters(self):
        query = self.search_input.text().strip()
        results = self.service.filter_channels(self.current_search_mode, query, self.filter_state)
        self._render_results(results)

    def _render_results(self, channels: Sequence[ChannelRecord]):
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not channels:
            empty = QFrame(); empty.setObjectName("content_card")
            layout = QVBoxLayout(empty); layout.setContentsMargins(24, 24, 24, 24)
            title = QLabel("No channels matched the current filters."); title.setObjectName("section_title"); layout.addWidget(title)
            hint = QLabel("Relax the RPM, revenue, or upload filters and try again."); hint.setObjectName("muted_label"); layout.addWidget(hint)
            self.results_layout.addWidget(empty)
        else:
            for channel in channels:
                card = ChannelCard(channel); card.toggled.connect(self._on_card_toggled); self.results_layout.addWidget(card)
        self.results_layout.addStretch()
        self.footer_label.setText(f"Showing {len(channels)} channel(s) from {len(self.channels)} sample records.")

    def _on_card_toggled(self, title: str, expanded: bool):
        state = "expanded" if expanded else "collapsed"
        window = self.window()
        if hasattr(window, "statusBar"):
            window.statusBar().showMessage(f"{title} {state}.", 2500)
