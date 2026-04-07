from __future__ import annotations

from typing import Sequence

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.rpm_data import ChannelRecord, build_sample_channels
from core.rpm_service import RPMFilterState, RPMFinderService, categories_from_channels
from ui.channel_card import ChannelCard


class ChannelsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.channels = build_sample_channels()
        self.service = RPMFinderService(self.channels)
        self.filter_state = RPMFilterState()
        self.current_search_mode = "Keyword"

        root = QHBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

        root.addWidget(self._build_filter_sidebar())
        root.addWidget(self._build_results_area(), 1)

        self._sync_controls_from_state()
        self._apply_filters()

    def _build_filter_sidebar(self):
        frame = QFrame()
        frame.setObjectName("content_card")
        frame.setFixedWidth(340)

        outer = QVBoxLayout(frame)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QLabel("Channels Filters")
        title.setObjectName("section_title")
        layout.addWidget(title)

        template_box = self._section_frame("Filter Template")
        template_layout = QVBoxLayout(template_box)
        template_layout.setContentsMargins(14, 14, 14, 14)
        template_layout.setSpacing(10)
        self.cmb_template = QComboBox()
        self.cmb_template.addItems(["Default", "High RPM", "Evergreen", "Low Competition"])
        template_layout.addWidget(self.cmb_template)
        template_actions = QHBoxLayout()
        self.btn_apply_template = QPushButton("Apply")
        self.btn_apply_template.setObjectName("accent_btn")
        self.btn_apply_template.clicked.connect(self._apply_template)
        self.btn_reset_sidebar = QPushButton("Reset")
        self.btn_reset_sidebar.setObjectName("ghost_btn")
        self.btn_reset_sidebar.clicked.connect(self._reset_filters)
        template_actions.addWidget(self.btn_apply_template)
        template_actions.addWidget(self.btn_reset_sidebar)
        template_layout.addLayout(template_actions)
        layout.addWidget(template_box)

        self.cmb_category = QComboBox()
        self.cmb_category.addItems(categories_from_channels(self.channels))
        layout.addWidget(self._single_field_group("Channel Category", self.cmb_category))

        self.sp_sub_min = self._int_spin(0, 10_000_000)
        self.sp_sub_max = self._int_spin(0, 10_000_000)
        layout.addWidget(self._range_group("Subscriber Count", self.sp_sub_min, self.sp_sub_max))

        self.dt_first_after = self._date_edit()
        self.dt_first_before = self._date_edit()
        layout.addWidget(self._date_group("First Upload Date", self.dt_first_after, self.dt_first_before))

        self.dt_last_after = self._date_edit()
        self.dt_last_before = self._date_edit()
        layout.addWidget(self._date_group("Last Upload Date", self.dt_last_after, self.dt_last_before))

        self.sp_rpm_min = self._float_spin(0.0, 100.0, 0.1)
        self.sp_rpm_max = self._float_spin(0.0, 100.0, 0.1)
        layout.addWidget(self._range_group("RPM", self.sp_rpm_min, self.sp_rpm_max))

        self.sp_rev_total_min = self._int_spin(0, 10_000_000)
        self.sp_rev_total_max = self._int_spin(0, 10_000_000)
        layout.addWidget(self._range_group("Revenue Generated", self.sp_rev_total_min, self.sp_rev_total_max))

        self.sp_rev_month_min = self._int_spin(0, 1_000_000)
        self.sp_rev_month_max = self._int_spin(0, 1_000_000)
        layout.addWidget(self._range_group("Revenue Per Month", self.sp_rev_month_min, self.sp_rev_month_max))

        self.sp_total_views_min = self._int_spin(0, 2_000_000_000)
        self.sp_total_views_max = self._int_spin(0, 2_000_000_000)
        layout.addWidget(self._range_group("Total Channel Views", self.sp_total_views_min, self.sp_total_views_max))

        self.sp_views_month_min = self._int_spin(0, 200_000_000)
        self.sp_views_month_max = self._int_spin(0, 200_000_000)
        layout.addWidget(self._range_group("Views Per Month", self.sp_views_month_min, self.sp_views_month_max))

        self.sp_avg_views_min = self._int_spin(0, 10_000_000)
        self.sp_avg_views_max = self._int_spin(0, 10_000_000)
        layout.addWidget(self._range_group("Average Views", self.sp_avg_views_min, self.sp_avg_views_max))

        self.sp_median_views_min = self._int_spin(0, 10_000_000)
        self.sp_median_views_max = self._int_spin(0, 10_000_000)
        layout.addWidget(self._range_group("Median Views", self.sp_median_views_min, self.sp_median_views_max))

        self.sp_uploads_min = self._int_spin(0, 5_000)
        self.sp_uploads_max = self._int_spin(0, 5_000)
        layout.addWidget(self._range_group("Videos Uploaded", self.sp_uploads_min, self.sp_uploads_max))

        self.sp_uploads_week_min = self._float_spin(0.0, 50.0, 0.1)
        self.sp_uploads_week_max = self._float_spin(0.0, 50.0, 0.1)
        layout.addWidget(self._range_group("Uploads Per Week", self.sp_uploads_week_min, self.sp_uploads_week_max))

        self.sp_avg_len_min = self._float_spin(0.0, 180.0, 0.1)
        self.sp_avg_len_max = self._float_spin(0.0, 180.0, 0.1)
        layout.addWidget(self._range_group("Avg. Video Length (min)", self.sp_avg_len_min, self.sp_avg_len_max))

        self.cmb_monetized = QComboBox()
        self.cmb_monetized.addItems(["All", "Yes", "No"])
        layout.addWidget(self._single_field_group("Monetized", self.cmb_monetized))

        self.cmb_shorts = QComboBox()
        self.cmb_shorts.addItems(["All", "Yes", "No"])
        layout.addWidget(self._single_field_group("Has Shorts", self.cmb_shorts))

        self.chk_hide_revealed = QCheckBox("Hide Revealed Channels")
        self.chk_hide_revealed.toggled.connect(self._apply_filters)
        layout.addWidget(self.chk_hide_revealed)

        layout.addStretch()
        scroll.setWidget(host)
        outer.addWidget(scroll)
        return frame

    def _build_results_area(self):
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        topbar = QFrame()
        topbar.setObjectName("topbar")
        top_layout = QVBoxLayout(topbar)
        top_layout.setContentsMargins(18, 18, 18, 18)
        top_layout.setSpacing(12)

        title = QLabel("Channels")
        title.setObjectName("app_title")
        top_layout.addWidget(title)

        search_row = QHBoxLayout()
        search_row.setSpacing(12)
        self.cmb_search_mode = QComboBox()
        self.cmb_search_mode.addItems(["Keyword", "Channel"])
        self.cmb_search_mode.setFixedWidth(130)
        self.cmb_search_mode.currentTextChanged.connect(self._on_search_mode_changed)
        search_row.addWidget(self.cmb_search_mode)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search a keyword...")
        self.search_input.returnPressed.connect(self._apply_filters)
        search_row.addWidget(self.search_input, 1)
        self.btn_search = QPushButton("Search")
        self.btn_search.setObjectName("primary_btn")
        self.btn_search.clicked.connect(self._apply_filters)
        search_row.addWidget(self.btn_search)
        self.btn_refresh = QPushButton("Refresh Results")
        self.btn_refresh.setObjectName("ghost_btn")
        self.btn_refresh.clicked.connect(self._apply_filters)
        search_row.addWidget(self.btn_refresh)
        top_layout.addLayout(search_row)

        hint_row = QHBoxLayout()
        self.lbl_scope = QLabel("Mode: Channels page with fixed filter sidebar")
        self.lbl_scope.setObjectName("muted_label")
        hint_row.addWidget(self.lbl_scope)
        hint_row.addStretch()
        top_layout.addLayout(hint_row)
        layout.addWidget(topbar)

        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.results_host = QWidget()
        self.results_layout = QVBoxLayout(self.results_host)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(18)
        self.results_scroll.setWidget(self.results_host)
        layout.addWidget(self.results_scroll, 1)

        self.footer_label = QLabel("")
        self.footer_label.setObjectName("muted_label")
        layout.addWidget(self.footer_label)
        return wrap

    def _section_frame(self, title: str):
        frame = QGroupBox(title)
        return frame

    def _single_field_group(self, title: str, widget):
        box = QGroupBox(title)
        box.setFlat(False)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.addWidget(widget)
        return box

    def _range_group(self, title: str, low_widget, high_widget):
        box = QGroupBox(title)
        layout = QGridLayout(box)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setHorizontalSpacing(10)
        layout.addWidget(QLabel("Min"), 0, 0)
        layout.addWidget(low_widget, 1, 0)
        layout.addWidget(QLabel("Max"), 0, 1)
        layout.addWidget(high_widget, 1, 1)
        return box

    def _date_group(self, title: str, from_widget, to_widget):
        box = QGroupBox(title)
        layout = QGridLayout(box)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setHorizontalSpacing(10)
        layout.addWidget(QLabel("After"), 0, 0)
        layout.addWidget(from_widget, 1, 0)
        layout.addWidget(QLabel("Before"), 0, 1)
        layout.addWidget(to_widget, 1, 1)
        return box

    @staticmethod
    def _int_spin(minimum: int, maximum: int):
        widget = QSpinBox()
        widget.setRange(minimum, maximum)
        widget.setGroupSeparatorShown(True)
        widget.setAccelerated(True)
        return widget

    @staticmethod
    def _float_spin(minimum: float, maximum: float, step: float):
        widget = QDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setDecimals(1)
        widget.setSingleStep(step)
        widget.setAccelerated(True)
        return widget

    @staticmethod
    def _date_edit():
        widget = QDateEdit()
        widget.setCalendarPopup(True)
        widget.setDisplayFormat("yyyy-MM-dd")
        widget.setSpecialValueText("Any")
        widget.setDate(QDate(2000, 1, 1))
        widget.setMinimumDate(QDate(2000, 1, 1))
        widget.setMaximumDate(QDate(2100, 12, 31))
        widget.setDate(widget.minimumDate())
        return widget

    def _apply_template(self):
        template = self.cmb_template.currentText()
        state = RPMFilterState()
        if template == "High RPM":
            state.rpm_min = 4.0
            state.revenue_per_month_min = 5_000
            state.average_views_min = 100_000
        elif template == "Evergreen":
            state.category = "History"
            state.last_upload_after = None
            state.avg_video_length_min = 8.0
            state.avg_video_length_max = 20.0
        elif template == "Low Competition":
            state.subscriber_max = 180_000
            state.average_views_min = 70_000
            state.uploads_max = 600
        self.filter_state = state
        self._sync_controls_from_state()
        self._apply_filters()

    def _sync_controls_from_state(self):
        state = self.filter_state
        self.cmb_category.setCurrentText(state.category if self.cmb_category.findText(state.category) >= 0 else "All Categories")
        self.sp_sub_min.setValue(state.subscriber_min)
        self.sp_sub_max.setValue(state.subscriber_max)
        self._set_optional_date(self.dt_first_after, state.first_upload_after)
        self._set_optional_date(self.dt_first_before, state.first_upload_before)
        self._set_optional_date(self.dt_last_after, state.last_upload_after)
        self._set_optional_date(self.dt_last_before, state.last_upload_before)
        self.sp_rpm_min.setValue(state.rpm_min)
        self.sp_rpm_max.setValue(state.rpm_max)
        self.sp_rev_total_min.setValue(state.revenue_generated_min)
        self.sp_rev_total_max.setValue(state.revenue_generated_max)
        self.sp_rev_month_min.setValue(state.revenue_per_month_min)
        self.sp_rev_month_max.setValue(state.revenue_per_month_max)
        self.sp_total_views_min.setValue(state.total_views_min)
        self.sp_total_views_max.setValue(state.total_views_max)
        self.sp_views_month_min.setValue(state.views_per_month_min)
        self.sp_views_month_max.setValue(state.views_per_month_max)
        self.sp_avg_views_min.setValue(state.average_views_min)
        self.sp_avg_views_max.setValue(state.average_views_max)
        self.sp_median_views_min.setValue(state.median_views_min)
        self.sp_median_views_max.setValue(state.median_views_max)
        self.sp_uploads_min.setValue(state.uploads_min)
        self.sp_uploads_max.setValue(state.uploads_max)
        self.sp_uploads_week_min.setValue(state.uploads_per_week_min)
        self.sp_uploads_week_max.setValue(state.uploads_per_week_max)
        self.sp_avg_len_min.setValue(state.avg_video_length_min)
        self.sp_avg_len_max.setValue(state.avg_video_length_max)
        self.cmb_monetized.setCurrentText(state.monetized)
        self.cmb_shorts.setCurrentText(state.shorts)
        self.chk_hide_revealed.setChecked(state.hide_revealed_channels)

    @staticmethod
    def _set_optional_date(widget: QDateEdit, value):
        if value is None:
            widget.setDate(widget.minimumDate())
        else:
            widget.setDate(QDate(value.year, value.month, value.day))

    @staticmethod
    def _read_optional_date(widget: QDateEdit):
        return None if widget.date() == widget.minimumDate() else widget.date().toPyDate()

    def _on_search_mode_changed(self, value: str):
        self.current_search_mode = value
        self.search_input.setPlaceholderText("Search a keyword..." if value == "Keyword" else "Search a channel...")

    def _build_state_from_controls(self) -> RPMFilterState:
        return RPMFilterState(
            category=self.cmb_category.currentText(),
            subscriber_min=self.sp_sub_min.value(),
            subscriber_max=self.sp_sub_max.value(),
            first_upload_after=self._read_optional_date(self.dt_first_after),
            first_upload_before=self._read_optional_date(self.dt_first_before),
            last_upload_after=self._read_optional_date(self.dt_last_after),
            last_upload_before=self._read_optional_date(self.dt_last_before),
            rpm_min=self.sp_rpm_min.value(),
            rpm_max=self.sp_rpm_max.value(),
            revenue_generated_min=self.sp_rev_total_min.value(),
            revenue_generated_max=self.sp_rev_total_max.value(),
            revenue_per_month_min=self.sp_rev_month_min.value(),
            revenue_per_month_max=self.sp_rev_month_max.value(),
            total_views_min=self.sp_total_views_min.value(),
            total_views_max=self.sp_total_views_max.value(),
            views_per_month_min=self.sp_views_month_min.value(),
            views_per_month_max=self.sp_views_month_max.value(),
            average_views_min=self.sp_avg_views_min.value(),
            average_views_max=self.sp_avg_views_max.value(),
            median_views_min=self.sp_median_views_min.value(),
            median_views_max=self.sp_median_views_max.value(),
            uploads_min=self.sp_uploads_min.value(),
            uploads_max=self.sp_uploads_max.value(),
            uploads_per_week_min=self.sp_uploads_week_min.value(),
            uploads_per_week_max=self.sp_uploads_week_max.value(),
            avg_video_length_min=self.sp_avg_len_min.value(),
            avg_video_length_max=self.sp_avg_len_max.value(),
            monetized=self.cmb_monetized.currentText(),
            shorts=self.cmb_shorts.currentText(),
            hide_revealed_channels=self.chk_hide_revealed.isChecked(),
        )

    def _reset_filters(self):
        self.filter_state = RPMFilterState()
        self.search_input.clear()
        self.cmb_search_mode.setCurrentText("Keyword")
        self._sync_controls_from_state()
        self._apply_filters()

    def _apply_filters(self):
        self.filter_state = self._build_state_from_controls()
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
            empty = QFrame()
            empty.setObjectName("content_card")
            layout = QVBoxLayout(empty)
            layout.setContentsMargins(24, 24, 24, 24)
            title = QLabel("No channels matched the current sidebar filters.")
            title.setObjectName("section_title")
            layout.addWidget(title)
            hint = QLabel("Relax the revenue, RPM, upload, or date filters and try again.")
            hint.setObjectName("muted_label")
            layout.addWidget(hint)
            self.results_layout.addWidget(empty)
        else:
            for channel in channels:
                card = ChannelCard(channel, start_expanded=True)
                card.toggled.connect(self._on_card_toggled)
                self.results_layout.addWidget(card)

        self.results_layout.addStretch()
        self.footer_label.setText(f"Showing {len(channels)} channel(s) from {len(self.channels)} sample records.")

    def _on_card_toggled(self, title: str, expanded: bool):
        state = "expanded" if expanded else "collapsed"
        window = self.window()
        if hasattr(window, "statusBar"):
            window.statusBar().showMessage(f"{title} {state}.", 2500)
