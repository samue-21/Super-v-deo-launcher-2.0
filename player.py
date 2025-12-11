import sys
import os
import json
import uuid
import hashlib
import hmac
import time
import platform
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QPushButton, QVBoxLayout, QFileDialog,
    QMessageBox, QHBoxLayout, QMenuBar, QApplication, QSplashScreen,
    QSlider, QLabel, QLineEdit, QDialog, QDialogButtonBox
)
from PyQt6.QtGui import (
    QIcon, QPixmap, QPainter, QColor, QPolygon, QAction, QKeySequence
)
from PyQt6.QtCore import (
    QUrl, Qt, QTimer, QPoint
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

# ============================================================
# 🔐 SISTEMA DE LICENÇA LOCAL
# ============================================================

SECRET = b"TROQUE-Essa-SECRET-ANTES-DE-DISTRIBUIR"  # ❗ ALTERE ESTA SECRET ANTES DE PUBLICAR!
LICENSE_DIR = Path.home() / ".superplayer"
LICENSE_FILE = LICENSE_DIR / "license.json"


def machine_id():
    """Gera uma impressão única da máquina baseada no MAC + hostname."""
    try:
        mac = uuid.getnode()
    except:
        mac = 0

    node = platform.node() or ""
    raw = f"{mac}-{node}".encode()

    return hashlib.sha256(raw).hexdigest()


def make_hmac(payload_bytes):
    return hmac.new(SECRET, payload_bytes, hashlib.sha256).hexdigest()


def parse_license_key(key: str):
    """Verifica formato, assinatura e decodifica a licença."""
    try:
        if not key.startswith("PLR-"):
            return None

        _, payload_hex, sig = key.split("-", 2)
        payload = bytes.fromhex(payload_hex)
        expected_sig = make_hmac(payload)

        if not hmac.compare_digest(expected_sig, sig):
            return None

        user, expiry, machine = payload.decode().split("|")
        return {"user": user, "expiry": int(expiry), "machine": machine}

    except:
        return None


def save_license_locally(key, parsed):
    LICENSE_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "key": key,
        "user": parsed["user"],
        "expiry": parsed["expiry"],
        "machine": parsed["machine"],
        "saved_at": int(time.time()),
    }
    with open(LICENSE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_local_license():
    if not LICENSE_FILE.exists():
        return None
    try:
        with open(LICENSE_FILE, "r") as f:
            return json.load(f)
    except:
        return None


def validate_local_license():
    """Verifica licença salva localmente: assinatura, expiração e máquina."""
    rec = load_local_license()
    if not rec:
        return False, "no_license"

    parsed = parse_license_key(rec["key"])
    if not parsed:
        return False, "invalid_key"

    if parsed["expiry"] < time.time():
        return False, "expired"

    if parsed["machine"]:
        if parsed["machine"] != machine_id():
            return False, "wrong_machine"

    return True, parsed


# ============================================================
# COMPONENTES DO PLAYER
# ============================================================

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


def show_splash(app):
    splash_pix = generate_icon_pixmap(256)
    splash = QSplashScreen(splash_pix)
    splash.show()
    QTimer.singleShot(700, splash.close)
    return splash


# ============================================================
# JANELA EXTERNA FULLSCREEN
# ============================================================
class VideoWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        self.video_widget = QVideoWidget(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.video_widget)

    def show_on_screen(self, screen):
        geo = screen.geometry()
        self.setGeometry(geo)
        self.showFullScreen()


# ============================================================
# JANELA PRINCIPAL
# ============================================================
class SuperPlayer(QWidget):
    def __init__(self):
        super().__init__()

        ok, info = validate_local_license()
        self.is_licensed = ok
        self.license_info = info if ok else None

        self.setWindowTitle("Super Player")
        self.setGeometry(200, 200, 760, 560)

        pix = generate_icon_pixmap(256)
        self.setWindowIcon(QIcon(pix))

        # PLAYER
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.video_widget = QVideoWidget()
        self.player.setVideoOutput(self.video_widget)

        # JANELA EXTERNA
        self.external_window = VideoWindow()

        # MENU
        self.menu_bar = QMenuBar(self)
        file_menu = self.menu_bar.addMenu("Arquivo")

        act_open = QAction("Abrir vídeo...", self)
        act_open.triggered.connect(self.open_file)
        file_menu.addAction(act_open)

        act_license = QAction("Ativar licença...", self)
        act_license.triggered.connect(self.activate_license)
        file_menu.addAction(act_license)

        act_machine = QAction("Mostrar Machine ID", self)
        act_machine.triggered.connect(self.show_machine)
        file_menu.addAction(act_machine)

        act_close = QAction("Fechar Player", self)
        act_close.triggered.connect(self.close)
        file_menu.addAction(act_close)

        # LAYOUT PRINCIPAL
        layout = QVBoxLayout()
        layout.setMenuBar(self.menu_bar)
        layout.addWidget(self.video_widget)

        # SLIDER
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.set_position)
        layout.addWidget(self.slider)

        self.player.positionChanged.connect(self.update_position)
        self.player.durationChanged.connect(self.update_duration)

        # CONTROLES
        controls = QHBoxLayout()

        self.btn_play = QPushButton("⏯️ Reprodução")
        self.btn_play.clicked.connect(self.toggle_play)
        controls.addWidget(self.btn_play)

        self.btn_stop = QPushButton("⏹️ Parar")
        self.btn_stop.clicked.connect(self.stop_video)
        controls.addWidget(self.btn_stop)

        self.btn_exit = QPushButton("⛔ Sair Tela Cheia")
        self.btn_exit.clicked.connect(self.exit_fullscreen)
        controls.addWidget(self.btn_exit)

        layout.addLayout(controls)

        self.control_widgets = [self.btn_play, self.btn_stop, self.btn_exit]

        self.create_monitor_shortcuts()
        self.add_shortcuts()

        self.setLayout(layout)

        self.update_license_label()

    # ============================================================
    #AÇÃO: JANELA PROFISSIONAL DE ATIVAÇÃO DE LICENÇA
    # ============================================================
    def activate_license(self):

        dlg = QDialog(self)
        dlg.setWindowTitle("Ativar Licença")
        dlg.setFixedSize(480, 260)

        layout = QVBoxLayout(dlg)

        # TÍTULO
        title = QLabel("<b>Cole sua chave de licença abaixo:</b>")
        layout.addWidget(title)

        # MACHINE ID + BOTÃO COPIAR
        mid_layout = QHBoxLayout()

        self.mid_label = QLabel(machine_id())
        self.mid_label.setStyleSheet("color:#00aaff; font-weight:bold;")
        self.mid_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        mid_layout.addWidget(QLabel("Machine ID:"))
        mid_layout.addWidget(self.mid_label)

        # botão de copiar
        copy_btn = QPushButton("Copiar")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.mid_label.text()))
        mid_layout.addWidget(copy_btn)

        layout.addLayout(mid_layout)

        # instrução
        layout.addWidget(QLabel("<small>Envie este Machine ID para o suporte gerar sua licença.</small>"))

        # INPUT DA LICENÇA
        self.input_key = QLineEdit()
        self.input_key.setPlaceholderText("Cole sua chave de licença aqui...")
        layout.addWidget(self.input_key)

        # BOTÕES OK/CANCEL
        buttons = (
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btn_box = QDialogButtonBox(buttons)
        layout.addWidget(btn_box)

        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)

        # MOSTRAR JANELA
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        # PEGAR TEXTO
        key = self.input_key.text().strip()
        if not key:
            return

        # VALIDAÇÃO DA LICENÇA
        parsed = parse_license_key(key)
        if not parsed:
            QMessageBox.critical(self, "Erro", "Licença inválida.")
            return

        if parsed["expiry"] < time.time():
            QMessageBox.warning(self, "Erro", "Licença expirada.")
            return

        if parsed["machine"] and parsed["machine"] != machine_id():
            QMessageBox.critical(self, "Erro", "Licença pertence a outra máquina.")
            return

        # SALVAR E ATIVAR
        save_license_locally(key, parsed)
        self.is_licensed = True
        self.license_info = parsed
        self.update_license_label()

        QMessageBox.information(self, "Sucesso", "Licença ativada com sucesso!")



    # EXIBIR MACHINE ID
    def show_machine(self):
        QMessageBox.information(self, "Machine ID", machine_id())

    # ============================================================
    # PLAYER FUNCTIONS
    # ============================================================ 
    def update_license_label(self):
        if self.is_licensed:
            user = self.license_info["user"]
            self.setWindowTitle(f"Super Player — PREMIUM ({user})")
        else:
            self.setWindowTitle("Super Player — FREE")

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Selecione um vídeo", "",
            "Vídeos (*.mp4 *.avi *.mkv *.mov *.mpg *.mpeg *.wmv)"
        )
        if file_path:
            self.player.setSource(QUrl.fromLocalFile(file_path))
            self.player.play()
            self.btn_play.setText("⏸️ Pausar")

    def toggle_play(self):
        if self.player.isPlaying():
            self.player.pause()
            self.btn_play.setText("▶️ Reproduzir")
        else:
            self.player.play()
            self.btn_play.setText("⏸️ Pausar")

    def stop_video(self):
        self.player.stop()
        self.btn_play.setText("▶️ Reproduzir")

    def restore_to_main(self):
        self.player.setVideoOutput(self.video_widget)
        self.external_window.hide()

    def exit_fullscreen(self):
        if self.external_window.isFullScreen():
            self.restore_to_main()
            return

        if self.isFullScreen():
            self.setWindowFlags(Qt.WindowType.Window)
            self.showNormal()
        else:
            self.close()

    def update_position(self, pos):
        self.slider.setValue(pos)

    def update_duration(self, dur):
        self.slider.setRange(0, dur)

    def set_position(self, pos):
        self.player.setPosition(pos)

    def jump(self, seconds):
        newpos = self.player.position() + seconds * 1000
        newpos = max(0, min(newpos, self.player.duration()))
        self.player.setPosition(newpos)

    def add_shortcuts(self):
        sc1 = QAction(self)
        sc1.setShortcut(QKeySequence("Space"))
        sc1.triggered.connect(self.toggle_play)
        self.addAction(sc1)

        sc2 = QAction(self)
        sc2.setShortcut(QKeySequence("A"))
        sc2.triggered.connect(lambda: self.jump(-10))
        self.addAction(sc2)

        sc3 = QAction(self)
        sc3.setShortcut(QKeySequence("D"))
        sc3.triggered.connect(lambda: self.jump(10))
        self.addAction(sc3)

        sc4 = QAction(self)
        sc4.setShortcut(QKeySequence("Escape"))
        sc4.triggered.connect(self.exit_fullscreen)
        self.addAction(sc4)

    def create_monitor_shortcuts(self):
        screens = QApplication.screens()
        for i, screen in enumerate(screens, start=1):
            act = QAction(self)
            act.setShortcut(QKeySequence(f"Ctrl+F{i}"))
            act.triggered.connect(lambda _, m=i: self.play_fullscreen_on_monitor(m))
            self.addAction(act)

    def play_fullscreen_on_monitor(self, monitor_index):
        screens = QApplication.screens()
        if monitor_index - 1 >= len(screens):
            QMessageBox.warning(self, "Erro", "Monitor não encontrado.")
            return

        screen = screens[monitor_index - 1]
        self.player.setVideoOutput(self.external_window.video_widget)
        self.external_window.show_on_screen(screen)


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    show_splash(app)
    window = SuperPlayer()
    window.show()
    sys.exit(app.exec())
