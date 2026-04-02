import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import TubeVibeApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = TubeVibeApp()
    window.show()
    
    sys.exit(app.exec())
