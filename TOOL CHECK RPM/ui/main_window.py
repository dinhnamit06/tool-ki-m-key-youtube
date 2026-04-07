from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from ui.channels_page import ChannelsPage
from ui.rpm_finder_page import RPMFinderPage
from ui.sidebar_nav import SidebarNav
from utils.styles import MAIN_STYLE


class PlaceholderPage(QWidget):
    def __init__(self, title: str, hint: str, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(0)

        card = QFrame()
        card.setObjectName("content_card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(10)

        lbl_title = QLabel(title)
        lbl_title.setObjectName("app_title")
        layout.addWidget(lbl_title)

        lbl_hint = QLabel(hint)
        lbl_hint.setObjectName("muted_label")
        lbl_hint.setWordWrap(True)
        layout.addWidget(lbl_hint)
        layout.addStretch()

        root.addWidget(card)


class YTBRPMApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YTB RPM - RPM Finder")
        self.resize(1560, 940)
        self._setup_ui()
        self.setStyleSheet(MAIN_STYLE)
        self.statusBar().showMessage("RPM Finder shell ready.")

    def _setup_ui(self):
        shell = QWidget()
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        nav_items = [
            ("rpm_finder", "AI Niche Finder"),
            ("dashboard", "Dashboard"),
            ("keywords", "Keywords"),
            ("custom_keywords", "Custom Keywords"),
            ("channels", "Channels"),
            ("saved", "Saved"),
            ("rpm_predictor", "RPM Predictor"),
            ("nexlev_ai", "NexLev AI"),
        ]
        self.sidebar = SidebarNav(nav_items, self)
        self.sidebar.page_requested.connect(self._show_page)
        shell_layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        shell_layout.addWidget(self.stack, 1)

        self.pages: dict[str, QWidget] = {
            "rpm_finder": RPMFinderPage(self),
            "channels": ChannelsPage(self),
            "dashboard": PlaceholderPage("Dashboard", "This page is reserved for a later RPM step.", self),
            "keywords": PlaceholderPage("Keywords", "This page is reserved for a later RPM step.", self),
            "custom_keywords": PlaceholderPage("Custom Keywords", "This page is reserved for a later RPM step.", self),
            "saved": PlaceholderPage("Saved", "This page is reserved for a later RPM step.", self),
            "rpm_predictor": PlaceholderPage("RPM Predictor", "This page is reserved for RPM-08.", self),
            "nexlev_ai": PlaceholderPage("NexLev AI", "This page is reserved for a later RPM step.", self),
        }
        for page in self.pages.values():
            self.stack.addWidget(page)

        self.setCentralWidget(shell)
        self._show_page("rpm_finder")

    def _show_page(self, page_key: str):
        page = self.pages.get(page_key)
        if page is None:
            return
        self.stack.setCurrentWidget(page)
        self.sidebar.set_active_page(page_key)
        label = {
            "rpm_finder": "RPM Finder overview ready.",
            "channels": "Channels page ready.",
            "rpm_predictor": "RPM Predictor page placeholder ready.",
        }.get(page_key, f"{page_key.replace('_', ' ').title()} page ready.")
        self.statusBar().showMessage(label, 2500)
