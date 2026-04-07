from __future__ import annotations

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)

from core.rpm_service import RPMFilterState


class AdvancedFiltersDialog(QDialog):
    def __init__(self, categories: list[str], state: RPMFilterState, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Channel Filters")
        self.resize(1180, 660)
        self.setModal(True)
        self._categories = list(categories)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(18)

        title = QLabel("Channel Filters")
        title.setObjectName("section_title")
        root.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(16)

        self.cmb_category = QComboBox(); self.cmb_category.addItems(self._categories)
        self.sp_sub_min = self._int_spin(0, 10_000_000); self.sp_sub_max = self._int_spin(0, 10_000_000)
        self.dt_first_after = self._date_edit(); self.dt_first_before = self._date_edit()
        self.dt_last_after = self._date_edit(); self.dt_last_before = self._date_edit()
        self.sp_rpm_min = self._float_spin(0.0, 100.0, 0.1); self.sp_rpm_max = self._float_spin(0.0, 100.0, 0.1)
        self.sp_rev_total_min = self._int_spin(0, 10_000_000); self.sp_rev_total_max = self._int_spin(0, 10_000_000)
        self.sp_rev_month_min = self._int_spin(0, 1_000_000); self.sp_rev_month_max = self._int_spin(0, 1_000_000)
        self.sp_total_views_min = self._int_spin(0, 2_000_000_000); self.sp_total_views_max = self._int_spin(0, 2_000_000_000)
        self.sp_views_month_min = self._int_spin(0, 200_000_000); self.sp_views_month_max = self._int_spin(0, 200_000_000)
        self.sp_avg_views_min = self._int_spin(0, 10_000_000); self.sp_avg_views_max = self._int_spin(0, 10_000_000)
        self.sp_median_views_min = self._int_spin(0, 10_000_000); self.sp_median_views_max = self._int_spin(0, 10_000_000)
        self.sp_uploads_min = self._int_spin(0, 5_000); self.sp_uploads_max = self._int_spin(0, 5_000)
        self.sp_uploads_week_min = self._float_spin(0.0, 50.0, 0.1); self.sp_uploads_week_max = self._float_spin(0.0, 50.0, 0.1)
        self.sp_avg_len_min = self._float_spin(0.0, 180.0, 0.1); self.sp_avg_len_max = self._float_spin(0.0, 180.0, 0.1)
        self.grp_monetized, self.rad_monetized_all, self.rad_monetized_yes, self.rad_monetized_no = self._radio_group("Monetized")
        self.grp_shorts, self.rad_shorts_all, self.rad_shorts_yes, self.rad_shorts_no = self._radio_group("Shorts")

        grid.addWidget(self._field_group("Channel category", self.cmb_category), 0, 0)
        grid.addWidget(self._range_group("Subscriber count", self.sp_sub_min, self.sp_sub_max), 0, 1)
        grid.addWidget(self._date_range_group("First video upload date", self.dt_first_after, self.dt_first_before), 0, 2)
        grid.addWidget(self._date_range_group("Last video uploaded", self.dt_last_after, self.dt_last_before), 0, 3)
        grid.addWidget(self._range_group("RPM", self.sp_rpm_min, self.sp_rpm_max), 1, 0)
        grid.addWidget(self._range_group("Revenue generated", self.sp_rev_total_min, self.sp_rev_total_max), 1, 1)
        grid.addWidget(self._range_group("Revenue per month", self.sp_rev_month_min, self.sp_rev_month_max), 1, 2)
        grid.addWidget(self._range_group("Total channel views", self.sp_total_views_min, self.sp_total_views_max), 1, 3)
        grid.addWidget(self._range_group("Views per month", self.sp_views_month_min, self.sp_views_month_max), 2, 0)
        grid.addWidget(self._range_group("Average views", self.sp_avg_views_min, self.sp_avg_views_max), 2, 1)
        grid.addWidget(self._range_group("Median views", self.sp_median_views_min, self.sp_median_views_max), 2, 2)
        grid.addWidget(self._range_group("Videos uploaded", self.sp_uploads_min, self.sp_uploads_max), 2, 3)
        grid.addWidget(self._range_group("Uploads per week", self.sp_uploads_week_min, self.sp_uploads_week_max), 3, 0)
        grid.addWidget(self._range_group("Average video length (minutes)", self.sp_avg_len_min, self.sp_avg_len_max), 3, 1)
        grid.addWidget(self.grp_monetized, 3, 2)
        grid.addWidget(self.grp_shorts, 3, 3)
        root.addLayout(grid)

        actions = QHBoxLayout(); actions.addStretch()
        btn_reset = QPushButton("Reset"); btn_reset.setObjectName("ghost_btn"); btn_reset.clicked.connect(self._reset_defaults); actions.addWidget(btn_reset)
        btn_cancel = QPushButton("Cancel"); btn_cancel.setObjectName("ghost_btn"); btn_cancel.clicked.connect(self.reject); actions.addWidget(btn_cancel)
        btn_apply = QPushButton("Go"); btn_apply.setObjectName("accent_btn"); btn_apply.clicked.connect(self.accept); actions.addWidget(btn_apply)
        root.addLayout(actions)

        self.set_state(state)

    def _field_group(self, title: str, widget):
        box = QGroupBox(title)
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

    def _date_range_group(self, title: str, from_widget, to_widget):
        box = QGroupBox(title)
        layout = QGridLayout(box)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setHorizontalSpacing(10)
        layout.addWidget(QLabel("After"), 0, 0)
        layout.addWidget(from_widget, 1, 0)
        layout.addWidget(QLabel("Before"), 0, 1)
        layout.addWidget(to_widget, 1, 1)
        return box

    def _radio_group(self, title: str):
        box = QGroupBox(title)
        layout = QHBoxLayout(box)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(18)
        group = QButtonGroup(box)
        rad_all = QRadioButton("All"); rad_yes = QRadioButton("Yes"); rad_no = QRadioButton("No")
        group.addButton(rad_all); group.addButton(rad_yes); group.addButton(rad_no)
        layout.addWidget(rad_all); layout.addWidget(rad_yes); layout.addWidget(rad_no); layout.addStretch()
        return box, rad_all, rad_yes, rad_no

    @staticmethod
    def _int_spin(minimum: int, maximum: int):
        widget = QSpinBox(); widget.setRange(minimum, maximum); widget.setGroupSeparatorShown(True); widget.setAccelerated(True); return widget

    @staticmethod
    def _float_spin(minimum: float, maximum: float, step: float):
        widget = QDoubleSpinBox(); widget.setRange(minimum, maximum); widget.setDecimals(1); widget.setSingleStep(step); widget.setAccelerated(True); return widget

    @staticmethod
    def _date_edit():
        widget = QDateEdit(); widget.setCalendarPopup(True); widget.setDisplayFormat("yyyy-MM-dd"); widget.setSpecialValueText("Any")
        widget.setDate(QDate(2000, 1, 1)); widget.setMinimumDate(QDate(2000, 1, 1)); widget.setMaximumDate(QDate(2100, 12, 31)); widget.setDate(widget.minimumDate())
        return widget

    def set_state(self, state: RPMFilterState):
        self.cmb_category.setCurrentText(state.category if state.category in self._categories else "All Categories")
        self.sp_sub_min.setValue(state.subscriber_min); self.sp_sub_max.setValue(state.subscriber_max)
        self.sp_rpm_min.setValue(state.rpm_min); self.sp_rpm_max.setValue(state.rpm_max)
        self.sp_rev_total_min.setValue(state.revenue_generated_min); self.sp_rev_total_max.setValue(state.revenue_generated_max)
        self.sp_rev_month_min.setValue(state.revenue_per_month_min); self.sp_rev_month_max.setValue(state.revenue_per_month_max)
        self.sp_total_views_min.setValue(state.total_views_min); self.sp_total_views_max.setValue(state.total_views_max)
        self.sp_views_month_min.setValue(state.views_per_month_min); self.sp_views_month_max.setValue(state.views_per_month_max)
        self.sp_avg_views_min.setValue(state.average_views_min); self.sp_avg_views_max.setValue(state.average_views_max)
        self.sp_median_views_min.setValue(state.median_views_min); self.sp_median_views_max.setValue(state.median_views_max)
        self.sp_uploads_min.setValue(state.uploads_min); self.sp_uploads_max.setValue(state.uploads_max)
        self.sp_uploads_week_min.setValue(state.uploads_per_week_min); self.sp_uploads_week_max.setValue(state.uploads_per_week_max)
        self.sp_avg_len_min.setValue(state.avg_video_length_min); self.sp_avg_len_max.setValue(state.avg_video_length_max)
        self._set_optional_date(self.dt_first_after, state.first_upload_after)
        self._set_optional_date(self.dt_first_before, state.first_upload_before)
        self._set_optional_date(self.dt_last_after, state.last_upload_after)
        self._set_optional_date(self.dt_last_before, state.last_upload_before)
        self._set_radio(self.rad_monetized_all, self.rad_monetized_yes, self.rad_monetized_no, state.monetized)
        self._set_radio(self.rad_shorts_all, self.rad_shorts_yes, self.rad_shorts_no, state.shorts)

    def _reset_defaults(self):
        self.set_state(RPMFilterState())

    @staticmethod
    def _set_optional_date(widget: QDateEdit, value):
        if value is None:
            widget.setDate(widget.minimumDate())
        else:
            widget.setDate(QDate(value.year, value.month, value.day))

    @staticmethod
    def _set_radio(rad_all, rad_yes, rad_no, value: str):
        if value == "Yes":
            rad_yes.setChecked(True)
        elif value == "No":
            rad_no.setChecked(True)
        else:
            rad_all.setChecked(True)

    @staticmethod
    def _read_optional_date(widget: QDateEdit):
        return None if widget.date() == widget.minimumDate() else widget.date().toPyDate()

    def build_state(self) -> RPMFilterState:
        return RPMFilterState(
            category=self.cmb_category.currentText(),
            subscriber_min=self.sp_sub_min.value(), subscriber_max=self.sp_sub_max.value(),
            first_upload_after=self._read_optional_date(self.dt_first_after), first_upload_before=self._read_optional_date(self.dt_first_before),
            last_upload_after=self._read_optional_date(self.dt_last_after), last_upload_before=self._read_optional_date(self.dt_last_before),
            rpm_min=self.sp_rpm_min.value(), rpm_max=self.sp_rpm_max.value(),
            revenue_generated_min=self.sp_rev_total_min.value(), revenue_generated_max=self.sp_rev_total_max.value(),
            revenue_per_month_min=self.sp_rev_month_min.value(), revenue_per_month_max=self.sp_rev_month_max.value(),
            total_views_min=self.sp_total_views_min.value(), total_views_max=self.sp_total_views_max.value(),
            views_per_month_min=self.sp_views_month_min.value(), views_per_month_max=self.sp_views_month_max.value(),
            average_views_min=self.sp_avg_views_min.value(), average_views_max=self.sp_avg_views_max.value(),
            median_views_min=self.sp_median_views_min.value(), median_views_max=self.sp_median_views_max.value(),
            uploads_min=self.sp_uploads_min.value(), uploads_max=self.sp_uploads_max.value(),
            uploads_per_week_min=self.sp_uploads_week_min.value(), uploads_per_week_max=self.sp_uploads_week_max.value(),
            avg_video_length_min=self.sp_avg_len_min.value(), avg_video_length_max=self.sp_avg_len_max.value(),
            monetized="Yes" if self.rad_monetized_yes.isChecked() else "No" if self.rad_monetized_no.isChecked() else "All",
            shorts="Yes" if self.rad_shorts_yes.isChecked() else "No" if self.rad_shorts_no.isChecked() else "All",
        )
