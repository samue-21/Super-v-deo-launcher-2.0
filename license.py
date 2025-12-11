# superplayer_with_license.py
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
    QSlider, QInputDialog, QLabel
)
from PyQt6.QtGui import (
    QIcon, QPixmap, QPainter, QColor, QPolygon, QAction, QKeySequence
)
from PyQt6.QtCore import (
    QUrl, Qt, QTimer, QPoint
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

# ----------------------------
# CONFIGURAÇÃO DE LICENÇA (ALTERE AQUI)
# ----------------------------
# Atenção: esta SECRET fica dentro do app — para produção com segurança real, usar servidor.
SECRET = b"mudar_para_uma_chave_super_secreta_123!"  # <--- altere antes de distribuir
LICENSE_DIR = Path.home() / ".superplayer"
LICENSE_FILE = LICENSE_DIR / "license.json"

# ----------------------------
# UTILITÁRIOS DE LICENÇA
# ----------------------------
def machine_id():
    """Gera um machine id baseado em MAC + hostname, retornando hex sha256."""
    try:
        mac = uuid.getnode()  # inteiro
    except Exception:
        mac = 0
    node = platform.node() or ""
    raw = f"{mac}-{node}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def make_hmac(payload_bytes: bytes) -> str:
    sig = hmac.new(SECRET, payload_bytes, hashlib.sha256).hexdigest()
    return sig

def make_license(user: str, days_valid: int = 365, bind_machine: bool = False, target_machine_id: str = None):
    """
    Gera uma chave de licença (apenas usado pelo gerador externo).
    payload: user|expiry_ts|machine_hash_or_empty
    retorna chave no formato: PLR-<payload_hex>-<sig_hex>
    """
    if target_machine_id is None:
        target_machine_id = "" if not bind_machine else machine_id()
    expiry_ts = int(time.time()) + days_valid * 24 * 3600
    payload = f"{user}|{expiry_ts}|{target_machine_id}".encode("utf-8")
    payload_hex = payload.hex()
    sig = make_hmac(payload)
    key = f"PLR-{payload_hex}-{sig}"
    return key

def parse_license_key(key: str):
    """Retorna (user, expiry_ts, machine_id) se o formato estiver ok, senão None."""
    try:
        if not key.startswith("PLR-"):
            return None
        parts = key.split("-", 2)
        if len(parts) != 3:
            return None
        payload_hex, sig = parts[1], parts[2]
        payload = bytes.fromhex(payload_hex)
        expected_sig = make_hmac(payload)
        if not hmac.compare_digest(expected_sig, sig):
            return None
        payload_s = payload.decode("utf-8")
        user, expiry_str, target_machine = payload_s.split("|")
        expiry_ts = int(expiry_str)
        return {"user": user, "expiry": expiry_ts, "machine": target_machine}
    except Exception:
        return None

def save_license_locally(key: str, parsed: dict):
    LICENSE_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "key": key,
        "user": parsed.get("user"),
        "expiry": parsed.get("expiry"),
        "machine": parsed.get("machine"),
        "activated_at": int(time.time())
    }
    with open(LICENSE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_local_license():
    if not LICENSE_FILE.exists():
        return None
    try:
        with open(LICENSE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception:
        return None

def check_local_license_valid():
    rec = load_local_license()
    if not rec:
        return False, "no_license"
    key = rec.get("key")
    parsed = parse_license_key(key)
    if not parsed:
        return False, "invalid_signature"
    # check expiry
    if parsed["expiry"] < int(time.time()):
        return False, "expired"
    # if license is bound to a machine, check
    if parsed["machine"]:
        if parsed["machine"] != machine_id():
            return False, "machine_mismatch"
    return True, parsed

# ----------------------------
# ICON / SPLASH / PLAYER (igual ao anterior)
# ----------------------------
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

class SuperPlayer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Super Player — Minimal Clean (with License)")
        self.setGeometry(200, 200, 760, 560)
        pix = generate_icon_pixmap(256)
        self.app_icon = QIcon(pix)
        self.setWindowIcon(self.app_icon)

        # license state
        self.is_licensed = False
        self.license_info = None
        self.check_license_at_startup()

        # Player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.video_widget = QVideoWidget()
        self.player.setVideoOutput(self.video_widget)
        self.external_window = VideoWindow()

        # Menu
        self.menu_bar = QMenuBar(self)
        file_menu = self.menu_bar.addMenu("Arquivo")
        open_action = QAction("Abrir vídeo...", self)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)

        act_license = QAction("Ativar licença...", self)
        act_license.triggered.connect(self.prompt_activate_license)
        file_menu.addAction(act_license)

        view_machine = QAction("Mostrar machine_id", self)
        view_machine.triggered.connect(self.show_machine_id)
        file_menu.addAction(view_machine)

        close_action = QAction("Fechar Player", self)
        close_action.triggered.connect(self.close)
        file_menu.addAction(close_action)

        # Layout
        layout = QVBoxLayout()
        layout.setMenuBar(self.menu_bar)
        layout.addWidget(self.video_widget)

        # status / license label
        self.lic_label = QLabel()
        self.update_license_label()
        layout.addWidget(self.lic_label)

        # slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.set_position)
        layout.addWidget(self.slider)
        self.player.positionChanged.connect(self.update_position)
        self.player.durationChanged.connect(self.update_duration)

        # controls
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
        self.setLayout(layout)

    # -----------------------------------
    # LICENÇA
    # -----------------------------------
    def check_license_at_startup(self):
        ok, info = check_local_license_valid()
        if ok:
            self.is_licensed = True
            self.license_info = info
        else:
            self.is_licensed = False
            self.license_info = None

    def update_license_label(self):
        if self.is_licensed and self.license_info:
            expiry_ts = self.license_info.get("expiry")
            expire_s = time.strftime("%Y-%m-%d", time.localtime(expiry_ts))
            user = self.license_info.get("user")
            self.lic_text = f"Licença ativa → {user} (expira: {expire_s})"
        else:
            self.lic_text = "Modo gratuito — licença não ativada"
        if hasattr(self, "lic_label"):
            self.lic_label.setText(self.lic_text)

    def show_machine_id(self):
        mid = machine_id()
        QMessageBox.information(self, "Machine ID", f"{mid}\n\nUse este value para gerar uma licença travada a esta máquina.")

    def prompt_activate_license(self):
        text, ok = QInputDialog.getText(self, "Ativar licença", "Cole sua chave de licença:")
        if not ok or not text:
            return
        parsed = parse_license_key(text.strip())
        if not parsed:
            QMessageBox.critical(self, "Licença inválida", "Chave inválida ou assinatura incorreta.")
            return
        # expiry check
        if parsed["expiry"] < int(time.time()):
            QMessageBox.critical(self, "Licença expirada", "Esta licença está expirada.")
            return
        # machine-binding check
        if parsed["machine"]:
            if parsed["machine"] != machine_id():
                QMessageBox.critical(self, "Máquina diferente", "Esta licença foi emitida para outra máquina.")
                return
        # ok → salvar localmente
        save_license_locally(text.strip(), parsed)
        self.is_licensed = True
        self.license_info = parsed
        self.update_license_label()
        QMessageBox.information(self, "Ativação", "Licença ativada com sucesso!")

    # -----------------------------------
    # PLAYER
    # -----------------------------------
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
            self.menu_bar.setVisible(True)
            for w in self.control_widgets:
                w.setVisible(True)
        else:
            self.close()

    # slider
    def update_position(self, position):
        self.slider.setValue(position)
    def update_duration(self, duration):
        self.slider.setRange(0, duration)
    def set_position(self, position):
        self.player.setPosition(position)

    # jump
    def jump(self, seconds):
        new_pos = self.player.position() + (seconds * 1000)
        new_pos = max(0, min(new_pos, self.player.duration()))
        self.player.setPosition(new_pos)

    # shortcuts
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

        sc_forward = QAction(self)
        sc_forward.setShortcut(QKeySequence("D"))
        sc_forward.triggered.connect(lambda: self.jump(10))
        self.addAction(sc_forward)

        sc_back = QAction(self)
        sc_back.setShortcut(QKeySequence("A"))
        sc_back.triggered.connect(lambda: self.jump(-10))
        self.addAction(sc_back)

    def create_monitor_shortcuts(self):
        screens = QApplication.screens()
        for i, screen in enumerate(screens, start=1):
            sc = QAction(self)
            sc.setShortcut(QKeySequence(f"Ctrl+F{i}"))
            sc.triggered.connect(lambda _, m=i: self.play_fullscreen_on_monitor(m))
            self.addAction(sc)

    def play_fullscreen_on_monitor(self, monitor_index):
        screens = QApplication.screens()
        if monitor_index - 1 >= len(screens):
            QMessageBox.warning(self, "Erro", f"O monitor {monitor_index} não existe.")
            return
        screen = screens[monitor_index - 1]
        self.player.setVideoOutput(self.external_window.video_widget)
        self.external_window.show_on_screen(screen)

# ----------------------------
# RUN
# ----------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    show_splash(app)
    window = SuperPlayer()
    window.show()
    sys.exit(app.exec())
