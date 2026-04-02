import webbrowser
import sys
from datetime import datetime, timedelta
from urllib.parse import urlencode

import numpy as np
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QHeaderView,
    QWidget,
    QCheckBox,
    QMenu,
    QSpinBox,
)

from core.trends_fetcher import TrendsFetcherWorker
from utils.constants import COUNTRY_LIST, GEO_MAP, TIME_MAP

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    _QTWEBENGINE_IMPORT_ERROR = ""
except Exception as _qtwebengine_exc:
    QWebEngineView = None
    _QTWEBENGINE_IMPORT_ERROR = str(_qtwebengine_exc)


def build_daily_series(raw_data):
    day_value_map = {}
    for point in raw_data or []:
        point_date = str(point.get("date", "")).strip()
        point_value = point.get("value")
        if not point_date or point_value is None:
            continue

        parsed_date = None
        try:
            parsed_date = datetime.strptime(point_date, "%Y-%m-%d")
        except ValueError:
            try:
                parsed_date = datetime.fromisoformat(point_date)
            except ValueError:
                parsed_date = None

        if parsed_date is None:
            continue

        try:
            day_value_map[parsed_date.date()] = float(point_value)
        except (TypeError, ValueError):
            continue

    if not day_value_map:
        return [], []

    sorted_days = sorted(day_value_map.keys())
    base_dates = [datetime.combine(day, datetime.min.time()) for day in sorted_days]
    base_values = np.array([day_value_map[day] for day in sorted_days], dtype=float)

    if len(base_dates) == 1:
        return base_dates, [float(base_values[0])]

    start_day = sorted_days[0]
    end_day = sorted_days[-1]
    day_count = (end_day - start_day).days + 1
    daily_dates = [
        datetime.combine(start_day + timedelta(days=idx), datetime.min.time())
        for idx in range(day_count)
    ]

    x_known = np.array([dt.toordinal() for dt in base_dates], dtype=float)
    x_full = np.array([dt.toordinal() for dt in daily_dates], dtype=float)
    y_full = np.interp(x_full, x_known, base_values)

    return daily_dates, y_full.astype(float).tolist()


class TrendChartDialog(QDialog):
    def __init__(self, keyword, raw_data, google_trends_url, dark_theme=True, parent=None):
        super().__init__(parent)
        self.keyword = keyword
        self.raw_data = raw_data or []
        self.google_trends_url = google_trends_url
        self.dark_theme = bool(dark_theme)
        self.figure = None
        self.axis = None
        self.canvas = None

        self.setWindowTitle(f"Searches Over Time - {self.keyword}")
        self.setModal(True)
        self.resize(920, 560)
        if self.dark_theme:
            self.setStyleSheet(
                """
                QDialog { background-color: #121212; color: #f2f2f2; }
                QPushButton {
                    background-color: #e50914;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-weight: 600;
                    padding: 4px 12px;
                }
                QPushButton:hover { background-color: #ff1a25; }
                QPushButton:disabled { background-color: #5a5a5a; color: #cccccc; }
                QCheckBox { color: #f2f2f2; font-weight: 600; }
                """
            )
        else:
            self.setStyleSheet(
                """
                QDialog { background-color: #f2f2f2; color: #222222; }
                QPushButton {
                    background-color: #e50914;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-weight: 600;
                    padding: 4px 12px;
                }
                QPushButton:hover { background-color: #ff1a25; }
                QPushButton:disabled { background-color: #5a5a5a; color: #cccccc; }
                QCheckBox { color: #222222; font-weight: 600; }
                """
            )

        self._build_ui()
        self._draw_chart()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
        except ImportError:
            QMessageBox.warning(
                self,
                "Chart Error",
                "matplotlib is missing. Install it with: pip install matplotlib",
            )
            self.close()
            return

        self.figure, self.axis = plt.subplots(figsize=(10, 5))
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas, stretch=1)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.btn_view_google = QPushButton("View on Google Trends")
        self.btn_view_google.setEnabled(bool(self.google_trends_url))
        self.btn_view_google.clicked.connect(self._open_google_trends)

        self.chk_bar_chart = QCheckBox("Bar Chart")
        self.chk_bar_chart.stateChanged.connect(self._draw_chart)

        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self._save_chart)

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.accept)

        button_layout.addWidget(self.btn_view_google)
        button_layout.addStretch()
        button_layout.addWidget(self.chk_bar_chart)
        button_layout.addWidget(self.btn_save)
        button_layout.addWidget(self.btn_close)
        layout.addLayout(button_layout)

    def _prepare_series(self):
        return build_daily_series(self.raw_data)

    def _draw_chart(self):
        if self.axis is None or self.canvas is None:
            return

        import matplotlib.dates as mdates

        dates, values = self._prepare_series()
        self.axis.clear()

        if self.dark_theme:
            fig_bg = "#121212"
            axis_bg = "#1a1a1a"
            line_color = "#ff3b3b"
            marker_face = "#ff4a4a"
            marker_edge = "#b71c1c"
            annotation_color = "#f3f3f3"
            title_color = "#f2f2f2"
            x_label_color = "#d4d4d4"
            axis_edge = "#4a4a4a"
            empty_color = "#bcbcbc"
            tick_color = "#d0d0d0"
        else:
            fig_bg = "#ffffff"
            axis_bg = "#ffffff"
            line_color = "#c5302c"
            marker_face = "#f44336"
            marker_edge = "#b71c1c"
            annotation_color = "#303030"
            title_color = "#222222"
            x_label_color = "#333333"
            axis_edge = "#c8c8c8"
            empty_color = "#555555"
            tick_color = "#444444"

        self.figure.patch.set_facecolor(fig_bg)
        self.axis.set_facecolor(axis_bg)

        if dates and values:
            if self.chk_bar_chart.isChecked():
                self.axis.bar(dates, values, color="#e50914", alpha=0.95, width=0.8)
            else:
                self.axis.plot(
                    dates,
                    values,
                    color=line_color,
                    linewidth=2.0,
                    marker="o",
                    markersize=7,
                    markerfacecolor=marker_face,
                    markeredgecolor=marker_edge,
                    markeredgewidth=1.4,
                )

            annotate_step = 1 if len(values) <= 60 else max(1, len(values) // 30)
            for idx, (x_point, y_point) in enumerate(zip(dates, values)):
                if idx % annotate_step != 0 and idx != len(values) - 1:
                    continue
                self.axis.annotate(
                    f"{int(round(y_point))}",
                    xy=(x_point, y_point),
                    xytext=(0, 8),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=8.5,
                    color=annotation_color,
                    fontweight="semibold",
                )
        else:
            self.axis.text(
                0.5,
                0.5,
                "No trend data available.",
                transform=self.axis.transAxes,
                ha="center",
                va="center",
                color=empty_color,
            )

        self.axis.set_title(
            f"Worldwide Search Trends Over Time for {self.keyword}",
            color=title_color,
            pad=10,
            fontsize=11,
            fontweight="semibold",
        )
        self.axis.set_xlabel("Date", color=x_label_color, labelpad=10)
        self.axis.set_ylabel("")
        self.axis.set_ylim(0, 100)
        self.axis.grid(False)

        for spine in self.axis.spines.values():
            spine.set_color(axis_edge)
        self.axis.spines["top"].set_visible(False)
        self.axis.spines["right"].set_visible(False)
        self.axis.spines["left"].set_visible(False)
        self.axis.tick_params(axis="x", colors=tick_color, labelsize=8)
        self.axis.tick_params(axis="y", left=False, labelleft=False)

        if dates:
            if len(dates) <= 35:
                tick_step = 1
            elif len(dates) <= 120:
                tick_step = 3
            elif len(dates) <= 370:
                tick_step = 7
            else:
                tick_step = max(1, len(dates) // 24)

            tick_dates = dates[::tick_step]
            if dates[-1] not in tick_dates:
                tick_dates.append(dates[-1])
            tick_labels = [dt.strftime("%b %d").replace(" 0", " ") for dt in tick_dates]
            self.axis.set_xticks(tick_dates)
            self.axis.set_xticklabels(tick_labels, rotation=90, ha="center")

        self.axis.margins(x=0.01)

        if not dates:
            locator = mdates.AutoDateLocator()
            formatter = mdates.ConciseDateFormatter(locator)
            self.axis.xaxis.set_major_locator(locator)
            self.axis.xaxis.set_major_formatter(formatter)

        self.figure.tight_layout(rect=[0.02, 0.06, 0.98, 0.97])
        self.canvas.draw_idle()

    def _open_google_trends(self):
        if self.google_trends_url:
            webbrowser.open(self.google_trends_url)

    def _save_chart(self):
        if self.figure is None:
            return
        default_name = f"{self.keyword.strip().replace(' ', '_') or 'trend_chart'}.png"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Chart",
            default_name,
            "PNG Files (*.png)",
        )
        if not path:
            return

        try:
            self.figure.savefig(path, dpi=160, facecolor=self.figure.get_facecolor(), bbox_inches="tight")
        except Exception as exc:
            QMessageBox.warning(self, "Save Error", f"Failed to save chart: {exc}")


class TrendsSettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Trends Tool Settings")
        self.setModal(True)
        self.resize(560, 310)
        self.setStyleSheet(
            """
            QDialog { background-color: #1c1c1c; color: #f2f2f2; }
            QLabel { color: #f2f2f2; }
            QSpinBox {
                background-color: #2a2a2a;
                color: #ffffff;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 4px 6px;
                min-width: 70px;
            }
            QCheckBox { color: #f2f2f2; spacing: 8px; }
            QPushButton {
                background-color: #2c2c2c;
                color: #ffffff;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: 600;
                min-width: 90px;
            }
            QPushButton:hover { background-color: #393939; }
            QPushButton#ok_btn { background-color: #e50914; border: none; }
            QPushButton#ok_btn:hover { background-color: #ff1a25; }
            """
        )

        self._settings = dict(settings)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 14)
        root.setSpacing(14)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("After"))
        self.spin_pause_after = QSpinBox()
        self.spin_pause_after.setRange(1, 10000)
        self.spin_pause_after.setValue(int(self._settings.get("pause_after_connections", 20)))
        row1.addWidget(self.spin_pause_after)
        row1.addWidget(QLabel("web connections, pause from"))
        self.spin_pause_min = QSpinBox()
        self.spin_pause_min.setRange(0, 3600)
        self.spin_pause_min.setValue(int(self._settings.get("pause_min_seconds", 10)))
        row1.addWidget(self.spin_pause_min)
        row1.addWidget(QLabel("to"))
        self.spin_pause_max = QSpinBox()
        self.spin_pause_max.setRange(0, 3600)
        self.spin_pause_max.setValue(int(self._settings.get("pause_max_seconds", 60)))
        row1.addWidget(self.spin_pause_max)
        row1.addWidget(QLabel("seconds"))
        row1.addStretch()
        root.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Maximum concurrent workers"))
        self.spin_workers = QSpinBox()
        self.spin_workers.setRange(1, 2)
        self.spin_workers.setValue(min(2, int(self._settings.get("max_workers", 2))))
        row2.addWidget(self.spin_workers)
        row2.addStretch()
        root.addLayout(row2)

        self.chk_auto_sort = QCheckBox("Auto sort table by Total Average after finishing")
        self.chk_auto_sort.setChecked(bool(self._settings.get("auto_sort_total_average", True)))
        root.addWidget(self.chk_auto_sort)

        self.chk_browser_default = QCheckBox("Enable embedded browser panel by default")
        self.chk_browser_default.setChecked(bool(self._settings.get("enable_embedded_browser_default", False)))
        root.addWidget(self.chk_browser_default)

        self.chk_dark_charts = QCheckBox("Dark theme for charts")
        self.chk_dark_charts.setChecked(bool(self._settings.get("dark_theme_charts", True)))
        root.addWidget(self.chk_dark_charts)

        root.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_ok = QPushButton("OK")
        btn_ok.setObjectName("ok_btn")
        btn_cancel = QPushButton("Cancel")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        root.addLayout(btn_row)

    def get_settings(self):
        pause_min = int(self.spin_pause_min.value())
        pause_max = int(self.spin_pause_max.value())
        if pause_max < pause_min:
            pause_min, pause_max = pause_max, pause_min

        return {
            "pause_after_connections": int(self.spin_pause_after.value()),
            "pause_min_seconds": pause_min,
            "pause_max_seconds": pause_max,
            "max_workers": min(2, int(self.spin_workers.value())),
            "auto_sort_total_average": bool(self.chk_auto_sort.isChecked()),
            "enable_embedded_browser_default": bool(self.chk_browser_default.isChecked()),
            "dark_theme_charts": bool(self.chk_dark_charts.isChecked()),
        }


class TrendsTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._sparkline_cache = {}
        self._worker_status_text = ""
        self.trends_settings = {
            "pause_after_connections": 20,
            "pause_min_seconds": 10,
            "pause_max_seconds": 60,
            "max_workers": 2,
            "auto_sort_total_average": True,
            "enable_embedded_browser_default": False,
            "dark_theme_charts": True,
        }
        self.browser_view = None
        self._webengine_available = False
        self.browser_panel = None
        self.browser_panel_layout = None
        self.browser_placeholder = None
        self._webengine_error = ""
        self.trends_splitter = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(35, 30, 35, 30)
        layout.setSpacing(20)

        header_label = QLabel("Trends Tool")
        header_label.setObjectName("header_label")
        header_label.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        layout.addWidget(header_label)

        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: transparent;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_trends_go = QPushButton("Go")
        self.btn_trends_go.setFixedSize(120, 28)
        self.btn_trends_go.setStyleSheet("background-color: #e50914; color: white; border: none; font-weight: bold; border-radius: 4px;")
        self.btn_trends_go.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_trends_go.clicked.connect(self.start_trends_fetch)

        self.btn_trends_stop = QPushButton("Stop")
        self.btn_trends_stop.setFixedSize(120, 28)
        self.btn_trends_stop.setStyleSheet("background-color: #444444; color: white; border: none; font-weight: bold; border-radius: 4px;")
        self.btn_trends_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_trends_stop.clicked.connect(self.stop_trends_fetch)
        self.btn_trends_stop.hide()

        self.btn_trends_settings = QPushButton("Settings")
        self.btn_trends_settings.setFixedSize(100, 28)
        self.btn_trends_settings.setStyleSheet("background-color: #e50914; color: white; border: none; font-weight: bold; border-radius: 4px;")
        self.btn_trends_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_trends_settings.clicked.connect(self.open_settings_dialog)

        self.btn_trends_browser = QPushButton("Browser")
        self.btn_trends_browser.setFixedSize(100, 28)
        self.btn_trends_browser.setStyleSheet("background-color: #e50914; color: white; border: none; font-weight: bold; border-radius: 4px;")
        self.btn_trends_browser.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_trends_browser.clicked.connect(self.toggle_browser_panel)

        top_layout.addWidget(self.btn_trends_go)
        top_layout.addWidget(self.btn_trends_stop)
        top_layout.addSpacing(140)
        top_layout.addWidget(self.btn_trends_settings)
        top_layout.addStretch()
        top_layout.addWidget(self.btn_trends_browser)

        layout.addWidget(top_bar)

        self.trends_splitter = QSplitter(Qt.Orientation.Horizontal)

        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 5, 10, 0)
        left_layout.setSpacing(12)
        left_panel.setStyleSheet("background-color: transparent;")

        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(8)

        combo_style = "background-color: #ffffff; color: #000000; padding: 4px; border: 1px solid #cccccc; border-radius: 2px; font-size: 12px; min-width: 140px;"
        label_style = "color: #f1f1f1; font-size: 13px;"

        self.t_combo_country = QComboBox()
        self.t_combo_country.addItems(COUNTRY_LIST)
        self.t_combo_country.setMaxVisibleItems(18)
        self.t_combo_country.setStyleSheet(combo_style)
        lbl_country = QLabel("Country:")
        lbl_country.setStyleSheet(label_style)
        form_layout.addRow(lbl_country, self.t_combo_country)

        self.t_combo_period = QComboBox()
        self.t_combo_period.addItems(["Past 30 days", "Past 7 days", "Past 12 months", "2004 - present"])
        self.t_combo_period.setStyleSheet(combo_style)
        lbl_period = QLabel("Time Period:")
        lbl_period.setStyleSheet(label_style)
        form_layout.addRow(lbl_period, self.t_combo_period)

        self.t_combo_cat = QComboBox()
        self.t_combo_cat.addItems(["All Categories", "Arts & Entertainment", "Autos & Vehicles", "Beauty & Fitness", "Games"])
        self.t_combo_cat.setStyleSheet(combo_style)
        lbl_cat = QLabel("Category:")
        lbl_cat.setStyleSheet(label_style)
        form_layout.addRow(lbl_cat, self.t_combo_cat)

        self.t_combo_prop = QComboBox()
        self.t_combo_prop.addItems(["Youtube Search", "Web Search", "Image Search", "News Search", "Google Shopping"])
        self.t_combo_prop.setStyleSheet(combo_style)
        lbl_prop = QLabel("Property:")
        lbl_prop.setStyleSheet(label_style)
        form_layout.addRow(lbl_prop, self.t_combo_prop)

        left_layout.addLayout(form_layout)

        kw_label = QLabel("Enter one keyword per line:")
        kw_label.setStyleSheet("color: #bbbbbb; font-size: 12px; margin-top: 10px;")
        left_layout.addWidget(kw_label)

        self.trends_input = QTextEdit()
        self.trends_input.setStyleSheet("background-color: #ffffff; color: #000000; border: 1px solid #aaa; border-radius: 2px;")
        self.trends_input.setText("diy crafts\ndiy wall decor\ndiy videos\ndiy yarn\ndiy upholstered headboard\ndiy zipline\ndiy tiktok\ndiy aquarium")
        left_layout.addWidget(self.trends_input, stretch=1)

        self.trends_table = QTableWidget()
        self.trends_table.setColumnCount(11)
        headers = [
            "Chart",
            "Keyword",
            "Country",
            "Time Period",
            "Category",
            "Property",
            "Word Count",
            "Character Count",
            "Total Average",
            "Trend Slope",
            "Trending Spike",
        ]
        self.trends_table.setHorizontalHeaderLabels(headers)
        self._setup_trends_table_columns()
        self.trends_table.verticalHeader().setDefaultSectionSize(36)
        self.trends_table.verticalHeader().setVisible(False)
        self.trends_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.trends_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.trends_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.trends_table.customContextMenuRequested.connect(self.show_trends_context_menu)
        self.trends_table.setStyleSheet(
            "QTableWidget { background-color: #ffffff; color: #000000; gridline-color: #dddddd; border: 1px solid #cccccc; } "
            "QHeaderView::section { background-color: #f0f0f0; color: #000000; font-weight: bold; border: 1px solid #cccccc; padding: 4px; }"
        )
        self.trends_table.cellDoubleClicked.connect(self.show_trend_chart)

        self.browser_panel = QFrame()
        self.browser_panel.setMinimumWidth(320)
        self.browser_panel_layout = QVBoxLayout(self.browser_panel)
        self.browser_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.browser_panel_layout.setSpacing(0)
        self.browser_placeholder = QLabel("Browser panel is ready.\nClick Browser to load Google Trends.")
        self.browser_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.browser_placeholder.setStyleSheet("color: #dddddd; background-color: #1f1f1f; border: 1px solid #333333;")
        self.browser_panel_layout.addWidget(self.browser_placeholder)

        self.browser_panel.hide()

        self.trends_splitter.addWidget(left_panel)
        self.trends_splitter.addWidget(self.trends_table)
        self.trends_splitter.addWidget(self.browser_panel)
        self.trends_splitter.setStretchFactor(0, 0)
        self.trends_splitter.setStretchFactor(1, 1)
        self.trends_splitter.setStretchFactor(2, 0)
        self.trends_splitter.setCollapsible(2, True)
        self.trends_splitter.setSizes([260, 980, 0])
        layout.addWidget(self.trends_splitter, stretch=1)

        bottom_toolbar = QFrame()
        b_layout = QHBoxLayout(bottom_toolbar)
        self.t_btn_vol = QPushButton("Volume Data")
        self.t_btn_hash = QPushButton("Hashtags")
        self.t_status = QLabel("Total Items: 0")
        self.t_status.setStyleSheet("color: #bbbbbb; font-weight: bold; font-size: 11px;")
        self.t_btn_file = QPushButton("File")
        self.t_btn_clear = QPushButton("Clear")
        for btn in [self.t_btn_vol, self.t_btn_hash, self.t_btn_file, self.t_btn_clear]:
            btn.setStyleSheet("background-color: #e50914; color: #ffffff; border: none; border-radius: 4px; font-weight: bold; padding: 7px 18px;")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.t_btn_clear.clicked.connect(self.clear_trends_table)
        b_layout.addWidget(self.t_btn_vol)
        b_layout.addWidget(self.t_btn_hash)
        b_layout.addStretch()
        b_layout.addWidget(self.t_status)
        b_layout.addStretch()
        b_layout.addWidget(self.t_btn_file)
        b_layout.addWidget(self.t_btn_clear)
        layout.addWidget(bottom_toolbar)
        self._refresh_status_label()

    def clear_trends_table(self):
        self.trends_table.setRowCount(0)
        self._sparkline_cache.clear()
        self._apply_trends_table_column_widths()
        self._worker_status_text = ""
        self._refresh_status_label()

    def _refresh_status_label(self):
        total_text = f"Total Items: {self.trends_table.rowCount()}"
        if self._worker_status_text:
            self.t_status.setText(f"{self._worker_status_text} | {total_text}")
        else:
            self.t_status.setText(total_text)

    def _set_worker_status(self, message):
        self._worker_status_text = str(message).strip() if message else ""
        self._refresh_status_label()

    def _setup_trends_table_columns(self):
        header = self.trends_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in range(2, self.trends_table.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

        self._trends_col_bounds = {
            0: (120, 140), # Chart sparkline
            2: (105, 180), # Country
            3: (105, 155), # Time Period
            4: (95, 150),  # Category
            5: (95, 145),  # Property
            6: (85, 120),  # Word Count
            7: (110, 165), # Character Count
            8: (95, 130),  # Total Average
            9: (90, 130),  # Trend Slope
            10: (100, 145) # Trending Spike
        }
        self._apply_trends_table_column_widths()

    def _apply_trends_table_column_widths(self):
        old_chart_width = self.trends_table.columnWidth(0)
        for col, (min_width, max_width) in self._trends_col_bounds.items():
            if col != 0:
                self.trends_table.resizeColumnToContents(col)
            width = self.trends_table.columnWidth(col)
            width = max(min_width, min(width, max_width))
            self.trends_table.setColumnWidth(col, width)
        if self.trends_table.columnWidth(0) != old_chart_width:
            self._refresh_sparklines()

    @staticmethod
    def _extract_values(raw_data):
        _, values = build_daily_series(raw_data)
        return values

    def _build_sparkline_pixmap(self, raw_data, width, height):
        values = self._extract_values(raw_data)
        if len(values) < 2 or width < 12 or height < 10:
            return None

        cache_key = (width, height, tuple(round(v, 3) for v in values))
        if cache_key in self._sparkline_cache:
            return self._sparkline_cache[cache_key]

        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        pen = QPen(QColor("#e50914"))
        pen.setWidthF(1.25)
        painter.setPen(pen)

        min_v = min(values)
        max_v = max(values)
        if max_v == min_v:
            max_v = min_v + 1.0

        left = 3.0
        right = float(width) - 3.0
        top = 3.0
        bottom = float(height) - 3.0
        x_step = (right - left) / float(len(values) - 1)

        path = QPainterPath()
        for idx, value in enumerate(values):
            x_pos = left + x_step * idx
            normalized = (value - min_v) / (max_v - min_v)
            y_pos = bottom - normalized * (bottom - top)
            if idx == 0:
                path.moveTo(x_pos, y_pos)
            else:
                path.lineTo(x_pos, y_pos)

        painter.drawPath(path)
        painter.end()

        self._sparkline_cache[cache_key] = pixmap
        return pixmap

    def _refresh_sparkline_for_row(self, row):
        sparkline_width = max(40, self.trends_table.columnWidth(0) - 10)
        chart_item = self.trends_table.item(row, 0)
        if chart_item is None:
            return

        payload = chart_item.data(Qt.ItemDataRole.UserRole) or {}
        raw_data = payload.get("raw_data") or []
        sparkline_height = max(18, self.trends_table.rowHeight(row) - 6)
        pixmap = self._build_sparkline_pixmap(raw_data, sparkline_width, sparkline_height)

        if pixmap is None:
            self.trends_table.removeCellWidget(row, 0)
            chart_item.setText("")
            return

        chart_item.setText("")
        chart_label = self.trends_table.cellWidget(row, 0)
        if not isinstance(chart_label, QLabel):
            chart_label = QLabel()
            chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chart_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.trends_table.setCellWidget(row, 0, chart_label)
        chart_label.setPixmap(pixmap)

    def _refresh_sparklines(self):
        for row in range(self.trends_table.rowCount()):
            self._refresh_sparkline_for_row(row)

    def _set_property_to_youtube(self):
        idx = self.t_combo_prop.findText("Youtube Search", Qt.MatchFlag.MatchFixedString)
        if idx < 0:
            idx = self.t_combo_prop.findText("YouTube Search", Qt.MatchFlag.MatchFixedString)
        if idx >= 0:
            self.t_combo_prop.setCurrentIndex(idx)

    def _ensure_embedded_browser(self):
        if self.browser_view is not None:
            return True

        if QWebEngineView is None:
            self._webengine_available = False
            self._webengine_error = _QTWEBENGINE_IMPORT_ERROR or "PyQt6-WebEngine import failed."
            if self.browser_placeholder is not None:
                self.browser_placeholder.setText(
                    "Embedded browser could not load.\n"
                    "Install with:\npython -m pip install PyQt6-WebEngine\n\n"
                    f"Python: {sys.executable}\n"
                    f"Error: {self._webengine_error}"
                )
            return False

        try:
            self.browser_view = QWebEngineView()
            self._webengine_available = True
            self._webengine_error = ""

            if self.browser_placeholder is not None:
                self.browser_placeholder.deleteLater()
                self.browser_placeholder = None

            self.browser_panel_layout.addWidget(self.browser_view)
            return True
        except Exception as exc:
            self.browser_view = None
            self._webengine_available = False
            self._webengine_error = str(exc)

            if self.browser_placeholder is not None:
                self.browser_placeholder.setText(
                    "Embedded browser could not load.\n"
                    "Install with:\npython -m pip install PyQt6-WebEngine\n\n"
                    f"Python: {sys.executable}\n"
                    f"Error: {self._webengine_error}"
                )
            return False

    def _build_embedded_trends_url(self, keyword=None):
        self._set_property_to_youtube()
        params = {"gprop": "youtube"}

        geo_code = GEO_MAP.get(self.t_combo_country.currentText(), "")
        if geo_code:
            params["geo"] = geo_code

        tf_code = TIME_MAP.get(self.t_combo_period.currentText(), "today 1-m")
        if tf_code:
            params["date"] = tf_code

        if keyword:
            params["q"] = keyword

        return f"https://trends.google.com/trends/explore?{urlencode(params)}"

    def _load_embedded_browser(self, keyword=None):
        if not self._ensure_embedded_browser() or self.browser_view is None:
            return
        url = self._build_embedded_trends_url(keyword=keyword)
        self.browser_view.setUrl(QUrl(url))

    def toggle_browser_panel(self):
        if not self._ensure_embedded_browser():
            QMessageBox.warning(
                self,
                "Browser Unavailable",
                "Embedded browser could not initialize.\n"
                "Run in the same interpreter:\n"
                "python -m pip install PyQt6-WebEngine\n\n"
                f"Python: {sys.executable}\n"
                f"Error: {self._webengine_error or 'Unknown'}",
            )
            return

        if self.browser_panel.isVisible():
            self.browser_panel.hide()
            self.btn_trends_browser.setText("Browser")
            total_width = max(900, self.trends_splitter.width())
            self.trends_splitter.setSizes([260, max(400, total_width - 260), 0])
            return

        self.browser_panel.show()
        self.btn_trends_browser.setText("Hide Browser")
        self._load_embedded_browser()

        total_width = max(1200, self.trends_splitter.width())
        left_width = 260
        browser_width = max(340, int(total_width * 0.33))
        table_width = max(460, total_width - left_width - browser_width)
        self.trends_splitter.setSizes([left_width, table_width, browser_width])

    def start_trends_fetch(self):
        text = self.trends_input.toPlainText()
        keywords = [line.strip() for line in text.split("\n") if line.strip()]
        if not keywords:
            QMessageBox.warning(self, "No Keywords", "Please enter keywords.")
            return

        if self.trends_settings.get("enable_embedded_browser_default", False) and not self.browser_panel.isVisible():
            self.toggle_browser_panel()

        self.trends_table.setRowCount(0)
        self._sparkline_cache.clear()
        self._set_worker_status("Starting trends fetch...")
        self.trends_table.setSortingEnabled(False)
        self.btn_trends_go.hide()
        self.btn_trends_stop.show()
        self.trends_worker = TrendsFetcherWorker(
            keywords,
            self.t_combo_country.currentText(),
            self.t_combo_period.currentText(),
            self.t_combo_cat.currentText(),
            self.t_combo_prop.currentText(),
            pause_after_connections=self.trends_settings.get("pause_after_connections", 20),
            pause_min_seconds=self.trends_settings.get("pause_min_seconds", 10),
            pause_max_seconds=self.trends_settings.get("pause_max_seconds", 60),
            max_workers=min(2, self.trends_settings.get("max_workers", 2)),
        )
        self.trends_worker.progress_signal.connect(self.on_trends_progress)
        self.trends_worker.finished_signal.connect(self.on_trends_finished)
        self.trends_worker.error_signal.connect(self.on_trends_error)
        self.trends_worker.status_signal.connect(self._set_worker_status)
        self.trends_worker.start()

    def stop_trends_fetch(self):
        if hasattr(self, "trends_worker") and self.trends_worker.isRunning():
            self.trends_worker.is_running = False
            self.btn_trends_stop.setText("Stopping...")

    def on_trends_progress(self, data):
        row = self.trends_table.rowCount()
        self.trends_table.insertRow(row)

        raw_data = data.get("RawData") or []
        chart_item = QTableWidgetItem("")
        chart_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if raw_data:
            chart_item.setForeground(QColor("#e50914"))
            chart_item.setData(
                Qt.ItemDataRole.UserRole,
                {
                    "keyword": data["Keyword"],
                    "raw_data": raw_data,
                    "google_trends_url": data.get("GoogleTrendsUrl", ""),
                },
            )
        self.trends_table.setItem(row, 0, chart_item)

        self.trends_table.setItem(row, 1, QTableWidgetItem(str(data["Keyword"])))
        self.trends_table.setItem(row, 2, QTableWidgetItem(str(data["Country"])))
        self.trends_table.setItem(row, 3, QTableWidgetItem(str(data["Time Period"])))
        self.trends_table.setItem(row, 4, QTableWidgetItem(str(data["Category"])))
        self.trends_table.setItem(row, 5, QTableWidgetItem(str(data["Property"])))

        numeric_values = [
            data["Word Count"],
            data["Character Count"],
            data["Total Average"],
            data["Trend Slope"],
            data["Trending Spike"],
        ]
        for col, val in enumerate(numeric_values, start=6):
            item = QTableWidgetItem()
            item.setData(Qt.ItemDataRole.DisplayRole, val)
            self.trends_table.setItem(row, col, item)

        self._apply_trends_table_column_widths()
        self._refresh_sparkline_for_row(row)
        keyword_item = self.trends_table.item(row, 1)
        if keyword_item is not None:
            self.trends_table.scrollToItem(
                keyword_item,
                QTableWidget.ScrollHint.PositionAtBottom,
            )

        progress_idx = data.get("ProcessedIndex")
        progress_total = data.get("TotalKeywords")
        if progress_idx is not None and progress_total is not None:
            self._worker_status_text = (
                f"Processing '{data.get('Keyword', '')}' ({progress_idx}/{progress_total})..."
            )

        self._refresh_status_label()
        self.trends_table.viewport().update()
        QApplication.processEvents()

    def on_trends_finished(self):
        self.btn_trends_stop.hide()
        self.btn_trends_stop.setText("Stop")
        self.btn_trends_go.show()
        self.trends_table.setSortingEnabled(True)
        if self.trends_settings.get("auto_sort_total_average", True):
            self.trends_table.sortItems(8, Qt.SortOrder.DescendingOrder)
        self._apply_trends_table_column_widths()
        self._set_worker_status("Trends fetch completed.")

        if self.trends_table.rowCount() > 0:
            first_kw_item = self.trends_table.item(0, 1)
            if first_kw_item is not None:
                first_keyword = first_kw_item.text().strip()
                if first_keyword:
                    self._load_embedded_browser(first_keyword)

        QMessageBox.information(self, "Finished", "Trends data fetching complete!")

    def on_trends_error(self, err):
        self.btn_trends_stop.hide()
        self.btn_trends_go.show()
        self._set_worker_status(f"Error: {err}")
        QMessageBox.critical(self, "Error", err)

    def show_trend_chart(self, row, column):
        if column != 0:
            return

        chart_item = self.trends_table.item(row, 0)
        if chart_item is None:
            return

        payload = chart_item.data(Qt.ItemDataRole.UserRole)
        if not payload:
            QMessageBox.information(self, "No Data", "No trend data available for this keyword.")
            return

        dialog = TrendChartDialog(
            keyword=payload.get("keyword", ""),
            raw_data=payload.get("raw_data", []),
            google_trends_url=payload.get("google_trends_url", ""),
            dark_theme=self.trends_settings.get("dark_theme_charts", True),
            parent=self,
        )
        dialog.exec()

    def _selected_trend_rows(self):
        return sorted({idx.row() for idx in self.trends_table.selectedIndexes()})

    def _keyword_at_row(self, row):
        item = self.trends_table.item(row, 1)
        return item.text().strip() if item is not None else ""

    def _selected_keywords(self):
        return [kw for kw in (self._keyword_at_row(r) for r in self._selected_trend_rows()) if kw]

    def _all_keywords(self):
        kws = []
        for row in range(self.trends_table.rowCount()):
            kw = self._keyword_at_row(row)
            if kw:
                kws.append(kw)
        return kws

    def _show_status_message(self, message):
        if hasattr(self.main_window, "statusBar") and self.main_window.statusBar():
            self.main_window.statusBar().showMessage(message, 4000)
        self.t_status.setText(message)

    def _show_placeholder_action(self, action_name):
        self._show_status_message(f"{action_name} is not wired yet.")

    def _send_ke_selected(self):
        keywords = self._selected_keywords()
        if not keywords:
            QMessageBox.information(self, "Keywords Everywhere", "No selected rows.")
            return
        self._show_status_message(f"Queued {len(keywords)} selected keyword(s) to Keywords Everywhere tool.")

    def _send_ke_all(self):
        keywords = self._all_keywords()
        if not keywords:
            QMessageBox.information(self, "Keywords Everywhere", "No keywords in Trends table.")
            return
        self._show_status_message(f"Queued ALL {len(keywords)} keyword(s) to Keywords Everywhere tool.")

    def _copy_selected_keywords(self):
        keywords = self._selected_keywords()
        if not keywords:
            QMessageBox.information(self, "Copy", "No selected rows to copy.")
            return
        QApplication.clipboard().setText("\n".join(keywords))
        self._show_status_message(f"Copied {len(keywords)} keyword(s).")

    def _delete_selected_rows(self):
        rows = self._selected_trend_rows()
        if not rows:
            QMessageBox.information(self, "Delete", "No selected rows to delete.")
            return
        for row in reversed(rows):
            self.trends_table.removeRow(row)
        self._refresh_sparklines()
        self.t_status.setText(f"Total Items: {self.trends_table.rowCount()}")

    def _toggle_row_selection(self):
        rows = self._selected_trend_rows()
        if not rows:
            self.trends_table.selectAll()
            return
        all_selected = len(rows) == self.trends_table.rowCount()
        if all_selected:
            self.trends_table.clearSelection()
        else:
            self.trends_table.selectAll()

    def _focus_search_input(self):
        self.trends_input.setFocus()
        self.trends_input.selectAll()

    def show_trends_context_menu(self, pos):
        row = self.trends_table.rowAt(pos.y())
        if row < 0:
            return
        if row >= 0 and row not in self._selected_trend_rows():
            self.trends_table.selectRow(row)

        menu = QMenu(self)
        menu.setStyleSheet(
            """
            QMenu { background-color: #2b2b2b; color: #ffffff; border: 1px solid #444444; }
            QMenu::item { padding: 8px 24px; }
            QMenu::item:selected { background-color: #e50914; color: #ffffff; }
            """
        )

        action_video = menu.addAction("Send to Video search tool")
        action_channel = menu.addAction("Send to Channel search tool")
        action_volume = menu.addAction("Get Search Volume")
        menu.addSeparator()
        action_ke_selected = menu.addAction("Send SELECTED to Keywords Everywhere tool")
        action_ke_all = menu.addAction("Send ALL to Keywords Everywhere tool")
        menu.addSeparator()
        action_checkboxes = menu.addAction("Checkboxes")
        action_filters = menu.addAction("Filters")
        action_copy = menu.addAction("Copy")
        action_hashtags = menu.addAction("Hashtags")
        action_search = menu.addAction("Search")
        action_delete = menu.addAction("Delete")

        action_video.triggered.connect(lambda: self._show_placeholder_action("Send to Video search tool"))
        action_channel.triggered.connect(lambda: self._show_placeholder_action("Send to Channel search tool"))
        action_volume.triggered.connect(lambda: self._show_placeholder_action("Get Search Volume"))
        action_ke_selected.triggered.connect(self._send_ke_selected)
        action_ke_all.triggered.connect(self._send_ke_all)
        action_checkboxes.triggered.connect(self._toggle_row_selection)
        action_filters.triggered.connect(lambda: self._show_placeholder_action("Filters"))
        action_copy.triggered.connect(self._copy_selected_keywords)
        action_hashtags.triggered.connect(lambda: self._show_placeholder_action("Hashtags"))
        action_search.triggered.connect(self._focus_search_input)
        action_delete.triggered.connect(self._delete_selected_rows)

        menu.exec(self.trends_table.viewport().mapToGlobal(pos))

    def open_settings_dialog(self):
        dialog = TrendsSettingsDialog(self.trends_settings, self)
        if dialog.exec():
            self.trends_settings = dialog.get_settings()
