from PyQt6.QtWidgets import QApplication
import sys
from player_window import SuperPlayer, show_splash

if __name__ == "__main__":
    app = QApplication(sys.argv)
    show_splash(app)
    win = SuperPlayer()
    win.show()
    sys.exit(app.exec())
