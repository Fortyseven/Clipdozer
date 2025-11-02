from PySide6.QtWidgets import QApplication, QMainWindow, QMenuBar, QMenu
from PySide6.QtGui import QAction
import sys

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Clipdozer")
        self.setGeometry(100, 100, 800, 600)
        self._createMenuBar()

    def _createMenuBar(self):
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("File")
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # About menu
        about_menu = menu_bar.addMenu("About")
        about_action = QAction("About Clipdozer", self)
        about_action.triggered.connect(self._showAboutDialog)
        about_menu.addAction(about_action)

    def _showAboutDialog(self):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.about(self, "About Clipdozer", "Clipdozer\nLightweight video editor for social media clips.")


def run():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
