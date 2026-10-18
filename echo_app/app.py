import logging
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from echo_app import __version__, config
from echo_app.ui import theme
from echo_app.ui.main_window import MainWindow


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setOrganizationName("Echo")
    app.setApplicationName("Echo")
    app.setApplicationDisplayName("Echo")
    app.setApplicationVersion(__version__)
    app.setDesktopFileName("echo-team-report")
    app.setWindowIcon(QIcon(str(config.ASSETS_DIR / "icon.svg")))
    app.setStyle("Fusion")
    app.setPalette(theme.light_palette())
    app.setStyleSheet(theme.STYLESHEET)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
