import webbrowser
import sys
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

from PyQt6.QtCore import Qt, QThread, QTimer, QUrl, pyqtSignal
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
    QStyle,
    QInputDialog,
)

from core.trends_fetcher import TrendsFetcherWorker
from utils.constants import CAT_MAP, COUNTRY_LIST, GEO_MAP, TIME_MAP
from utils.i18n import DEFAULT_LANGUAGE, translate
from utils.proxy_utils import parse_proxy_lines, to_requests_proxies

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

TRENDS_NUMERIC_FILTER_COLUMNS = {
    6: "Word Count",
    7: "Character Count",
    8: "Total Average",
    9: "Trend Slope",
    10: "Trending Spike",
}


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
    base_values = [float(day_value_map[day]) for day in sorted_days]

    if len(base_dates) == 1:
        return base_dates, [base_values[0]]

    start_day = sorted_days[0]
    end_day = sorted_days[-1]
    day_count = (end_day - start_day).days + 1
    daily_dates = [
        datetime.combine(start_day + timedelta(days=idx), datetime.min.time())
        for idx in range(day_count)
    ]

    known_map = {
        dt.date(): float(value)
        for dt, value in zip(base_dates, base_values)
    }

    daily_values = []
    sorted_value_days = sorted(known_map.keys())
    current_index = 0

    for day in (dt.date() for dt in daily_dates):
        if day in known_map:
            daily_values.append(float(known_map[day]))
            continue

        while (
            current_index + 1 < len(sorted_value_days)
            and sorted_value_days[current_index + 1] < day
        ):
            current_index += 1

        prev_day = sorted_value_days[current_index]
        next_idx = min(current_index + 1, len(sorted_value_days) - 1)
        next_day = sorted_value_days[next_idx]

        prev_val = float(known_map[prev_day])
        next_val = float(known_map[next_day])

        if next_day == prev_day:
            daily_values.append(prev_val)
            continue

        span = (next_day - prev_day).days
        offset = (day - prev_day).days
        ratio = max(0.0, min(1.0, float(offset) / float(span)))
        interpolated = prev_val + (next_val - prev_val) * ratio
        daily_values.append(float(interpolated))

    return daily_dates, daily_values


class TrendChartDialog(QDialog):
    def __init__(self, keyword, raw_data, google_trends_url, dark_theme=True, language=DEFAULT_LANGUAGE, parent=None):
        super().__init__(parent)
        self.keyword = keyword
        self.raw_data = raw_data or []
        self.google_trends_url = google_trends_url
        self.dark_theme = bool(dark_theme)
        self.language = str(language or DEFAULT_LANGUAGE).strip().lower() or DEFAULT_LANGUAGE
        self.figure = None
        self.axis = None
        self.canvas = None

        self.setWindowTitle(self._t("trends.chart.window_title", "Searches Over Time - {keyword}", keyword=self.keyword))
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

    def _t(self, key, default=None, **kwargs):
        return translate(self.language, key, default=default, **kwargs)

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
                self._t("trends.chart.error_title", "Chart Error"),
                self._t("trends.chart.missing_matplotlib", "matplotlib is missing. Install it with: pip install matplotlib"),
            )
            self.close()
            return

        self.figure, self.axis = plt.subplots(figsize=(10, 5))
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas, stretch=1)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.btn_view_google = QPushButton(self._t("trends.chart.view_google", "View on Google Trends"))
        self.btn_view_google.setEnabled(bool(self.google_trends_url))
        self.btn_view_google.clicked.connect(self._open_google_trends)

        self.chk_bar_chart = QCheckBox(self._t("trends.chart.bar_chart", "Bar Chart"))
        self.chk_bar_chart.stateChanged.connect(self._draw_chart)

        self.btn_save = QPushButton(self._t("common.save", "Save"))
        self.btn_save.clicked.connect(self._save_chart)

        self.btn_close = QPushButton(self._t("common.close", "Close"))
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
                self._t("trends.chart.no_data", "No trend data available."),
                transform=self.axis.transAxes,
                ha="center",
                va="center",
                color=empty_color,
            )

        self.axis.set_title(
            self._t("trends.chart.title", "Worldwide Search Trends Over Time for {keyword}", keyword=self.keyword),
            color=title_color,
            pad=10,
            fontsize=11,
            fontweight="semibold",
        )
        self.axis.set_xlabel(self._t("trends.chart.date", "Date"), color=x_label_color, labelpad=10)
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
            self._t("trends.chart.save_title", "Save Chart"),
            default_name,
            "PNG Files (*.png)",
        )
        if not path:
            return

        try:
            self.figure.savefig(path, dpi=160, facecolor=self.figure.get_facecolor(), bbox_inches="tight")
        except Exception as exc:
            QMessageBox.warning(
                self,
                self._t("trends.chart.save_error_title", "Save Error"),
                self._t("trends.chart.save_error_message", "Failed to save chart: {error}", error=exc),
            )


class TrendsSettingsDialog(QDialog):
    def __init__(self, settings, language=DEFAULT_LANGUAGE, parent=None):
        super().__init__(parent)
        self.language = str(language or DEFAULT_LANGUAGE).strip().lower() or DEFAULT_LANGUAGE
        self.setWindowTitle(self._t("trends.settings.window_title", "Trends Tool Settings"))
        self.setModal(True)
        self.resize(620, 360)
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

    def _t(self, key, default=None, **kwargs):
        return translate(self.language, key, default=default, **kwargs)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 14)
        root.setSpacing(14)

        row1 = QHBoxLayout()
        self.chk_pause_after_connections = QCheckBox("")
        self.chk_pause_after_connections.setChecked(bool(self._settings.get("enable_pause_after_connections", True)))
        row1.addWidget(self.chk_pause_after_connections)
        row1.addWidget(QLabel(self._t("trends.settings.after", "After")))
        self.spin_pause_after = QSpinBox()
        self.spin_pause_after.setRange(1, 10000)
        self.spin_pause_after.setValue(int(self._settings.get("pause_after_connections", 20)))
        row1.addWidget(self.spin_pause_after)
        row1.addWidget(QLabel(self._t("trends.settings.web_connections_pause_from", "web connections, pause from")))
        self.spin_pause_min = QSpinBox()
        self.spin_pause_min.setRange(0, 3600)
        self.spin_pause_min.setValue(int(self._settings.get("pause_min_seconds", 10)))
        row1.addWidget(self.spin_pause_min)
        row1.addWidget(QLabel(self._t("trends.settings.seconds_to", "seconds to")))
        self.spin_pause_max = QSpinBox()
        self.spin_pause_max.setRange(0, 3600)
        self.spin_pause_max.setValue(int(self._settings.get("pause_max_seconds", 60)))
        row1.addWidget(self.spin_pause_max)
        row1.addWidget(QLabel(self._t("trends.settings.seconds", "seconds")))
        row1.addStretch()
        root.addLayout(row1)

        row2 = QHBoxLayout()
        self.chk_max_consecutive_proxy = QCheckBox("")
        self.chk_max_consecutive_proxy.setChecked(
            bool(self._settings.get("enable_max_consecutive_proxy_connections", True))
        )
        row2.addWidget(self.chk_max_consecutive_proxy)
        row2.addWidget(QLabel(self._t("trends.settings.max_connections_per_proxy", "Max consecutive web connections per proxy:")))
        self.spin_consecutive_proxy = QSpinBox()
        self.spin_consecutive_proxy.setRange(1, 10000)
        self.spin_consecutive_proxy.setValue(
            int(self._settings.get("max_consecutive_web_connections_per_proxy", 50))
        )
        row2.addWidget(self.spin_consecutive_proxy)
        row2.addStretch()
        root.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel(self._t("trends.settings.max_workers", "Maximum concurrent workers")))
        self.spin_workers = QSpinBox()
        self.spin_workers.setRange(1, 2)
        self.spin_workers.setValue(min(2, int(self._settings.get("max_workers", 2))))
        row3.addWidget(self.spin_workers)
        row3.addStretch()
        root.addLayout(row3)

        self.chk_auto_sort = QCheckBox(self._t("trends.settings.auto_sort", "Auto sort table by Total Average after finishing"))
        self.chk_auto_sort.setChecked(bool(self._settings.get("auto_sort_total_average", True)))
        root.addWidget(self.chk_auto_sort)

        self.chk_browser_default = QCheckBox(self._t("trends.settings.browser_default", "Enable embedded browser panel by default"))
        self.chk_browser_default.setChecked(bool(self._settings.get("enable_embedded_browser_default", False)))
        root.addWidget(self.chk_browser_default)

        self.chk_dark_charts = QCheckBox(self._t("trends.settings.dark_charts", "Dark theme for charts"))
        self.chk_dark_charts.setChecked(bool(self._settings.get("dark_theme_charts", True)))
        root.addWidget(self.chk_dark_charts)

        root.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_ok = QPushButton(self._t("common.ok", "OK"))
        btn_ok.setObjectName("ok_btn")
        btn_cancel = QPushButton(self._t("common.cancel", "Cancel"))
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
            "enable_pause_after_connections": bool(self.chk_pause_after_connections.isChecked()),
            "pause_after_connections": int(self.spin_pause_after.value()),
            "pause_min_seconds": pause_min,
            "pause_max_seconds": pause_max,
            "max_workers": min(2, int(self.spin_workers.value())),
            "enable_max_consecutive_proxy_connections": bool(self.chk_max_consecutive_proxy.isChecked()),
            "max_consecutive_web_connections_per_proxy": int(self.spin_consecutive_proxy.value()),
            "auto_sort_total_average": bool(self.chk_auto_sort.isChecked()),
            "enable_embedded_browser_default": bool(self.chk_browser_default.isChecked()),
            "dark_theme_charts": bool(self.chk_dark_charts.isChecked()),
        }


class ProxyHealthCheckWorker(QThread):
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(list, list, float)
    error_signal = pyqtSignal(str)

    def __init__(self, proxy_list, timeout_seconds=4.0):
        super().__init__()
        self.proxy_list = list(proxy_list or [])
        self.timeout_seconds = max(1.0, float(timeout_seconds))
        self._running = True

    def stop(self):
        self._running = False

    @staticmethod
    def _safe_proxy_label(proxy_text):
        text = str(proxy_text or "").strip()
        if not text:
            return "proxy"
        if "://" in text:
            text = text.split("://", 1)[1]
        if "@" in text:
            text = text.split("@", 1)[1]
        return text

    def _is_proxy_alive(self, proxy_url):
        if not self._running:
            return False
        proxy_map = to_requests_proxies(proxy_url)
        if not proxy_map:
            return False

        endpoints = [
            ("https://www.google.com/generate_204", 204),
            ("https://httpbin.org/ip", 200),
            ("http://httpbin.org/ip", 200),
        ]
        headers = {"User-Agent": "Mozilla/5.0"}
        for endpoint, expected in endpoints:
            if not self._running:
                return False
            try:
                response = requests.get(
                    endpoint,
                    headers=headers,
                    proxies=proxy_map,
                    timeout=(self.timeout_seconds, self.timeout_seconds),
                )
                if response.status_code == expected or (expected == 200 and response.status_code < 400):
                    return True
            except Exception:
                continue
        return False

    def run(self):
        if requests is None:
            self.error_signal.emit("requests is required. Run: pip install requests")
            self.finished_signal.emit([], list(self.proxy_list), 0.0)
            return

        proxies = [str(p).strip() for p in self.proxy_list if str(p).strip()]
        if not proxies:
            self.finished_signal.emit([], [], 0.0)
            return

        start_ts = time.time()
        alive = []
        dead = []
        total = len(proxies)
        completed = 0
        max_workers = min(24, max(4, total // 5 if total >= 20 else 4))

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_map = {pool.submit(self._is_proxy_alive, proxy): proxy for proxy in proxies}
            for future in as_completed(future_map):
                if not self._running:
                    break
                proxy = future_map[future]
                ok = False
                try:
                    ok = bool(future.result())
                except Exception:
                    ok = False

                if ok:
                    alive.append(proxy)
                else:
                    dead.append(proxy)
                completed += 1
                self.progress_signal.emit(
                    f"Checking proxies... {completed}/{total} (live: {len(alive)})"
                )

        if not self._running:
            self.finished_signal.emit(alive, dead, time.time() - start_ts)
            return

        self.finished_signal.emit(alive, dead, time.time() - start_ts)


class TrendsTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.current_language = getattr(main_window, "current_language", DEFAULT_LANGUAGE)
        self._sparkline_cache = {}
        self._worker_status_text = ""
        self.trends_settings = {
            "enable_pause_after_connections": True,
            "pause_after_connections": 20,
            "pause_min_seconds": 10,
            "pause_max_seconds": 60,
            "max_workers": 2,
            "enable_max_consecutive_proxy_connections": True,
            "max_consecutive_web_connections_per_proxy": 50,
            "max_proxies_per_run": 30,
            "auto_sort_total_average": True,
            "enable_embedded_browser_default": False,
            "dark_theme_charts": True,
        }
        if self.main_window is not None and hasattr(self.main_window, "get_proxy_runtime_settings"):
            runtime_proxy_settings = self.main_window.get_proxy_runtime_settings()
            self.trends_settings["max_proxies_per_run"] = int(
                runtime_proxy_settings.get("max_proxies_per_run", self.trends_settings["max_proxies_per_run"])
            )
        self.browser_view = None
        self._webengine_available = False
        self.browser_panel = None
        self.browser_panel_layout = None
        self.browser_placeholder = None
        self._webengine_error = ""
        self._qwebengine_view_class = None
        self._qwebengine_import_attempted = False
        self.trends_splitter = None
        self._use_embedded_browser_mode = False
        self._run_pytrends_with_external_browser = True
        self._open_external_browser_sequence = False
        self._browser_sequence_active = False
        self._browser_keywords_queue = []
        self._browser_keyword_index = 0
        self._browser_wait_min_seconds = 4.5
        self._browser_wait_max_seconds = 6.5
        self._pending_input_keywords = []
        self._chart_header_checked = False
        self._chart_check_syncing = False
        self._filter_keyword_text = ""
        self._filter_country_value = ""
        self._filter_category_value = ""
        self._filter_property_value = ""
        self._filter_checked_only = False
        self._filter_numeric_rules = {}
        self._proxy_panel_hidden = False
        proxy_settings = (
            self.main_window.get_proxy_settings()
            if self.main_window is not None and hasattr(self.main_window, "get_proxy_settings")
            else {"enabled": False, "proxies": []}
        )
        self._proxy_enabled = bool(proxy_settings.get("enabled", False))
        self._proxy_list = list(proxy_settings.get("proxies", []))
        self._proxy_health_worker = None
        self._pending_keywords_after_proxy_check = []
        self._proxy_health_check_before_go = True
        self._proxy_health_timeout_seconds = 4.0
        self._browser_wait_timer = QTimer(self)
        self._browser_wait_timer.setSingleShot(True)
        self._browser_wait_timer.timeout.connect(self._load_next_browser_keyword)
        self.setup_ui()

    def _t(self, key, default=None, **kwargs):
        return translate(self.current_language, key, default=default, **kwargs)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(35, 30, 35, 30)
        layout.setSpacing(20)

        self.header_label = QLabel("Trends Tool")
        self.header_label.setObjectName("header_label")
        self.header_label.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        layout.addWidget(self.header_label)

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
        self.btn_trends_stop.setStyleSheet("background-color: #e50914; color: white; border: none; font-weight: bold; border-radius: 4px;")
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

        self.btn_use_proxies = QPushButton("Use Proxies")
        self.btn_use_proxies.setCheckable(True)
        self.btn_use_proxies.setChecked(False)
        self.btn_use_proxies.setFixedSize(116, 28)
        self.btn_use_proxies.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_use_proxies.setStyleSheet(
            "QPushButton { background-color: #2b2b2b; color: #ffffff; border: 1px solid #4a4a4a; font-weight: 600; border-radius: 4px; }"
            "QPushButton:checked { background-color: #e50914; border: none; font-weight: bold; }"
        )
        self.btn_use_proxies.toggled.connect(self._on_proxy_toggle_changed)

        top_layout.addWidget(self.btn_trends_go)
        top_layout.addWidget(self.btn_trends_stop)
        top_layout.addSpacing(140)
        top_layout.addWidget(self.btn_trends_settings)
        top_layout.addStretch()
        top_layout.addWidget(self.btn_use_proxies)
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
        self.lbl_country = QLabel("Country:")
        self.lbl_country.setStyleSheet(label_style)
        form_layout.addRow(self.lbl_country, self.t_combo_country)

        self.t_combo_period = QComboBox()
        self.t_combo_period.addItems(["Past 30 days", "Past 7 days", "Past 12 months", "2004 - present"])
        self.t_combo_period.setStyleSheet(combo_style)
        self.lbl_period = QLabel("Time Period:")
        self.lbl_period.setStyleSheet(label_style)
        form_layout.addRow(self.lbl_period, self.t_combo_period)

        self.t_combo_cat = QComboBox()
        self.t_combo_cat.addItems(["All Categories", "Arts & Entertainment", "Autos & Vehicles", "Beauty & Fitness", "Games"])
        self.t_combo_cat.setStyleSheet(combo_style)
        self.lbl_cat = QLabel("Category:")
        self.lbl_cat.setStyleSheet(label_style)
        form_layout.addRow(self.lbl_cat, self.t_combo_cat)

        self.t_combo_prop = QComboBox()
        self.t_combo_prop.addItems(["Youtube Search", "Web Search", "Image Search", "News Search", "Google Shopping"])
        self.t_combo_prop.setStyleSheet(combo_style)
        self.lbl_prop = QLabel("Property:")
        self.lbl_prop.setStyleSheet(label_style)
        form_layout.addRow(self.lbl_prop, self.t_combo_prop)

        left_layout.addLayout(form_layout)

        self.kw_label = QLabel("Enter one keyword per line:")
        self.kw_label.setStyleSheet("color: #bbbbbb; font-size: 12px; margin-top: 10px;")
        left_layout.addWidget(self.kw_label)

        self.trends_input = QTextEdit()
        self.trends_input.setStyleSheet("background-color: #ffffff; color: #000000; border: 1px solid #aaa; border-radius: 2px;")
        self.trends_input.setText("diy crafts\ndiy wall decor\ndiy videos\ndiy yarn\ndiy upholstered headboard\ndiy zipline\ndiy tiktok\ndiy aquarium")
        left_layout.addWidget(self.trends_input, stretch=1)

        self.trends_table = QTableWidget()
        self.trends_table.setColumnCount(11)
        self.trends_table.setHorizontalHeaderLabels(self._translated_trends_table_headers())
        self._update_chart_header_label()
        self._setup_trends_table_columns()
        self.trends_table.verticalHeader().setDefaultSectionSize(36)
        self.trends_table.verticalHeader().setVisible(False)
        self.trends_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.trends_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.trends_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.trends_table.customContextMenuRequested.connect(self.show_trends_context_menu)
        self.trends_table.horizontalHeader().sectionClicked.connect(self._on_trends_header_clicked)
        self.trends_table.itemChanged.connect(self._on_trends_item_changed)
        self.trends_table.setStyleSheet(
            "QTableWidget { background-color: #ffffff; color: #000000; gridline-color: #dddddd; border: 1px solid #cccccc; } "
            "QHeaderView::section { background-color: #f0f0f0; color: #000000; font-weight: bold; border: 1px solid #cccccc; padding: 4px; }"
        )
        self.trends_table.cellDoubleClicked.connect(self.show_trend_chart)

        self.browser_panel = QFrame()
        self.browser_panel.setStyleSheet("background-color: #12151d; border: 1px solid #2f3444; border-radius: 4px;")
        self.browser_panel.setMinimumWidth(260)
        self.browser_panel.setMaximumWidth(340)
        self.browser_panel_layout = QVBoxLayout(self.browser_panel)
        self.browser_panel_layout.setContentsMargins(8, 8, 8, 8)
        self.browser_panel_layout.setSpacing(6)

        proxy_top = QHBoxLayout()
        proxy_top.setContentsMargins(0, 0, 0, 0)
        proxy_top.setSpacing(8)
        self.lbl_proxy_title = QLabel("Use Proxies")
        self.lbl_proxy_title.setStyleSheet("color: #f2f5fb; font-size: 12px; font-weight: 700;")
        proxy_top.addWidget(self.lbl_proxy_title)
        proxy_top.addStretch()

        self.btn_proxy_hide = QPushButton("Hide")
        self.btn_proxy_hide.setFixedSize(52, 24)
        self.btn_proxy_hide.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_proxy_hide.setStyleSheet(
            "background-color: #e50914; color: #ffffff; border: none; border-radius: 4px; font-weight: bold;"
        )
        self.btn_proxy_hide.clicked.connect(self._toggle_proxy_panel_visibility)
        proxy_top.addWidget(self.btn_proxy_hide)
        self.browser_panel_layout.addLayout(proxy_top)

        self.proxy_label = QLabel("Enter one proxy per line:")
        self.proxy_label.setStyleSheet("color: #d4d8e2; font-size: 11px;")
        self.browser_panel_layout.addWidget(self.proxy_label)

        self.proxy_input = QTextEdit()
        self.proxy_input.setPlaceholderText(
            "190.109.121.1:9999\n"
            "user:pass@190.109.121.1:9999\n"
            "190.109.121.1:9999:user:pass"
        )
        self.proxy_input.setStyleSheet("background-color: #ffffff; color: #000000; border: 1px solid #8a8f9f; border-radius: 2px;")
        self.proxy_input.setFixedHeight(330)
        self.proxy_input.setPlainText("")
        self.proxy_input.textChanged.connect(self._on_proxy_text_changed)
        self.browser_panel_layout.addWidget(self.proxy_input, stretch=1)

        self.lbl_proxy_total = QLabel("Total: 0")
        self.lbl_proxy_total.setStyleSheet("color: #cfd4df; font-size: 11px;")
        self.browser_panel_layout.addWidget(self.lbl_proxy_total)

        proxy_health_row = QHBoxLayout()
        proxy_health_row.setContentsMargins(0, 0, 0, 0)
        proxy_health_row.setSpacing(6)
        self.chk_proxy_health_before_go = QCheckBox("Health check before Go")
        self.chk_proxy_health_before_go.setChecked(True)
        self.chk_proxy_health_before_go.setStyleSheet("color: #d4d8e2; font-size: 11px;")
        self.chk_proxy_health_before_go.toggled.connect(
            lambda checked: setattr(self, "_proxy_health_check_before_go", bool(checked))
        )
        proxy_health_row.addWidget(self.chk_proxy_health_before_go)
        proxy_health_row.addStretch()
        self.lbl_proxy_timeout = QLabel("Timeout")
        proxy_health_row.addWidget(self.lbl_proxy_timeout)
        self.spin_proxy_health_timeout = QSpinBox()
        self.spin_proxy_health_timeout.setRange(1, 15)
        self.spin_proxy_health_timeout.setValue(4)
        self.spin_proxy_health_timeout.setStyleSheet(
            "background-color: #ffffff; color: #000000; border: 1px solid #8a8f9f; border-radius: 2px; padding: 2px 4px; font-size: 11px;"
        )
        self.spin_proxy_health_timeout.valueChanged.connect(
            lambda value: setattr(self, "_proxy_health_timeout_seconds", float(value))
        )
        proxy_health_row.addWidget(self.spin_proxy_health_timeout)
        self.lbl_proxy_timeout_unit = QLabel("s")
        proxy_health_row.addWidget(self.lbl_proxy_timeout_unit)
        self.browser_panel_layout.addLayout(proxy_health_row)

        proxy_btn_row = QHBoxLayout()
        proxy_btn_row.setContentsMargins(0, 0, 0, 0)
        proxy_btn_row.setSpacing(6)

        self.source_label = QLabel("Source:")
        self.source_label.setStyleSheet("color: #cfd4df; font-size: 11px;")
        proxy_btn_row.addWidget(self.source_label)

        self.combo_proxy_source = QComboBox()
        self.combo_proxy_source.addItems([
            "Webshare.io",
            "ProxyScrape",
            "GeoNode",
            "Free Proxy List",
        ])
        self.combo_proxy_source.setStyleSheet(
            "background-color: #ffffff; color: #000000; border: 1px solid #8a8f9f; border-radius: 2px; padding: 3px 6px; font-size: 11px;"
        )
        proxy_btn_row.addWidget(self.combo_proxy_source, stretch=1)
        self.browser_panel_layout.addLayout(proxy_btn_row)

        proxy_action_row = QHBoxLayout()
        proxy_action_row.setContentsMargins(0, 0, 0, 0)
        proxy_action_row.setSpacing(6)
        self.btn_load_free_proxies = QPushButton("Load Free Proxies")
        self.btn_load_free_proxies.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_load_free_proxies.setStyleSheet(
            "background-color: #e50914; color: #ffffff; border: none; border-radius: 4px; font-weight: bold; padding: 5px 10px;"
        )
        self.btn_load_free_proxies.clicked.connect(self._load_free_proxies)
        proxy_action_row.addWidget(self.btn_load_free_proxies)

        self.btn_load_proxy_txt = QPushButton("Load TXT")
        self.btn_load_proxy_txt.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_load_proxy_txt.setStyleSheet(
            "background-color: #252b3a; color: #ffffff; border: 1px solid #434b60; border-radius: 4px; font-weight: 600; padding: 5px 10px;"
        )
        self.btn_load_proxy_txt.clicked.connect(self._load_proxies_from_txt)
        proxy_action_row.addWidget(self.btn_load_proxy_txt)

        self.btn_check_proxy_health = QPushButton("Check Proxies")
        self.btn_check_proxy_health.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_check_proxy_health.setStyleSheet(
            "background-color: #252b3a; color: #ffffff; border: 1px solid #434b60; border-radius: 4px; font-weight: 600; padding: 5px 10px;"
        )
        self.btn_check_proxy_health.clicked.connect(self._run_proxy_health_check_only)
        proxy_action_row.addWidget(self.btn_check_proxy_health)

        self.btn_proxy_settings = QPushButton("Settings")
        self.btn_proxy_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_proxy_settings.setStyleSheet(
            "background-color: #252b3a; color: #ffffff; border: 1px solid #434b60; border-radius: 4px; font-weight: 600; padding: 5px 10px;"
        )
        self.btn_proxy_settings.clicked.connect(self._open_proxy_help_dialog)
        proxy_action_row.addWidget(self.btn_proxy_settings)
        self.browser_panel_layout.addLayout(proxy_action_row)

        self.browser_panel.hide()
        self._refresh_proxy_summary()
        self._sync_proxy_settings_to_main_window()

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
        self._set_fetch_buttons_running(False)
        self.apply_language(self.current_language)
        self._refresh_status_label()

    def clear_trends_table(self):
        self.trends_table.setRowCount(0)
        self._sparkline_cache.clear()
        self._chart_header_checked = False
        self._update_chart_header_label()
        self._clear_trends_filters(update_ui=False)
        self._apply_trends_table_column_widths()
        self._worker_status_text = ""
        self._pending_input_keywords = []
        self._refresh_status_label()

    def _translated_trends_table_headers(self):
        return [
            self._t("trends.table.chart", "Chart"),
            self._t("trends.table.keyword", "Keyword"),
            self._t("trends.table.country", "Country"),
            self._t("trends.table.time_period", "Time Period"),
            self._t("trends.table.category", "Category"),
            self._t("trends.table.property", "Property"),
            self._t("trends.table.word_count", "Word Count"),
            self._t("trends.table.character_count", "Character Count"),
            self._t("trends.table.total_average", "Total Average"),
            self._t("trends.table.trend_slope", "Trend Slope"),
            self._t("trends.table.trending_spike", "Trending Spike"),
        ]

    def apply_language(self, language):
        self.current_language = str(language or DEFAULT_LANGUAGE).strip().lower() or DEFAULT_LANGUAGE
        self.header_label.setText(self._t("trends.title", "Trends Tool"))
        self.btn_trends_go.setText(self._t("common.go", "Go"))
        self.btn_trends_stop.setText(self._t("common.stop", "Stop"))
        self.btn_trends_settings.setText(self._t("common.settings", "Settings"))
        self.btn_trends_browser.setText(self._t("common.browser", "Browser"))
        self.btn_use_proxies.setText(self._t("trends.use_proxies", "Use Proxies"))

        self.lbl_country.setText(self._t("trends.country", "Country:"))
        self.lbl_period.setText(self._t("trends.time_period", "Time Period:"))
        self.lbl_cat.setText(self._t("trends.category", "Category:"))
        self.lbl_prop.setText(self._t("trends.property", "Property:"))
        self.kw_label.setText(self._t("trends.enter_keywords", "Enter one keyword per line:"))

        self.trends_table.setHorizontalHeaderLabels(self._translated_trends_table_headers())
        self._update_chart_header_label()

        self.lbl_proxy_title.setText(self._t("trends.use_proxies", "Use Proxies"))
        self.btn_proxy_hide.setText(
            self._t("common.show", "Show") if self._proxy_panel_hidden else self._t("common.hide", "Hide")
        )
        self.proxy_label.setText(self._t("trends.enter_proxies", "Enter one proxy per line:"))
        self.chk_proxy_health_before_go.setText(self._t("trends.proxy_health_before_go", "Health check before Go"))
        self.lbl_proxy_timeout.setText(self._t("trends.proxy_timeout", "Timeout"))
        self.lbl_proxy_timeout_unit.setText(self._t("trends.proxy_timeout_unit", "s"))
        self.source_label.setText(self._t("trends.proxy_source", "Source:"))
        self.btn_load_free_proxies.setText(self._t("trends.load_free_proxies", "Load Free Proxies"))
        self.btn_load_proxy_txt.setText(self._t("trends.load_txt", "Load TXT"))
        self.btn_check_proxy_health.setText(self._t("trends.check_proxies", "Check Proxies"))
        self.btn_proxy_settings.setText(self._t("common.settings", "Settings"))
        self._refresh_proxy_summary()

        self.t_btn_vol.setText(self._t("common.volume_data", "Volume Data"))
        self.t_btn_hash.setText(self._t("common.hashtags", "Hashtags"))
        self.t_btn_file.setText(self._t("common.file", "File"))
        self.t_btn_clear.setText(self._t("common.clear", "Clear"))
        self._refresh_status_label()

    def _collect_proxy_list_from_ui(self):
        if not hasattr(self, "proxy_input"):
            return list(self._proxy_list)
        return parse_proxy_lines(self.proxy_input.toPlainText())

    def _sync_proxy_settings_to_main_window(self):
        self._proxy_list = self._collect_proxy_list_from_ui()
        enabled = bool(getattr(self, "btn_use_proxies", None) and self.btn_use_proxies.isChecked())
        self._proxy_enabled = enabled
        if self.main_window is not None and hasattr(self.main_window, "set_proxy_settings"):
            self.main_window.set_proxy_settings(enabled=enabled, proxies=self._proxy_list)

    def _refresh_proxy_summary(self):
        if not hasattr(self, "lbl_proxy_total"):
            return
        count = len(self._collect_proxy_list_from_ui())
        self.lbl_proxy_total.setText(self._t("common.total_count", "Total: {count}", count=count))

    def _on_proxy_text_changed(self):
        self._refresh_proxy_summary()
        self._sync_proxy_settings_to_main_window()

    def _on_proxy_toggle_changed(self, checked):
        self._proxy_enabled = bool(checked)
        self._set_proxy_panel_visible(bool(checked))
        self._sync_proxy_settings_to_main_window()
        if checked and not self._collect_proxy_list_from_ui():
            self._show_status_message(self._t("trends.proxy_on_empty", "Proxy is ON but proxy list is empty."))
        elif checked:
            self._show_status_message(
                self._t(
                    "trends.proxy_enabled",
                    "Proxy enabled ({count} entries).",
                    count=len(self._collect_proxy_list_from_ui()),
                )
            )
        else:
            self._show_status_message(self._t("trends.proxy_disabled", "Proxy disabled."))

    def _set_proxy_panel_visible(self, visible):
        if visible:
            self.browser_panel.show()
            total_width = max(900, self.trends_splitter.width())
            right_width = 300
            table_width = max(420, total_width - 260 - right_width)
            self.trends_splitter.setSizes([260, table_width, right_width])
            self._proxy_panel_hidden = False
            self.btn_proxy_hide.setText(self._t("common.hide", "Hide"))
        else:
            self.browser_panel.hide()
            total_width = max(900, self.trends_splitter.width())
            self.trends_splitter.setSizes([260, max(420, total_width - 260), 0])
            self._proxy_panel_hidden = True
            self.btn_proxy_hide.setText(self._t("common.show", "Show"))

    def _toggle_proxy_panel_visibility(self):
        if self._proxy_panel_hidden:
            self._set_proxy_panel_visible(True)
            if hasattr(self, "btn_use_proxies"):
                self.btn_use_proxies.setChecked(True)
            return
        self._set_proxy_panel_visible(False)
        if hasattr(self, "btn_use_proxies"):
            self.btn_use_proxies.setChecked(False)

    def _open_proxy_help_dialog(self):
        QMessageBox.information(
            self,
            self._t("trends.proxy_help.title", "Proxy Format Help"),
            self._t(
                "trends.proxy_help.body",
                "Supported formats:\n"
                "- ip:port\n"
                "- http://ip:port\n"
                "- user:pass@ip:port\n"
                "- http://user:pass@ip:port\n"
                "- ip:port:user:pass\n"
                "- user:pass:ip:port\n\n"
                "Free source UI options:\n"
                "- Webshare.io\n"
                "- ProxyScrape\n"
                "- GeoNode\n"
                "- Free Proxy List",
            ),
        )

    def _load_proxies_from_txt(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self._t("trends.proxy_txt.load_title", "Load Proxy TXT"),
            "",
            "Text Files (*.txt);;All Files (*.*)",
        )
        if not file_path:
            return

        text_data = ""
        read_errors = []
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                with open(file_path, "r", encoding=enc) as f:
                    text_data = f.read()
                break
            except Exception as exc:
                read_errors.append(str(exc))
                continue

        if not text_data.strip():
            QMessageBox.warning(
                self,
                self._t("trends.proxy_txt.title", "Proxy TXT"),
                self._t("trends.proxy_txt.empty_file", "File is empty or cannot be read."),
            )
            return

        loaded = parse_proxy_lines(text_data)
        if not loaded:
            QMessageBox.warning(
                self,
                self._t("trends.proxy_txt.title", "Proxy TXT"),
                self._t(
                    "trends.proxy_txt.no_valid_proxies",
                    "No valid proxies found.\nSupported formats:\n"
                    "- ip:port\n"
                    "- user:pass@ip:port\n"
                    "- ip:port:user:pass\n"
                    "- user:pass:ip:port",
                ),
            )
            return

        added, total = self._merge_proxy_list_into_ui(loaded)
        self._show_status_message(
            self._t("trends.status.loaded_proxies_from_txt", "Loaded {added} proxies from TXT. Total: {total}", added=added, total=total)
        )

    @staticmethod
    def _dedupe_proxies(proxies):
        output = []
        seen = set()
        for proxy in proxies or []:
            text = str(proxy).strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            output.append(text)
        return output

    @staticmethod
    def _proxy_to_display_text(proxy):
        text = str(proxy or "").strip()
        if not text:
            return ""
        if "://" in text:
            text = text.split("://", 1)[1].strip()
        return text

    def _proxies_to_display_text(self, proxies):
        return "\n".join(
            self._proxy_to_display_text(p)
            for p in (proxies or [])
            if self._proxy_to_display_text(p)
        )

    def _merge_proxy_list_into_ui(self, new_proxies):
        existing = self._collect_proxy_list_from_ui()
        merged = self._dedupe_proxies(existing + list(new_proxies or []))
        self.proxy_input.blockSignals(True)
        self.proxy_input.setPlainText(self._proxies_to_display_text(merged))
        self.proxy_input.blockSignals(False)
        self._refresh_proxy_summary()
        self._sync_proxy_settings_to_main_window()
        added_count = max(0, len(merged) - len(existing))
        return added_count, len(merged)

    def _replace_proxy_list_in_ui(self, proxies):
        clean = self._dedupe_proxies(proxies)
        self.proxy_input.blockSignals(True)
        self.proxy_input.setPlainText(self._proxies_to_display_text(clean))
        self.proxy_input.blockSignals(False)
        self._refresh_proxy_summary()
        self._sync_proxy_settings_to_main_window()
        return len(clean)

    def _set_proxy_ui_busy(self, busy):
        enabled = not bool(busy)
        for widget_name in (
            "btn_load_free_proxies",
            "btn_load_proxy_txt",
            "btn_check_proxy_health",
            "combo_proxy_source",
            "spin_proxy_health_timeout",
            "btn_use_proxies",
            "chk_proxy_health_before_go",
        ):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.setEnabled(enabled)

    def _run_proxy_health_check_only(self):
        proxies = self._collect_proxy_list_from_ui()
        if not proxies:
            QMessageBox.warning(
                self,
                self._t("trends.proxy_health.title", "Proxy Health"),
                self._t("trends.proxy_health.empty_list", "Proxy list is empty."),
            )
            return
        self._start_proxy_health_check(proxies, auto_start_fetch=False)

    def _start_proxy_health_check(self, proxies, auto_start_fetch=False):
        if self._proxy_health_worker is not None and self._proxy_health_worker.isRunning():
            QMessageBox.information(
                self,
                self._t("trends.proxy_health.title", "Proxy Health"),
                self._t("trends.proxy_health.already_running", "Proxy health check is already running."),
            )
            return False

        proxy_candidates = [str(p).strip() for p in (proxies or []) if str(p).strip()]
        if not proxy_candidates:
            QMessageBox.warning(
                self,
                self._t("trends.proxy_health.title", "Proxy Health"),
                self._t("trends.proxy_health.no_proxies", "No proxies to check."),
            )
            return False

        self._set_proxy_ui_busy(True)
        self._set_fetch_buttons_running(True)
        self._set_worker_status(f"Checking {len(proxy_candidates)} proxies...")

        self._proxy_health_worker = ProxyHealthCheckWorker(
            proxy_list=proxy_candidates,
            timeout_seconds=float(self._proxy_health_timeout_seconds),
        )
        self._proxy_health_worker.progress_signal.connect(self._set_worker_status)
        self._proxy_health_worker.error_signal.connect(self.on_trends_error)
        self._proxy_health_worker.finished_signal.connect(
            lambda alive, dead, elapsed, run_fetch=bool(auto_start_fetch): self._on_proxy_health_check_finished(
                alive, dead, elapsed, run_fetch
            )
        )
        self._proxy_health_worker.start()
        return True

    def _on_proxy_health_check_finished(self, alive, dead, elapsed_seconds, run_fetch):
        self._set_proxy_ui_busy(False)
        self._proxy_health_worker = None

        alive_count = len(alive)
        dead_count = len(dead)
        self._replace_proxy_list_in_ui(alive)

        base_msg = (
            f"Proxy health check done in {round(float(elapsed_seconds), 1)}s: "
            f"live {alive_count}, dead {dead_count}."
        )
        self._set_worker_status(base_msg)

        if not run_fetch:
            self._set_fetch_buttons_running(False)
            QMessageBox.information(self, self._t("trends.proxy_health.title", "Proxy Health"), base_msg)
            return

        pending_keywords = list(self._pending_keywords_after_proxy_check)
        self._pending_keywords_after_proxy_check = []
        if not pending_keywords:
            self._set_fetch_buttons_running(False)
            return

        if not alive:
            self._set_fetch_buttons_running(False)
            QMessageBox.warning(
                self,
                self._t("trends.proxy_health.title", "Proxy Health"),
                self._t("trends.proxy_health.no_live_proxies", "No live proxies found. Please load another list or disable proxy."),
            )
            return

        self._start_pytrends_fetch(
            pending_keywords,
            clear_table=True,
            proxy_override=alive,
        )

    @staticmethod
    def _http_get_text(url, timeout=20, headers=None):
        req_headers = headers or {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, timeout=timeout, headers=req_headers)
        response.raise_for_status()
        return response.text

    def _load_from_proxyscrape(self):
        endpoints = [
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
            "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxytype=http",
        ]
        loaded = []
        for url in endpoints:
            try:
                text = self._http_get_text(url, timeout=20)
                loaded.extend(parse_proxy_lines(text))
            except Exception:
                continue
        return self._dedupe_proxies(loaded)

    def _load_from_geonode(self):
        api_url = (
            "https://proxylist.geonode.com/api/proxy-list"
            "?limit=200&page=1&sort_by=lastChecked&sort_type=desc"
        )
        payload = requests.get(
            api_url,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        )
        payload.raise_for_status()
        data = payload.json() if payload.content else {}
        rows = data.get("data", []) if isinstance(data, dict) else []
        loaded = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            ip = str(row.get("ip", "")).strip()
            port = str(row.get("port", "")).strip()
            protocols = [str(x).lower() for x in row.get("protocols", []) if str(x).strip()]
            if not ip or not port:
                continue
            if "http" in protocols or "https" in protocols or not protocols:
                loaded.append(f"{ip}:{port}")
        return self._dedupe_proxies(parse_proxy_lines("\n".join(loaded)))

    def _load_from_free_proxy_list(self):
        html = self._http_get_text("https://free-proxy-list.net/", timeout=20)
        pattern = re.compile(r"<tr>\s*<td>(\d+\.\d+\.\d+\.\d+)</td>\s*<td>(\d+)</td>", re.IGNORECASE)
        found = [f"{ip}:{port}" for ip, port in pattern.findall(html)]
        return self._dedupe_proxies(parse_proxy_lines("\n".join(found)))

    def _load_from_webshare(self):
        token, ok = QInputDialog.getText(
            self,
            self._t("trends.webshare.title", "Webshare Token"),
            self._t("trends.webshare.prompt", "Enter your Webshare download token:"),
        )
        if not ok or not str(token).strip():
            return []

        url = f"https://proxy.webshare.io/api/v2/proxy/list/download/{token.strip()}/-/any/sourceip/direct/-/"
        text = self._http_get_text(url, timeout=25)
        return self._dedupe_proxies(parse_proxy_lines(text))

    def _load_free_proxies(self):
        if requests is None:
            QMessageBox.warning(self, self._t("trends.proxy.title", "Proxy"), self._t("trends.proxy.requests_required", "requests is required. Run: pip install requests"))
            return

        source = self.combo_proxy_source.currentText() if hasattr(self, "combo_proxy_source") else "ProxyScrape"
        self._show_status_message(self._t("trends.status.loading_free_proxies", "Loading free proxies from {source}...", source=source))
        QApplication.processEvents()

        try:
            if source == "Webshare.io":
                loaded = self._load_from_webshare()
            elif source == "ProxyScrape":
                loaded = self._load_from_proxyscrape()
            elif source == "GeoNode":
                loaded = self._load_from_geonode()
            else:
                loaded = self._load_from_free_proxy_list()
        except Exception as exc:
            QMessageBox.warning(
                self,
                self._t("trends.proxy.title", "Proxy"),
                self._t("trends.proxy.load_failed", "Failed to load proxies from {source}:\n{error}", source=source, error=exc),
            )
            self._show_status_message(self._t("trends.status.proxy_load_failed", "Proxy load failed from {source}.", source=source))
            return

        if not loaded:
            QMessageBox.information(
                self,
                self._t("trends.proxy.title", "Proxy"),
                self._t("trends.proxy.none_returned", "No proxies returned from {source}.", source=source),
            )
            self._show_status_message(self._t("trends.proxy.none_returned", "No proxies returned from {source}.", source=source))
            return

        added, total = self._merge_proxy_list_into_ui(loaded)
        self._show_status_message(
            self._t("trends.status.loaded_new_proxies", "Loaded {added} new proxies from {source}. Total: {total}", added=added, source=source, total=total)
        )

    def _refresh_status_label(self):
        total_text = self._t("trends.total_items", "Total Items: {count}", count=self.trends_table.rowCount())
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
        self._trends_default_widths = {
            0: 128,
            2: 120,
            3: 120,
            4: 115,
            5: 115,
            6: 95,
            7: 125,
            8: 108,
            9: 108,
            10: 116,
        }
        self._apply_trends_table_column_widths()

    def _update_chart_header_label(self):
        header_item = self.trends_table.horizontalHeaderItem(0)
        if header_item is None:
            header_item = QTableWidgetItem()
            self.trends_table.setHorizontalHeaderItem(0, header_item)
        chart_text = self._t("trends.table.chart", "Chart")
        header_item.setText(f"[x] {chart_text}" if self._chart_header_checked else f"[ ] {chart_text}")

    def _set_all_chart_checkboxes(self, checked):
        self._chart_check_syncing = True
        self.trends_table.blockSignals(True)
        try:
            target_state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            for row in range(self.trends_table.rowCount()):
                item = self.trends_table.item(row, 0)
                if item is None:
                    continue
                item.setFlags(
                    item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsEnabled
                )
                item.setCheckState(target_state)
        finally:
            self.trends_table.blockSignals(False)
            self._chart_check_syncing = False

        self._chart_header_checked = bool(checked)
        self._update_chart_header_label()
        if self._filter_checked_only:
            self._apply_trends_filters()

    def _refresh_chart_header_checked_state(self):
        row_count = self.trends_table.rowCount()
        if row_count <= 0:
            self._chart_header_checked = False
            self._update_chart_header_label()
            return

        all_checked = True
        for row in range(row_count):
            item = self.trends_table.item(row, 0)
            if item is None or item.checkState() != Qt.CheckState.Checked:
                all_checked = False
                break

        self._chart_header_checked = all_checked
        self._update_chart_header_label()

    def _on_trends_header_clicked(self, column):
        if column == 0:
            if self.trends_table.rowCount() <= 0:
                return
            self._set_all_chart_checkboxes(not self._chart_header_checked)
            return
        if column in TRENDS_NUMERIC_FILTER_COLUMNS:
            self._set_numeric_filter_dialog(column)

    def _on_trends_item_changed(self, item):
        if self._chart_check_syncing:
            return
        if item is None or item.column() != 0:
            return
        self._refresh_chart_header_checked_state()
        if self._filter_checked_only:
            self._apply_trends_filters()

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

    def _auto_fit_trends_column_widths(self):
        if self.trends_table.columnCount() <= 0:
            return

        header = self.trends_table.horizontalHeader()
        old_chart_width = self.trends_table.columnWidth(0)
        col_count = self.trends_table.columnCount()

        for col in range(col_count):
            if col == 0:
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            else:
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

        for col in range(col_count):
            if col != 0:
                self.trends_table.resizeColumnToContents(col)
            measured = self.trends_table.columnWidth(col) + 16
            if col in self._trends_col_bounds:
                min_w, max_w = self._trends_col_bounds[col]
                width = max(min_w, min(measured, max_w))
            elif col == 1:
                width = max(220, min(measured, 620))
            else:
                width = max(90, min(measured, 420))
            self.trends_table.setColumnWidth(col, width)

        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        for col in range(1, col_count):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)

        if self.trends_table.columnWidth(0) != old_chart_width:
            self._refresh_sparklines()
        self._show_status_message(self._t("trends.status.auto_fit_applied", "Auto-fit column widths applied."))

    def _reset_trends_column_widths(self):
        header = self.trends_table.horizontalHeader()
        old_chart_width = self.trends_table.columnWidth(0)

        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in range(2, self.trends_table.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)

        for col, width in self._trends_default_widths.items():
            self.trends_table.setColumnWidth(col, width)

        self._apply_trends_table_column_widths()

        if self.trends_table.columnWidth(0) != old_chart_width:
            self._refresh_sparklines()
        self._show_status_message(self._t("trends.status.column_widths_reset", "Column widths reset."))

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

    def _get_qwebengine_view_class(self):
        if self._qwebengine_import_attempted:
            return self._qwebengine_view_class

        self._qwebengine_import_attempted = True
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView as ImportedWebEngineView
        except Exception as exc:
            self._qwebengine_view_class = None
            self._webengine_error = str(exc)
            return None

        self._qwebengine_view_class = ImportedWebEngineView
        self._webengine_error = ""
        return self._qwebengine_view_class

    def _ensure_embedded_browser(self):
        if self.browser_view is not None:
            return True

        qwebengine_view_class = self._get_qwebengine_view_class()
        if qwebengine_view_class is None:
            self._webengine_available = False
            self._webengine_error = self._webengine_error or "PyQt6-WebEngine import failed."
            if self.browser_placeholder is not None:
                self.browser_placeholder.setText(
                    "Embedded browser could not load.\n"
                    "Install with:\npython -m pip install PyQt6-WebEngine\n\n"
                    f"Python: {sys.executable}\n"
                    f"Error: {self._webengine_error}"
                )
            return False

        try:
            self.browser_view = qwebengine_view_class()
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
        self._open_external_browser_sequence = not self._open_external_browser_sequence
        if self._open_external_browser_sequence:
            self.btn_trends_browser.setText(self._t("trends.browser.on", "Browser On"))
            self.btn_trends_browser.setStyleSheet(
                "background-color: #ff2b2b; color: white; border: none; font-weight: bold; border-radius: 4px;"
            )
            QMessageBox.information(
                self,
                self._t("trends.browser.mode_title", "Browser Mode"),
                self._t("trends.browser.on_message", "External browser auto-open is ON.\nTabs will be opened in background mode when possible."),
            )
        else:
            self.btn_trends_browser.setText(self._t("common.browser", "Browser"))
            self.btn_trends_browser.setStyleSheet(
                "background-color: #e50914; color: white; border: none; font-weight: bold; border-radius: 4px;"
            )
            QMessageBox.information(
                self,
                self._t("trends.browser.mode_title", "Browser Mode"),
                self._t("trends.browser.off_message", "External browser auto-open is OFF.\nGo will fetch data in app without popping browser tabs."),
            )

    def _show_browser_panel_for_sequence(self):
        self.browser_panel.hide()
        self.btn_trends_browser.setText(self._t("common.browser", "Browser"))
        total_width = max(900, self.trends_splitter.width())
        self.trends_splitter.setSizes([260, max(400, total_width - 260), 0])
        return True

    def _set_fetch_buttons_running(self, running):
        self.btn_trends_go.setVisible(not running)
        self.btn_trends_stop.setVisible(running)
        if not running:
            self.btn_trends_stop.setText(self._t("common.stop", "Stop"))

    def _is_pytrends_running(self):
        return hasattr(self, "trends_worker") and self.trends_worker.isRunning()

    def _build_browser_sequence_url(self, keyword):
        self._set_property_to_youtube()
        geo_code = GEO_MAP.get(self.t_combo_country.currentText(), "")
        encoded_geo = quote(geo_code, safe="")
        encoded_keyword = quote(str(keyword).strip(), safe="")
        date_code = TIME_MAP.get(self.t_combo_period.currentText(), "today 1-m")
        encoded_date = quote(date_code, safe="")
        cat_code = CAT_MAP.get(self.t_combo_cat.currentText(), 0)
        return (
            "https://trends.google.com/trends/explore"
            f"?geo={encoded_geo}&q={encoded_keyword}&gprop=youtube"
            f"&date={encoded_date}&cat={cat_code}"
        )

    def _finish_browser_sequence(self, stopped):
        self._browser_wait_timer.stop()
        self._browser_sequence_active = False
        self._browser_keywords_queue = []
        self._browser_keyword_index = 0
        if stopped:
            self._set_worker_status(self._t("trends.browser.stopped", "Opening in browser stopped."))
        else:
            self._set_worker_status(self._t("trends.browser.complete", "Opening in browser complete."))
        if not self._is_pytrends_running():
            self._set_fetch_buttons_running(False)

    def _load_next_browser_keyword(self):
        if not self._browser_sequence_active:
            return
        total = len(self._browser_keywords_queue)
        if self._browser_keyword_index >= total:
            self._finish_browser_sequence(stopped=False)
            return

        keyword = self._browser_keywords_queue[self._browser_keyword_index]
        idx = self._browser_keyword_index + 1
        geo_code = GEO_MAP.get(self.t_combo_country.currentText(), "")
        self._set_worker_status(
            self._t("trends.browser.opening", "Opening '{keyword}' in browser ({index}/{total}) with geo={geo}...", keyword=keyword, index=idx, total=total, geo=geo_code)
        )
        url = self._build_browser_sequence_url(keyword)
        try:
            # Background-friendly open: same browser window, avoid stealing focus when possible.
            webbrowser.open(url, new=0, autoraise=False)
        except Exception as exc:
            self._set_worker_status(
                self._t("trends.browser.open_failed", "Failed to open '{keyword}' in browser: {error}", keyword=keyword, error=exc)
            )
            self._finish_browser_sequence(stopped=True)
            return

        self._browser_keyword_index += 1
        wait_seconds = random.uniform(self._browser_wait_min_seconds, self._browser_wait_max_seconds)
        self._browser_wait_timer.start(max(1000, int(wait_seconds * 1000)))

    def _start_browser_sequence(self, keywords):
        if not self._show_browser_panel_for_sequence():
            return False

        self._browser_wait_timer.stop()
        self._browser_keywords_queue = list(keywords)
        self._browser_keyword_index = 0
        self._browser_sequence_active = True
        self._set_fetch_buttons_running(True)
        self._load_next_browser_keyword()
        return True

    def _start_pytrends_fetch(self, keywords, clear_table=True, proxy_override=None):
        if clear_table:
            self.trends_table.setRowCount(0)
            self._sparkline_cache.clear()
            self._chart_header_checked = False
            self._update_chart_header_label()
        self._sync_proxy_settings_to_main_window()
        proxy_settings = (
            self.main_window.get_proxy_settings()
            if self.main_window is not None and hasattr(self.main_window, "get_proxy_settings")
            else {"enabled": False, "proxies": []}
        )
        use_proxies = bool(proxy_settings.get("enabled", False))
        if proxy_override is not None:
            proxy_list = [str(p).strip() for p in proxy_override if str(p).strip()]
        else:
            proxy_list = list(proxy_settings.get("proxies", []))
        max_proxies_per_run = max(1, int(self.trends_settings.get("max_proxies_per_run", 30)))
        if proxy_list and proxy_override is None:
            proxy_list = proxy_list[:max_proxies_per_run]
        if use_proxies and not proxy_list:
            QMessageBox.warning(self, self._t("trends.proxy.title", "Proxy"), self._t("trends.proxy.enabled_but_empty", "Proxy is enabled but the list is empty."))
            return False

        self._set_worker_status(self._t("trends.status.starting_fetch", "Starting trends fetch..."))
        self.trends_table.setSortingEnabled(False)
        self._set_fetch_buttons_running(True)
        self.trends_worker = TrendsFetcherWorker(
            keywords,
            self.t_combo_country.currentText(),
            self.t_combo_period.currentText(),
            self.t_combo_cat.currentText(),
            self.t_combo_prop.currentText(),
            pause_after_connections=self.trends_settings.get("pause_after_connections", 20),
            pause_min_seconds=self.trends_settings.get("pause_min_seconds", 10),
            pause_max_seconds=self.trends_settings.get("pause_max_seconds", 60),
            enable_pause_after_connections=self.trends_settings.get("enable_pause_after_connections", True),
            max_workers=min(2, self.trends_settings.get("max_workers", 2)),
            use_proxies=use_proxies,
            proxy_list=proxy_list,
            enable_max_consecutive_proxy_connections=self.trends_settings.get(
                "enable_max_consecutive_proxy_connections",
                True,
            ),
            max_consecutive_web_connections_per_proxy=self.trends_settings.get(
                "max_consecutive_web_connections_per_proxy",
                50,
            ),
        )
        self.trends_worker.progress_signal.connect(self.on_trends_progress)
        self.trends_worker.finished_signal.connect(self.on_trends_finished)
        self.trends_worker.error_signal.connect(self.on_trends_error)
        self.trends_worker.status_signal.connect(self._set_worker_status)
        self.trends_worker.start()
        return True

    def _remove_processed_keyword_from_input(self, keyword):
        target = str(keyword).strip()
        if not target:
            return

        if not self._pending_input_keywords:
            self._pending_input_keywords = [
                line.strip()
                for line in self.trends_input.toPlainText().split("\n")
                if line.strip()
            ]

        removed = False
        for idx, item in enumerate(self._pending_input_keywords):
            if item == target:
                self._pending_input_keywords.pop(idx)
                removed = True
                break

        if removed:
            self.trends_input.blockSignals(True)
            self.trends_input.setPlainText("\n".join(self._pending_input_keywords))
            self.trends_input.blockSignals(False)

    def start_trends_fetch(self):
        text = self.trends_input.toPlainText()
        keywords = [line.strip() for line in text.split("\n") if line.strip()]
        if not keywords:
            QMessageBox.warning(
                self,
                self._t("trends.no_keywords_title", "No Keywords"),
                self._t("trends.no_keywords_message", "Please enter keywords."),
            )
            return

        self._pending_input_keywords = list(keywords)
        self.trends_input.blockSignals(True)
        self.trends_input.setPlainText("\n".join(self._pending_input_keywords))
        self.trends_input.blockSignals(False)

        # Always prioritize in-app data fetch so table can fill in real time.
        started = True
        if self._run_pytrends_with_external_browser:
            self._sync_proxy_settings_to_main_window()
            proxy_settings = (
                self.main_window.get_proxy_settings()
                if self.main_window is not None and hasattr(self.main_window, "get_proxy_settings")
                else {"enabled": False, "proxies": []}
            )
            use_proxies = bool(proxy_settings.get("enabled", False))
            proxy_list = list(proxy_settings.get("proxies", []))
            if use_proxies and self._proxy_health_check_before_go:
                max_proxies_per_run = max(1, int(self.trends_settings.get("max_proxies_per_run", 30)))
                proxy_list = proxy_list[:max_proxies_per_run]
                if not proxy_list:
                    QMessageBox.warning(self, self._t("trends.proxy.title", "Proxy"), self._t("trends.proxy.enabled_but_empty", "Proxy is enabled but the list is empty."))
                    return
                self._pending_keywords_after_proxy_check = list(keywords)
                started = self._start_proxy_health_check(proxy_list, auto_start_fetch=True)
            else:
                started = self._start_pytrends_fetch(keywords, clear_table=True)
        else:
            self._set_fetch_buttons_running(True)
        if not started:
            return

        # Optional external browser sequence (disabled by default to avoid UI focus jumps).
        if self._open_external_browser_sequence:
            self._start_browser_sequence(keywords)

    def stop_trends_fetch(self):
        if self._browser_sequence_active:
            self._finish_browser_sequence(stopped=True)

        if self._proxy_health_worker is not None and self._proxy_health_worker.isRunning():
            self._pending_keywords_after_proxy_check = []
            self._proxy_health_worker.stop()
            self.btn_trends_stop.setText(self._t("trends.stopping", "Stopping..."))
            self._set_worker_status(self._t("trends.status.stopping_proxy_health", "Stopping proxy health check..."))
            return

        if hasattr(self, "trends_worker") and self.trends_worker.isRunning():
            self.trends_worker.is_running = False
            self.btn_trends_stop.setText(self._t("trends.stopping", "Stopping..."))
            return

        if not self._browser_sequence_active:
            self._set_fetch_buttons_running(False)

    def on_trends_progress(self, data):
        row = self.trends_table.rowCount()
        self.trends_table.insertRow(row)

        raw_data = data.get("RawData") or []
        chart_item = QTableWidgetItem("")
        chart_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        chart_item.setFlags(
            chart_item.flags()
            | Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEnabled
        )
        chart_item.setCheckState(Qt.CheckState.Unchecked)
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

        self._remove_processed_keyword_from_input(data.get("Keyword", ""))

        self._refresh_status_label()
        self.trends_table.viewport().update()
        QApplication.processEvents()
        self._refresh_chart_header_checked_state()
        if self._filter_summary():
            self._apply_trends_filters()

    def on_trends_finished(self):
        if not self._browser_sequence_active:
            self._set_fetch_buttons_running(False)
        self.trends_table.setSortingEnabled(True)
        self.trends_table.sortItems(8, Qt.SortOrder.DescendingOrder)
        self._apply_trends_table_column_widths()
        self._set_worker_status(self._t("trends.status.fetch_completed", "Trends fetch completed."))

        QMessageBox.information(
            self,
            self._t("common.finished", "Finished"),
            self._t("trends.finished_message", "Trends data fetching complete!"),
        )

    def on_trends_error(self, err):
        if not self._browser_sequence_active:
            self._set_fetch_buttons_running(False)
        self._set_worker_status(f"{self._t('common.error', 'Error')}: {err}")
        QMessageBox.critical(self, self._t("common.error", "Error"), err)

    def show_trend_chart(self, row, column):
        if column != 0:
            return

        chart_item = self.trends_table.item(row, 0)
        if chart_item is None:
            return

        payload = chart_item.data(Qt.ItemDataRole.UserRole)
        if not payload:
            QMessageBox.information(
                self,
                self._t("common.no_data", "No Data"),
                self._t("trends.chart.no_data_for_keyword", "No trend data available for this keyword."),
            )
            return

        dialog = TrendChartDialog(
            keyword=payload.get("keyword", ""),
            raw_data=payload.get("raw_data", []),
            google_trends_url=payload.get("google_trends_url", ""),
            dark_theme=self.trends_settings.get("dark_theme_charts", True),
            language=self.current_language,
            parent=self,
        )
        dialog.exec()

    def _selected_trend_rows(self):
        return sorted({idx.row() for idx in self.trends_table.selectedIndexes()})

    def _checked_trend_rows(self):
        rows = []
        for row in range(self.trends_table.rowCount()):
            item = self.trends_table.item(row, 0)
            if item is None:
                continue
            try:
                if item.checkState() == Qt.CheckState.Checked:
                    rows.append(row)
            except Exception:
                continue
        return rows

    def _rows_for_selected_actions(self):
        # Prefer explicit checkbox selections in column 0.
        checked = self._checked_trend_rows()
        if checked:
            return sorted(checked)
        # Fallback to highlighted row selections.
        return self._selected_trend_rows()

    def _keyword_at_row(self, row):
        item = self.trends_table.item(row, 1)
        return item.text().strip() if item is not None else ""

    def _keywords_from_rows(self, rows):
        return [kw for kw in (self._keyword_at_row(r) for r in rows) if kw]

    def _selected_keywords(self):
        return self._keywords_from_rows(self._rows_for_selected_actions())

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

    def _show_next_steps_message(self):
        QMessageBox.information(
            self,
            self._t("common.coming_soon", "Coming Soon"),
            self._t("common.next_steps_message", "This feature will be implemented in the next steps"),
        )

    def _add_context_action(self, menu, text, callback, icon=None):
        action = menu.addAction(text)
        if icon is not None:
            action.setIcon(self.style().standardIcon(icon))
        action.triggered.connect(lambda _checked=False, cb=callback: cb())
        return action

    def _warn_select_rows(self):
        QMessageBox.warning(
            self,
            self._t("common.no_selection", "No Selection"),
            self._t("trends.select_at_least_one_row", "Please select at least one row"),
        )

    def _require_selected_keywords(self):
        keywords = self._selected_keywords()
        if not keywords:
            self._warn_select_rows()
            return []
        return keywords

    def _require_selected_rows(self):
        rows = self._rows_for_selected_actions()
        if not rows:
            self._warn_select_rows()
            return []
        return rows

    def _send_to_video_search_tool(self):
        keywords = self._require_selected_keywords()
        if not keywords:
            return
        if self.main_window is not None:
            self.main_window.handle_send_to_videos(keywords, source_tool="Trends")
            return
        print(f"[Trends] Sent to Video search tool: {keywords}")
        QMessageBox.information(self, self._t("main.nav.trends", "Trends"), self._t("trends.sent_video", "Sent to Video search tool"))

    def _send_to_channel_search_tool(self):
        keywords = self._require_selected_keywords()
        if not keywords:
            return
        QMessageBox.information(self, self._t("main.nav.trends", "Trends"), self._t("trends.sent_channel", "Sent to Channel search tool"))

    def _send_selected_to_keywords_tool(self):
        keywords = self._require_selected_keywords()
        if not keywords:
            return
        if self.main_window is not None and hasattr(self.main_window, "handle_send_trends_to_keywords"):
            self.main_window.handle_send_trends_to_keywords(keywords, source_tool="Trends")
            return
        QMessageBox.information(self, self._t("main.nav.trends", "Trends"), self._t("trends.sent_selected_keywords", "Sent selected keywords to Keywords tool"))

    def _send_all_to_keywords_tool(self):
        keywords = self._all_keywords()
        if not keywords:
            QMessageBox.warning(self, self._t("common.no_data", "No Data"), self._t("trends.no_keywords_in_table", "No keywords in the table"))
            return
        if self.main_window is not None and hasattr(self.main_window, "handle_send_trends_to_keywords"):
            self.main_window.handle_send_trends_to_keywords(keywords, source_tool="Trends")
            return
        QMessageBox.information(self, self._t("main.nav.trends", "Trends"), self._t("trends.sent_all_keywords", "Sent all keywords to Keywords tool"))

    def _get_search_volume_for_selected(self):
        keywords = self._require_selected_keywords()
        if not keywords:
            return
        QMessageBox.information(self, self._t("main.nav.trends", "Trends"), self._t("trends.getting_search_volume", "Getting search volume for selected keywords..."))

    def _send_selected_to_keywords_everywhere(self):
        keywords = self._require_selected_keywords()
        if not keywords:
            return
        QMessageBox.information(self, "Trends", "Sent SELECTED to Keywords Everywhere tool")

    def _send_all_to_keywords_everywhere(self):
        keywords = self._all_keywords()
        if not keywords:
            QMessageBox.warning(self, "No Data", "No keywords in the table")
            return
        QMessageBox.information(self, "Trends", "Sent ALL to Keywords Everywhere tool")

    def _rows_to_text_lines(self, rows):
        lines = []
        for row in rows:
            parts = []
            for col in range(1, self.trends_table.columnCount()):
                item = self.trends_table.item(row, col)
                parts.append(item.text().strip() if item is not None else "")
            if any(parts):
                lines.append("\t".join(parts))
        return lines

    def _copy_to_clipboard(self, text, success_message):
        if not text:
            return
        QApplication.clipboard().setText(text)
        self._show_status_message(success_message)

    def _copy_selected_rows_to_clipboard(self):
        rows = self._require_selected_rows()
        if not rows:
            return
        lines = self._rows_to_text_lines(rows)
        self._copy_to_clipboard("\n".join(lines), f"Copied {len(lines)} selected row(s).")

    def _copy_all_rows_to_clipboard(self):
        rows = list(range(self.trends_table.rowCount()))
        if not rows:
            QMessageBox.warning(self, "No Data", "No rows in the table")
            return
        lines = self._rows_to_text_lines(rows)
        self._copy_to_clipboard("\n".join(lines), f"Copied ALL {len(lines)} row(s).")

    def _copy_highlighted_items_to_clipboard(self):
        items = self.trends_table.selectedItems()
        if not items:
            self._warn_select_rows()
            return
        text = "\n".join(item.text().strip() for item in items if item.text().strip())
        self._copy_to_clipboard(text, f"Copied {len(items)} highlighted item(s).")

    def _copy_selected_keywords_to_clipboard(self, comma_separated=False):
        keywords = self._require_selected_keywords()
        if not keywords:
            return
        sep = ", " if comma_separated else "\n"
        self._copy_to_clipboard(
            sep.join(keywords),
            f"Copied {len(keywords)} selected keyword(s).",
        )

    def _copy_all_keywords_to_clipboard(self, comma_separated=False):
        keywords = self._all_keywords()
        if not keywords:
            QMessageBox.warning(self, "No Data", "No keywords in the table")
            return
        sep = ", " if comma_separated else "\n"
        self._copy_to_clipboard(
            sep.join(keywords),
            f"Copied ALL {len(keywords)} keyword(s).",
        )

    def _delete_selected_rows_with_confirm(self):
        rows = self._require_selected_rows()
        if not rows:
            return
        confirm = QMessageBox.question(
            self,
            "Delete Rows",
            f"Delete {len(rows)} selected row(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        for row in reversed(rows):
            self.trends_table.removeRow(row)
        self._refresh_sparklines()
        self._refresh_chart_header_checked_state()
        self._refresh_status_label()
        self._show_status_message(f"Deleted {len(rows)} row(s).")

    def _toggle_row_selection(self):
        rows = self._selected_trend_rows()
        if not rows:
            self._warn_select_rows()
            return

        all_checked = True
        for row in rows:
            item = self.trends_table.item(row, 0)
            if item is None or item.checkState() != Qt.CheckState.Checked:
                all_checked = False
                break

        new_state = Qt.CheckState.Unchecked if all_checked else Qt.CheckState.Checked
        for row in rows:
            item = self.trends_table.item(row, 0)
            if item is None:
                continue
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEnabled
            )
            item.setCheckState(new_state)

        self._refresh_chart_header_checked_state()
        state_text = "Checked" if new_state == Qt.CheckState.Checked else "Unchecked"
        self._show_status_message(f"{state_text} {len(rows)} row(s).")

    def _focus_search_input(self):
        self.trends_input.setFocus()
        self.trends_input.selectAll()

    def _search_keywords_with_engine(self, engine, keywords, scope_label):
        clean_keywords = [str(k).strip() for k in keywords if str(k).strip()]
        if not clean_keywords:
            QMessageBox.warning(self, "Search", f"No keywords available for {scope_label}.")
            return

        if len(clean_keywords) > 12:
            confirm = QMessageBox.question(
                self,
                "Search",
                f"This will open {len(clean_keywords)} browser tabs for {scope_label}.\nContinue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        try:
            from utils.helpers import web_search
        except Exception as exc:
            QMessageBox.critical(self, "Search Error", f"Cannot load web search helper:\n{exc}")
            return

        opened = 0
        for keyword in clean_keywords:
            try:
                web_search(engine, keyword)
                opened += 1
            except Exception:
                continue

        if opened <= 0:
            QMessageBox.warning(self, "Search", "No browser tabs were opened.")
            return
        self._show_status_message(f"Opened {opened} tab(s) on {engine} for {scope_label}.")

    def _search_current_row_with_engine(self, engine):
        row = getattr(self, "_context_menu_row", -1)
        if row is None or row < 0:
            rows = self._selected_trend_rows()
            row = rows[0] if rows else -1
        if row < 0:
            self._warn_select_rows()
            return
        keyword = self._keyword_at_row(row)
        self._search_keywords_with_engine(engine, [keyword], "current row")

    def _search_selected_with_engine(self, engine):
        keywords = self._selected_keywords()
        if not keywords:
            self._warn_select_rows()
            return
        self._search_keywords_with_engine(engine, keywords, "selected rows")

    def _search_all_with_engine(self, engine):
        keywords = self._all_keywords()
        self._search_keywords_with_engine(engine, keywords, "all rows")

    def _build_search_scope_submenu(self, parent_menu, scope_title, callback):
        engines = [
            "Google Trends",
            "Google Search",
            "YouTube Search",
            "Bing Search",
            "Amazon",
            "eBay",
        ]
        scope_menu = QMenu(scope_title, parent_menu)
        for engine in engines:
            action = scope_menu.addAction(engine)
            action.triggered.connect(lambda _checked=False, e=engine, cb=callback: cb(e))
        return scope_menu

    def _text_at(self, row, col):
        item = self.trends_table.item(row, col)
        return item.text().strip() if item is not None else ""

    @staticmethod
    def _parse_numeric_value(raw_value):
        text = str(raw_value or "").strip()
        if not text:
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

    def _selected_row_for_filter(self):
        rows = self._selected_trend_rows()
        if not rows:
            self._warn_select_rows()
            return -1
        return rows[0]

    def _set_numeric_filter_dialog(self, column):
        column_name = TRENDS_NUMERIC_FILTER_COLUMNS.get(column, f"Column {column}")
        current = str(self._filter_numeric_rules.get(column, "")).strip()
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
            self._filter_numeric_rules.pop(column, None)
            self._apply_trends_filters()
            return

        if self._evaluate_numeric_rule(1.0, expr) is None:
            QMessageBox.warning(
                self,
                "Filter",
                "Numeric filter format is invalid. Use examples like >10, >=100, <5, =0.",
            )
            return

        self._filter_numeric_rules[column] = expr
        self._apply_trends_filters()

    def _filter_summary(self):
        tags = []
        if self._filter_keyword_text:
            tags.append(f"keyword~'{self._filter_keyword_text}'")
        if self._filter_country_value:
            tags.append(f"country='{self._filter_country_value}'")
        if self._filter_category_value:
            tags.append(f"category='{self._filter_category_value}'")
        if self._filter_property_value:
            tags.append(f"property='{self._filter_property_value}'")
        if self._filter_checked_only:
            tags.append("checked-only")
        for column, expression in sorted(self._filter_numeric_rules.items()):
            column_name = TRENDS_NUMERIC_FILTER_COLUMNS.get(column, f"col{column}")
            tags.append(f"{column_name}{expression}")
        return ", ".join(tags)

    def _apply_trends_filters(self):
        total = self.trends_table.rowCount()
        visible = 0
        keyword_filter = self._filter_keyword_text.lower().strip()

        for row in range(total):
            row_visible = True

            if keyword_filter:
                kw_text = self._text_at(row, 1).lower()
                if keyword_filter not in kw_text:
                    row_visible = False

            if row_visible and self._filter_country_value:
                row_visible = self._text_at(row, 2) == self._filter_country_value

            if row_visible and self._filter_category_value:
                row_visible = self._text_at(row, 4) == self._filter_category_value

            if row_visible and self._filter_property_value:
                row_visible = self._text_at(row, 5) == self._filter_property_value

            if row_visible and self._filter_checked_only:
                chart_item = self.trends_table.item(row, 0)
                row_visible = chart_item is not None and chart_item.checkState() == Qt.CheckState.Checked

            if row_visible and self._filter_numeric_rules:
                for column, expression in self._filter_numeric_rules.items():
                    parsed_value = self._parse_numeric_value(self._text_at(row, column))
                    if parsed_value is None or self._evaluate_numeric_rule(parsed_value, expression) is not True:
                        row_visible = False
                        break

            self.trends_table.setRowHidden(row, not row_visible)
            if row_visible:
                visible += 1

        summary = self._filter_summary()
        if summary:
            self._show_status_message(f"Filters applied: {summary} • Visible {visible}/{total}")
        else:
            self._show_status_message(f"Filters cleared • Visible {visible}/{total}")

    def _clear_trends_filters(self, update_ui=True):
        self._filter_keyword_text = ""
        self._filter_country_value = ""
        self._filter_category_value = ""
        self._filter_property_value = ""
        self._filter_checked_only = False
        self._filter_numeric_rules = {}
        if update_ui:
            self._apply_trends_filters()

    def _set_keyword_filter_dialog(self):
        current = self._filter_keyword_text
        text, ok = QInputDialog.getText(
            self,
            "Filter Keywords",
            "Keyword contains:",
            text=current,
        )
        if not ok:
            return
        self._filter_keyword_text = text.strip()
        self._apply_trends_filters()

    def _set_country_filter_from_selected(self):
        row = self._selected_row_for_filter()
        if row < 0:
            return
        value = self._text_at(row, 2)
        if not value:
            QMessageBox.warning(self, "Filter", "Selected row has no Country value.")
            return
        self._filter_country_value = value
        self._apply_trends_filters()

    def _set_category_filter_from_selected(self):
        row = self._selected_row_for_filter()
        if row < 0:
            return
        value = self._text_at(row, 4)
        if not value:
            QMessageBox.warning(self, "Filter", "Selected row has no Category value.")
            return
        self._filter_category_value = value
        self._apply_trends_filters()

    def _set_property_filter_from_selected(self):
        row = self._selected_row_for_filter()
        if row < 0:
            return
        value = self._text_at(row, 5)
        if not value:
            QMessageBox.warning(self, "Filter", "Selected row has no Property value.")
            return
        self._filter_property_value = value
        self._apply_trends_filters()

    def _toggle_checked_only_filter(self):
        self._filter_checked_only = not self._filter_checked_only
        self._apply_trends_filters()

    def _clear_keyword_filter_only(self):
        self._filter_keyword_text = ""
        self._apply_trends_filters()

    def _clear_country_filter_only(self):
        self._filter_country_value = ""
        self._apply_trends_filters()

    def _clear_category_filter_only(self):
        self._filter_category_value = ""
        self._apply_trends_filters()

    def _clear_property_filter_only(self):
        self._filter_property_value = ""
        self._apply_trends_filters()

    def show_trends_context_menu(self, pos):
        row = self.trends_table.rowAt(pos.y())
        if row < 0:
            return
        self._context_menu_row = row
        if row >= 0 and row not in self._selected_trend_rows():
            self.trends_table.selectRow(row)

        menu = QMenu(self)
        menu.setStyleSheet(
            """
            QMenu {
                background-color: #f4f4f4;
                color: #222222;
                border: 1px solid #a8a8a8;
            }
            QMenu::item {
                padding: 6px 26px;
                margin: 1px 4px;
            }
            QMenu::item:selected {
                background-color: #f1d5df;
                color: #111111;
            }
            QMenu::separator {
                height: 1px;
                background: #d0d0d0;
                margin: 4px 8px;
            }
            """
        )

        self._add_context_action(
            menu,
            self._t("trends.menu.send_video", "Send to Video search tool"),
            self._send_to_video_search_tool,
            QStyle.StandardPixmap.SP_MediaPlay,
        )
        self._add_context_action(
            menu,
            self._t("trends.menu.send_channel", "Send to Channel search tool"),
            self._send_to_channel_search_tool,
            QStyle.StandardPixmap.SP_FileDialogInfoView,
        )
        self._add_context_action(
            menu,
            self._t("trends.menu.send_selected_keywords", "Send SELECTED to Keywords tool"),
            self._send_selected_to_keywords_tool,
            QStyle.StandardPixmap.SP_ArrowBack,
        )
        self._add_context_action(
            menu,
            self._t("trends.menu.send_all_keywords", "Send ALL to Keywords tool"),
            self._send_all_to_keywords_tool,
            QStyle.StandardPixmap.SP_ArrowLeft,
        )
        self._add_context_action(
            menu,
            self._t("trends.menu.get_search_volume", "Get Search Volume"),
            self._get_search_volume_for_selected,
            QStyle.StandardPixmap.SP_FileDialogDetailedView,
        )
        self._add_context_action(
            menu,
            self._t("trends.menu.send_selected_ke", "Send SELECTED to Keywords Everywhere tool"),
            self._send_selected_to_keywords_everywhere,
            QStyle.StandardPixmap.SP_ArrowForward,
        )
        self._add_context_action(
            menu,
            self._t("trends.menu.send_all_ke", "Send ALL to Keywords Everywhere tool"),
            self._send_all_to_keywords_everywhere,
            QStyle.StandardPixmap.SP_CommandLink,
        )
        self._add_context_action(
            menu,
            self._t("trends.menu.checkboxes", "Checkboxes"),
            self._toggle_row_selection,
            QStyle.StandardPixmap.SP_DialogApplyButton,
        )
        filters_menu = QMenu(self._t("common.filters", "Filters"), menu)
        filters_menu.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogResetButton))

        action_kw = filters_menu.addAction(self._t("trends.menu.filter_keyword_contains", "Keyword contains..."))
        action_kw.triggered.connect(self._set_keyword_filter_dialog)

        action_country = filters_menu.addAction(self._t("trends.menu.filter_country_selected", "Country = selected row"))
        action_country.triggered.connect(self._set_country_filter_from_selected)

        action_category = filters_menu.addAction(self._t("trends.menu.filter_category_selected", "Category = selected row"))
        action_category.triggered.connect(self._set_category_filter_from_selected)

        action_property = filters_menu.addAction(self._t("trends.menu.filter_property_selected", "Property = selected row"))
        action_property.triggered.connect(self._set_property_filter_from_selected)

        filters_menu.addSeparator()

        action_checked_only = filters_menu.addAction(self._t("trends.menu.filter_checked_only", "Checked rows only"))
        action_checked_only.setCheckable(True)
        action_checked_only.setChecked(self._filter_checked_only)
        action_checked_only.triggered.connect(self._toggle_checked_only_filter)

        filters_menu.addSeparator()

        clear_keyword = filters_menu.addAction(self._t("trends.menu.clear_keyword_filter", "Clear keyword filter"))
        clear_keyword.triggered.connect(self._clear_keyword_filter_only)

        clear_country = filters_menu.addAction(self._t("trends.menu.clear_country_filter", "Clear country filter"))
        clear_country.triggered.connect(self._clear_country_filter_only)

        clear_category = filters_menu.addAction(self._t("trends.menu.clear_category_filter", "Clear category filter"))
        clear_category.triggered.connect(self._clear_category_filter_only)

        clear_property = filters_menu.addAction(self._t("trends.menu.clear_property_filter", "Clear property filter"))
        clear_property.triggered.connect(self._clear_property_filter_only)

        clear_all = filters_menu.addAction(self._t("trends.menu.clear_all_filters", "Clear all filters"))
        clear_all.triggered.connect(lambda: self._clear_trends_filters(update_ui=True))

        menu.addMenu(filters_menu)

        menu.addSeparator()

        copy_menu = QMenu(self._t("common.copy", "Copy"), menu)
        copy_menu.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        copy_items = [
            self._t("trends.menu.copy_selected_rows", "Copy SELECTED rows to clipboard"),
            self._t("trends.menu.copy_all_rows", "Copy ALL rows to clipboard"),
            self._t("trends.menu.copy_highlighted_items", "Copy HIGHLIGHTED items to clipboard"),
            self._t("trends.menu.copy_selected_keywords", "Copy SELECTED keywords to clipboard"),
            self._t("trends.menu.copy_all_keywords", "Copy ALL keywords to clipboard"),
            self._t("trends.menu.copy_selected_keywords_csv", "Copy SELECTED comma separated keywords to clipboard"),
            self._t("trends.menu.copy_all_keywords_csv", "Copy ALL comma separated keywords to clipboard"),
        ]
        copy_handlers = [
            self._copy_selected_rows_to_clipboard,
            self._copy_all_rows_to_clipboard,
            self._copy_highlighted_items_to_clipboard,
            lambda: self._copy_selected_keywords_to_clipboard(comma_separated=False),
            lambda: self._copy_all_keywords_to_clipboard(comma_separated=False),
            lambda: self._copy_selected_keywords_to_clipboard(comma_separated=True),
            lambda: self._copy_all_keywords_to_clipboard(comma_separated=True),
        ]
        for label, handler in zip(copy_items, copy_handlers):
            sub_action = copy_menu.addAction(label)
            sub_action.triggered.connect(lambda _checked=False, cb=handler: cb())
        menu.addMenu(copy_menu)

        hashtags_menu = QMenu(self._t("common.hashtags", "Hashtags"), menu)
        hashtags_menu.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        hash_action = hashtags_menu.addAction(self._t("trends.menu.hashtag_options", "Hashtags options"))
        hash_action.triggered.connect(lambda _checked=False: self._show_next_steps_message())
        menu.addMenu(hashtags_menu)

        search_menu = QMenu(self._t("common.search", "Search"), menu)
        search_menu.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView))
        search_menu.addMenu(self._build_search_scope_submenu(search_menu, self._t("trends.menu.current_row", "Current row"), self._search_current_row_with_engine))
        search_menu.addMenu(self._build_search_scope_submenu(search_menu, self._t("trends.menu.selected_rows", "SELECTED rows"), self._search_selected_with_engine))
        search_menu.addMenu(self._build_search_scope_submenu(search_menu, self._t("trends.menu.all_rows", "ALL rows"), self._search_all_with_engine))
        menu.addMenu(search_menu)
        self._add_context_action(
            menu,
            self._t("trends.menu.auto_fit", "Auto-fit column widths"),
            self._auto_fit_trends_column_widths,
            QStyle.StandardPixmap.SP_TitleBarShadeButton,
        )
        self._add_context_action(
            menu,
            self._t("trends.menu.reset_widths", "Reset column widths"),
            self._reset_trends_column_widths,
            QStyle.StandardPixmap.SP_BrowserReload,
        )
        self._add_context_action(
            menu,
            self._t("common.delete", "Delete"),
            self._delete_selected_rows_with_confirm,
            QStyle.StandardPixmap.SP_TrashIcon,
        )

        menu.exec(self.trends_table.viewport().mapToGlobal(pos))

    def open_settings_dialog(self):
        dialog = TrendsSettingsDialog(self.trends_settings, language=self.current_language, parent=self)
        if dialog.exec():
            self.trends_settings = dialog.get_settings()
            if self.main_window is not None and hasattr(self.main_window, "set_proxy_runtime_settings"):
                self.main_window.set_proxy_runtime_settings(
                    max_proxies_per_run=int(self.trends_settings.get("max_proxies_per_run", 30))
                )

    def closeEvent(self, event):
        try:
            self._browser_wait_timer.stop()
        except Exception:
            pass

        try:
            if self._proxy_health_worker is not None and self._proxy_health_worker.isRunning():
                self._proxy_health_worker.stop()
                self._proxy_health_worker.wait(1200)
        except Exception:
            pass

        try:
            if hasattr(self, "trends_worker") and self.trends_worker is not None and self.trends_worker.isRunning():
                self.trends_worker.is_running = False
                self.trends_worker.wait(1500)
        except Exception:
            pass

        try:
            if self.browser_view is not None:
                self.browser_view.stop()
        except Exception:
            pass

        super().closeEvent(event)
