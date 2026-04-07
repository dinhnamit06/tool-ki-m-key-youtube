from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton, QVBoxLayout, QWidget

from core.rpm_data import build_sample_channels
from core.rpm_predictor import RPMPredictorService


def _fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", ".")


class PredictorMetricCard(QFrame):
    def __init__(self, title: str, value: str, parent=None):
        super().__init__(parent)
        self.setObjectName("metric_card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(4)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color:#e8fbff; font-size:11px;")
        layout.addWidget(lbl_title)

        lbl_value = QLabel(value)
        lbl_value.setStyleSheet("color:#ffffff; font-size:19px; font-weight:800;")
        lbl_value.setWordWrap(True)
        layout.addWidget(lbl_value)


class RPMPredictorPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.channels = build_sample_channels()
        self.service = RPMPredictorService(self.channels)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

        topbar = QFrame()
        topbar.setObjectName("topbar")
        top_layout = QHBoxLayout(topbar)
        top_layout.setContentsMargins(18, 18, 18, 18)
        top_layout.setSpacing(12)

        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["Channel"])
        self.cmb_mode.setFixedWidth(130)
        top_layout.addWidget(self.cmb_mode)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search a channel...")
        self.search_input.returnPressed.connect(self._predict)
        top_layout.addWidget(self.search_input, 1)

        self.btn_predict_top = QPushButton("Get RPM")
        self.btn_predict_top.setObjectName("primary_btn")
        self.btn_predict_top.clicked.connect(self._predict)
        top_layout.addWidget(self.btn_predict_top)
        root.addWidget(topbar)

        hero = QFrame()
        hero.setObjectName("content_card")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(28, 28, 28, 28)
        hero_layout.setSpacing(16)

        title = QLabel("RPM Predictor")
        title.setObjectName("app_title")
        hero_layout.addWidget(title)

        subtitle = QLabel("AI Powered RPM Predictor")
        subtitle.setObjectName("muted_label")
        hero_layout.addWidget(subtitle)

        center_row = QHBoxLayout()
        center_row.setSpacing(12)
        self.center_input = QLineEdit()
        self.center_input.setPlaceholderText("Enter a channel name to estimate RPM...")
        self.center_input.returnPressed.connect(self._predict)
        center_row.addWidget(self.center_input, 1)

        self.btn_get_rpm = QPushButton("Get RPM")
        self.btn_get_rpm.setObjectName("accent_btn")
        self.btn_get_rpm.clicked.connect(self._predict)
        center_row.addWidget(self.btn_get_rpm)
        hero_layout.addLayout(center_row)

        self.lbl_hint = QLabel("Try a sample channel like: Space Matters, Stories To Remember, Navy Productions")
        self.lbl_hint.setObjectName("muted_label")
        hero_layout.addWidget(self.lbl_hint)
        root.addWidget(hero)

        body = QHBoxLayout()
        body.setSpacing(18)

        left_card = QFrame()
        left_card.setObjectName("content_card")
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(18, 18, 18, 18)
        left_layout.setSpacing(12)
        left_title = QLabel("Suggestions")
        left_title.setObjectName("section_title")
        left_layout.addWidget(left_title)
        left_hint = QLabel("Local sample channels used by the current predictor.")
        left_hint.setObjectName("muted_label")
        left_hint.setWordWrap(True)
        left_layout.addWidget(left_hint)
        self.list_suggestions = QListWidget()
        self.list_suggestions.itemDoubleClicked.connect(self._use_suggestion)
        left_layout.addWidget(self.list_suggestions, 1)
        body.addWidget(left_card, 0)

        right_wrap = QVBoxLayout()
        right_wrap.setSpacing(18)

        result_card = QFrame()
        result_card.setObjectName("content_card")
        result_layout = QVBoxLayout(result_card)
        result_layout.setContentsMargins(22, 22, 22, 22)
        result_layout.setSpacing(12)

        self.lbl_result_title = QLabel("No prediction yet")
        self.lbl_result_title.setObjectName("section_title")
        result_layout.addWidget(self.lbl_result_title)

        self.lbl_result_sub = QLabel("Run a prediction to see RPM, confidence, and matching details.")
        self.lbl_result_sub.setObjectName("muted_label")
        self.lbl_result_sub.setWordWrap(True)
        result_layout.addWidget(self.lbl_result_sub)

        self.result_metrics = QWidget()
        metrics_layout = QGridLayout(self.result_metrics)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setHorizontalSpacing(14)
        metrics_layout.setVerticalSpacing(12)
        self.metric_rpm = PredictorMetricCard("Predicted RPM", "--")
        self.metric_conf = PredictorMetricCard("Confidence", "--")
        self.metric_rev = PredictorMetricCard("Avg. Monthly Revenue", "--")
        self.metric_views = PredictorMetricCard("Avg. Monthly Views", "--")
        metrics_layout.addWidget(self.metric_rpm, 0, 0)
        metrics_layout.addWidget(self.metric_conf, 0, 1)
        metrics_layout.addWidget(self.metric_rev, 1, 0)
        metrics_layout.addWidget(self.metric_views, 1, 1)
        result_layout.addWidget(self.result_metrics)
        right_wrap.addWidget(result_card)

        detail_card = QFrame()
        detail_card.setObjectName("content_card")
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(22, 22, 22, 22)
        detail_layout.setSpacing(10)
        detail_title = QLabel("Prediction Details")
        detail_title.setObjectName("section_title")
        detail_layout.addWidget(detail_title)
        self.lbl_detail = QLabel("Matched channel, note, and supporting metrics will appear here.")
        self.lbl_detail.setWordWrap(True)
        self.lbl_detail.setStyleSheet("color:#334155;")
        detail_layout.addWidget(self.lbl_detail)
        right_wrap.addWidget(detail_card)

        body.addLayout(right_wrap, 1)
        root.addLayout(body, 1)

        self._refresh_suggestions()

    def _refresh_suggestions(self, query: str = ""):
        self.list_suggestions.clear()
        for title in self.service.suggest(query):
            self.list_suggestions.addItem(title)

    def _use_suggestion(self, item):
        text = item.text().strip()
        self.search_input.setText(text)
        self.center_input.setText(text)
        self._predict()

    def _predict(self):
        query = self.center_input.text().strip() or self.search_input.text().strip()
        self.search_input.setText(query)
        self.center_input.setText(query)
        self._refresh_suggestions(query)
        result = self.service.predict_channel_rpm(query)
        if result is None:
            self.lbl_result_title.setText("No local channel match found")
            self.lbl_result_sub.setText("Try a closer sample channel title or wire the predictor to a real data source later.")
            self._set_metric_values("--", "--", "--", "--")
            self.lbl_detail.setText(
                "The local predictor only knows the sample dataset right now. Use a title close to the seeded channels, or implement a remote source in a later RPM step."
            )
            return

        self.lbl_result_title.setText(f"Predicted RPM for {result.matched_channel}")
        self.lbl_result_sub.setText(
            f"Query: {result.query} | Confidence: {result.confidence_label} ({result.confidence_score:.2f})"
        )
        self._set_metric_values(
            f"{result.predicted_rpm:.2f}",
            result.confidence_label,
            f"$ {_fmt_int(result.avg_monthly_revenue)}",
            _fmt_int(result.avg_monthly_views),
        )
        monetized_text = "Yes" if result.monetized else "No"
        self.lbl_detail.setText(
            f"Matched channel: {result.matched_channel}\n"
            f"Monetized: {monetized_text}\n"
            f"Avg. views per video: {_fmt_int(result.avg_views_per_video)}\n"
            f"Total revenue generated: $ {_fmt_int(result.total_revenue_generated)}\n"
            f"Note: {result.note}"
        )
        window = self.window()
        if hasattr(window, "statusBar"):
            window.statusBar().showMessage(f"Predicted RPM for {result.matched_channel}.", 2500)

    def _set_metric_values(self, rpm_text: str, confidence_text: str, revenue_text: str, views_text: str):
        self._set_metric_card_value(self.metric_rpm, rpm_text)
        self._set_metric_card_value(self.metric_conf, confidence_text)
        self._set_metric_card_value(self.metric_rev, revenue_text)
        self._set_metric_card_value(self.metric_views, views_text)

    @staticmethod
    def _set_metric_card_value(card: QWidget, value: str):
        labels = card.findChildren(QLabel)
        if len(labels) >= 2:
            labels[1].setText(value)
