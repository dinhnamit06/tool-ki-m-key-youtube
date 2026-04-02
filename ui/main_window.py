from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QStackedWidget, QSizePolicy
)
from PyQt6.QtCore import Qt

from ui.keywords_tab import KeywordsTab
from ui.trends_tab import TrendsTab
from utils.constants import MAIN_STYLE

class TubeVibeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TubeVibe - YouTube Research Pro")
        self.resize(1280, 800)
        self.setup_ui()
        self.setStyleSheet(MAIN_STYLE)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # MAIN AREA
        right_area = QWidget()
        r_layout = QVBoxLayout(right_area)
        r_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.setSpacing(0)
        
        # Navbar
        navbar = QFrame(); navbar.setObjectName("navbar"); navbar.setFixedHeight(60)
        n_layout = QHBoxLayout(navbar); n_layout.setContentsMargins(20, 0, 20, 0)
        
        self.nav_labels = []
        tabs_names = ["Welcome", "Keywords", "Trends", "Videos", "Channels", "Video to Text", "Comments"]
        for i, name in enumerate(tabs_names):
            lbl = QLabel(name)
            lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            lbl.setObjectName("active_tab" if name == "Keywords" else "inactive_tab")
            lbl.mousePressEvent = lambda e, idx=i: self.switch_tab(idx)
            self.nav_labels.append(lbl)
            n_layout.addWidget(lbl)
        n_layout.addStretch()
        
        self.main_stack = QStackedWidget()
        self.tab_welcome = QWidget()
        self.tab_keywords = KeywordsTab(self)
        self.tab_trends = TrendsTab(self)
        
        # Connect signal: Keywords -> Trends data transfer
        self.tab_keywords.send_to_trends_signal.connect(self.handle_send_to_trends)
        
        self.main_stack.addWidget(self.tab_welcome)
        self.main_stack.addWidget(self.tab_keywords)
        self.main_stack.addWidget(self.tab_trends)
        # Placeholders for other tabs
        for _ in range(4): self.main_stack.addWidget(QWidget())
        
        self.main_stack.setCurrentIndex(1)
        
        r_layout.addWidget(navbar)
        r_layout.addWidget(self.main_stack, stretch=1)
        main_layout.addWidget(right_area, stretch=1)

    def switch_tab(self, index):
        self.main_stack.setCurrentIndex(index)
        for i, lbl in enumerate(self.nav_labels):
            if i == index:
                lbl.setObjectName("active_tab")
                lbl.setStyleSheet("color: #ffffff; background-color: #2a2a2a; padding: 20px 15px; border-bottom: 3px solid #e50914; font-weight: bold; font-size: 15px;")
            else:
                lbl.setObjectName("inactive_tab")
                lbl.setStyleSheet("color: #aaaaaa; padding: 20px 15px; font-size: 15px; border-bottom: none; background-color: transparent;")

    def handle_send_to_trends(self, keywords):
        self.tab_trends.trends_input.setText("\n".join(keywords))
        self.switch_tab(2)
        self.statusBar().showMessage(f"Sent {len(keywords)} keywords to Trends tool.", 4000)
