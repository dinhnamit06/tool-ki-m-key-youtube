from PyQt6.QtWidgets import QMainWindow

from ui.rpm_finder_page import RPMFinderPage
from utils.styles import MAIN_STYLE


class YTBRPMApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YTB RPM - RPM Finder")
        self.resize(1560, 940)
        self.statusBar().showMessage("RPM Finder shell ready.")
        self._setup_ui()
        self.setStyleSheet(MAIN_STYLE)

    def _setup_ui(self):
        self.page = RPMFinderPage(self)
        self.setCentralWidget(self.page)
