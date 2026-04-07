from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaceholderPage(QWidget):
    def __init__(self, title: str, hint: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(12)

        lbl_title = QLabel(title)
        lbl_title.setObjectName("app_title")
        layout.addWidget(lbl_title)

        lbl_hint = QLabel(hint)
        lbl_hint.setWordWrap(True)
        lbl_hint.setObjectName("muted_label")
        layout.addWidget(lbl_hint)
        layout.addStretch()
