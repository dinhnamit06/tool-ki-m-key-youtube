import sys
import traceback
from pathlib import Path

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

APP_ROOT = Path(__file__).resolve().parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from ui.main_window import YTBRPMApp


def _show_unhandled_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    traceback_text = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    try:
        message_box = QMessageBox()
        message_box.setIcon(QMessageBox.Icon.Critical)
        message_box.setWindowTitle("Application Error")
        message_box.setText("YTB RPM caught an unexpected error and prevented a hard crash.")
        message_box.setInformativeText(str(exc_value) or exc_type.__name__)
        message_box.setDetailedText(traceback_text)
        message_box.exec()
    except Exception:
        pass

    print(traceback_text, file=sys.stderr)


sys.excepthook = _show_unhandled_exception


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = YTBRPMApp()
    window.show()

    sys.exit(app.exec())
