from __future__ import annotations

from typing import Iterable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QToolButton, QVBoxLayout, QLabel


class SidebarNav(QFrame):
    page_requested = pyqtSignal(str)

    def __init__(self, items: Iterable[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(176)
        self._buttons: dict[str, QToolButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(8)

        logo = QLabel("nex\nLev")
        logo.setObjectName("sidebar_logo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)

        for page_key, label in items:
            btn = QToolButton()
            btn.setObjectName("sidebar_btn")
            btn.setText(label)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            btn.clicked.connect(lambda _checked=False, key=page_key: self.page_requested.emit(key))
            self._buttons[page_key] = btn
            layout.addWidget(btn)

        layout.addStretch()

    def set_active_page(self, page_key: str):
        for key, button in self._buttons.items():
            button.setProperty("active", key == page_key)
            button.style().unpolish(button)
            button.style().polish(button)
