from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from core.rpm_data import ChannelRecord


def _fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", ".")


class MetricTile(QFrame):
    def __init__(self, title: str, value: str):
        super().__init__()
        self.setObjectName("metric_card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setStyleSheet("color:#e8fbff; font-size:12px;")
        layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setStyleSheet("color:#ffffff; font-size:26px; font-weight:800;")
        layout.addWidget(value_label)


class ChannelCard(QFrame):
    toggled = pyqtSignal(str, bool)

    def __init__(self, channel: ChannelRecord):
        super().__init__()
        self.setObjectName("channel_card")
        self.channel = channel
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(12)
        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(4)
        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        self.lbl_title = QLabel(channel.title)
        self.lbl_title.setStyleSheet("font-size:18px; font-weight:800; color:#18202a;")
        title_row.addWidget(self.lbl_title)

        if channel.picked_by_ai:
            badge = QLabel("Picked by AI")
            badge.setStyleSheet(
                "QLabel { background:#eef8ff; color:#2261d4; border:1px solid #b8cff8; border-radius:8px; padding:5px 9px; font-weight:700; font-size:12px; }"
            )
            title_row.addWidget(badge)

        title_row.addStretch()
        title_wrap.addLayout(title_row)

        meta_text = (
            f"Subscribers: {_fmt_int(channel.subscribers)}     "
            f"Avg. Views Per Video: {_fmt_int(channel.avg_views_per_video)}     "
            f"Days Since Start: {_fmt_int(channel.days_since_start)}     "
            f"Number of Uploads: {_fmt_int(channel.upload_count)}     "
            f"Monetized: {'Yes' if channel.monetized else 'No'}"
        )
        lbl_meta = QLabel(meta_text)
        lbl_meta.setStyleSheet("color:#6d7886; font-size:12px;")
        lbl_meta.setWordWrap(True)
        title_wrap.addWidget(lbl_meta)

        header.addLayout(title_wrap, 1)

        self.btn_expand = QToolButton()
        self.btn_expand.setText("Collapse" if channel.revealed else "Expand")
        self.btn_expand.setCheckable(True)
        self.btn_expand.setChecked(channel.revealed)
        self.btn_expand.clicked.connect(self._toggle_expanded)
        header.addWidget(self.btn_expand, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        self.detail_panel = QWidget()
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(14)

        metrics_grid = QGridLayout()
        metrics_grid.setHorizontalSpacing(14)
        metrics_grid.setVerticalSpacing(12)
        metric_tiles = [
            ("Categories", channel.category),
            ("Total Views", _fmt_int(channel.total_views)),
            ("Avg. Monthly Views", _fmt_int(channel.avg_monthly_views)),
            ("Total Revenue Generated", f"$ {_fmt_int(channel.total_revenue_generated)}"),
            ("Avg. Monthly Revenue", f"$ {_fmt_int(channel.avg_monthly_revenue)}"),
            ("RPM", f"{channel.rpm:.1f}"),
            ("Last Upload", f"{channel.last_upload_days_ago} Days Ago"),
            ("Avg. Monthly Upload Freq", _fmt_int(channel.avg_monthly_upload_freq)),
            ("Avg. Video Length", f"{channel.avg_video_length_minutes:.2f} min"),
            ("Has Youtube Shorts", "Yes" if channel.has_shorts else "No"),
        ]
        for idx, (title, value) in enumerate(metric_tiles):
            metrics_grid.addWidget(MetricTile(title, value), idx // 3, idx % 3)
        detail_layout.addLayout(metrics_grid)

        sub = QVBoxLayout()
        sub.setSpacing(6)
        lbl_popular = QLabel("Most Popular Videos")
        lbl_popular.setStyleSheet("font-size:15px; font-weight:700; color:#18202a;")
        sub.addWidget(lbl_popular)
        for rank, title in enumerate(channel.most_popular_videos, start=1):
            row = QLabel(f"{rank}. {title}")
            row.setStyleSheet("color:#3b4552;")
            sub.addWidget(row)
        detail_layout.addLayout(sub)

        root.addWidget(self.detail_panel)
        self.detail_panel.setVisible(channel.revealed)

    def _toggle_expanded(self):
        expanded = self.btn_expand.isChecked()
        self.btn_expand.setText("Collapse" if expanded else "Expand")
        self.detail_panel.setVisible(expanded)
        self.channel.revealed = expanded
        self.toggled.emit(self.channel.title, expanded)
