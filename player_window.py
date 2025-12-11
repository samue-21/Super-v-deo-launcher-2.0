import sys
import os
from PyQt6.QtWidgets import (
    QWidget, QPushButton, QVBoxLayout, QFileDialog,
    QMessageBox, QHBoxLayout, QMenuBar, QApplication, QSplashScreen
)
from PyQt6.QtGui import (
    QIcon, QPixmap, QPainter, QColor, QPolygon, QAction, QKeySequence
)
from PyQt6.QtCore import (
    QUrl, Qt, QTimer, QPoint
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

VIDEO_EXT = [".mp4", ".avi", ".mov", ".mkv", ".wmv", ".mpg", ".mpeg"]


# ---------------------------------------------------------------------
# ÍCONE GERADO EM RUNTIME
# ---------------------------------------------------------------------
def generate_icon_pixmap(size=256):
    pm = QPixmap(size, size)
    pm.fill(QColor("#f7f7f8"))

    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    painter.setBrush(QColor("#2f2f2f"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, size, size, 24, 24)

    painter.setBrush(QColor("#ffffff"))
    margin = int(size * 0.22)

    points = [
        (margin, margin),
        (size - margin, size // 2),
        (margin, size - margin)
    ]

    polygon = QPolygon([QPoint(p[0], p[1]) for p in points])
    painter.drawPolygon(polygon)

    painter.end()
    return pm


# ---------------------------------------------------------------------
# SPLASH SCREEN
# ---------------------------------------------------------------------
def show_splash(app):
    splash_pix = generate_icon_pixmap(256)
    splash = QSplashScreen(splash_pix)
    splash.show()
    QTimer.singleShot(900, splash.close)
    return splash


# ---------------------------------------------------------------------
# JANELA PRINCIPAL
# ---------------------------------------------------------------------
class SuperPlayer(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Super Player — Minimal Clean")
        self.setGeometry(200, 200, 760, 560)

        pix = generate_icon_pixmap(256)
        self.app_icon = QIcon(pix)
        self.setWindowIcon(self.app_icon)

        # Player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        self.video_widget = QVideoWidget()
        self.player.setVideoOutput(self.video_widget)

        # Barra de menu
        self.menu_bar = QMenuBar(self)
        file_menu = self.menu_bar.addMenu("Arquivo")

        open_action = QAction("Abrir vídeo...", self)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)

        close_action = QAction("Fechar Player", self)
        close_action.triggered.connect(self.close)
        file_menu.addAction(close_action)

        # Layout principal
        layout = QVBoxLayout()
        layout.setMenuBar(self.menu_bar)
        layout.addWidget(self.video_widget)
        self.setLayout(layout)

        # -------- CONTROLES --------
        controls_layout = QHBoxLayout()

        self.btn_play = QPushButton("⏯️ Reprodução")
        self.btn_play.clicked.connect(self.toggle_play)
        controls_layout.addWidget(self.btn_play)

        self.btn_stop = QPushButton("⏹️ Parar")
        self.btn_stop.clicked.connect(self.stop_video)
        controls_layout.addWidget(self.btn_stop)

        self.btn_exit_fs = QPushButton("⛔ Sair Tela Cheia")
        self.btn_exit_fs.clicked.connect(self.exit_fullscreen)
        controls_layout.addWidget(self.btn_exit_fs)

        layout.addLayout(controls_layout)

        self.control_widgets = [self.btn_play, self.btn_stop, self.btn_exit_fs]

        self.create_monitor_shortcuts()
        self.add_shortcuts()

    # ------------------------------------------------------------
    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecione um vídeo",
            "",
            "Vídeos (*.mp4 *.avi *.mkv *.mov *.mpg *.mpeg *.wmv)"
        )

        if file_path:
            self.player.setSource(QUrl.fromLocalFile(file_path))
            self.player.play()
            self.btn_play.setText("⏸️ Pausar")

    # ------------------------------------------------------------
    def toggle_play(self):
        if self.player.isPlaying():
            self.player.pause()
            self.btn_play.setText("▶️ Reproduzir")
        else:
            self.player.play()
            self.btn_play.setText("⏸️ Pausar")

    # ------------------------------------------------------------
    def stop_video(self):
        self.player.stop()
        self.btn_play.setText("▶️ Reproduzir")

    # ------------------------------------------------------------
    def exit_fullscreen(self):
        # Sai do fullscreen ou fecha se já estiver na janela
        if self.isFullScreen():
            self.setWindowFlags(Qt.WindowType.Window)
            self.showNormal()
            self.menu_bar.setVisible(True)
            for w in self.control_widgets:
                w.setVisible(True)
        else:
            self.close()

    # ------------------------------------------------------------
    def add_shortcuts(self):

        sc_playpause = QAction(self)
        sc_playpause.setShortcut(QKeySequence("Space"))
        sc_playpause.triggered.connect(self.toggle_play)
        self.addAction(sc_playpause)

        sc_stop = QAction(self)
        sc_stop.setShortcut(QKeySequence("S"))
        sc_stop.triggered.connect(self.stop_video)
        self.addAction(sc_stop)

        sc_exitfs = QAction(self)
        sc_exitfs.setShortcut(QKeySequence("Escape"))
        sc_exitfs.triggered.connect(self.exit_fullscreen)
        self.addAction(sc_exitfs)

    # ------------------------------------------------------------
    def create_monitor_shortcuts(self):
        screens = QApplication.screens()

        for i, screen in enumerate(screens, start=1):
            sc = QAction(self)
            sc.setShortcut(QKeySequence(f"Ctrl+F{i}"))
            sc.triggered.connect(lambda _, m=i: self.play_fullscreen_on_monitor(m))
            self.addAction(sc)

    # ------------------------------------------------------------
    def play_fullscreen_on_monitor(self, monitor_index):
        screens = QApplication.screens()

        if monitor_index - 1 >= len(screens):
            QMessageBox.warning(self, "Erro", f"O monitor {monitor_index} não existe.")
            return

        screen = screens[monitor_index - 1]
        geo = screen.geometry()

        # Oculta menu e controles
        self.menu_bar.setVisible(False)
        for w in self.control_widgets:
            w.setVisible(False)

        # Remove bordas 100%
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        # Move para o monitor e coloca fullscreen
        self.setGeometry(geo)
        self.showFullScreen()
