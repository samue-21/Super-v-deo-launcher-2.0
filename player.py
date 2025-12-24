# player.py (versão com Dock recolhível/desacoplável) + botão "Sair Tela Cheia" no canto superior direito (modo janela)
import sys
import os
import json
import uuid
import hashlib
import hmac
import time
import platform
import re
import subprocess
import tempfile

from pathlib import Path
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import Qt



from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QPushButton, QVBoxLayout, QFileDialog,
    QMessageBox, QHBoxLayout, QMenuBar, QApplication, QSplashScreen,
    QSlider, QLabel, QLineEdit, QDialog, QDialogButtonBox,
    QDockWidget, QListWidget, QAbstractItemView, QListWidgetItem
)
from PyQt6.QtGui import (
    QIcon,
    QPixmap,
    QPainter,
    QColor,
    QPolygon,
    QKeySequence,
    QAction   
)
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QMenu
from PyQt6.QtGui import QAction
from PyQt6.QtCore import QEvent



from PyQt6.QtWidgets import QInputDialog 
from PyQt6.QtCore import (
    QUrl, Qt, QTimer, QPoint
)


from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink

from PyQt6.QtMultimediaWidgets import QVideoWidget

# --- (licensing utilities same as before) ---
SECRET = b"TROQUE-Essa-SECRET-ANTES-DE-DISTRIBUIR"
LICENSE_DIR = Path.home() / ".superplayer"
LICENSE_FILE = LICENSE_DIR / "license.json"
PLAYLIST_FILE = LICENSE_DIR / "playlist.json"
PLAYLIST_FILE = Path.home() / ".superplayer" / "playlist.json"
LAST_PLAYLIST_FILE = LICENSE_DIR / "last_playlist.json"



def machine_id():
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
    data = {"key": key, "user": parsed["user"], "expiry": parsed["expiry"], "machine": parsed["machine"], "saved_at": int(time.time())}
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
    rec = load_local_license()
    if not rec:
        return False, None
    parsed = parse_license_key(rec["key"])
    if not parsed:
        return False, None
    if parsed["expiry"] < time.time():
        return False, None
    if parsed["machine"] and parsed["machine"] != machine_id():
        return False, None
    return True, parsed

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
    points = [(margin, margin), (size - margin, size // 2), (margin, size - margin)]
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
        
    def __init__(self, player, parent=None, exit_callback=None):
        super().__init__(parent)
        self.player_ref = player
        self.exit_callback = exit_callback


        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()
       
       
        self.video_widget = QVideoWidget(self)
        # menu de contexto (clique direito no vídeo)
        self.video_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.video_widget.customContextMenuRequested.connect(self.show_context_menu)


    def show_context_menu(self, pos):
        menu = QMenu(self)

        loop_action = QAction("🔁 Modo Loop", self)
        loop_action.setCheckable(True)
        loop_action.setChecked(self.parent().loop_enabled)

        loop_action.triggered.connect(self.toggle_loop)

        menu.exec(self.video_widget.mapToGlobal(pos))

    def toggle_loop(self):
        parent = self.parent()
        if parent and hasattr(parent, "loop_enabled"):
            parent.loop_enabled = not parent.loop_enabled
            status = "ATIVADO" if parent.loop_enabled else "DESATIVADO"
            print(f"Modo Loop {status}")



   

       

    def show_on_screen(self, screen):
        self.setGeometry(screen.geometry())
        self.showFullScreen()

    # 🔥 FORÇA FOCO DE TECLADO
        self.activateWindow()
        self.raise_()
        self.setFocus()

        self.reposition_exit_button()


    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reposition_exit_button()

    def reposition_exit_button(self):
        margin = 16
        self.btn_exit.move(
            self.width() - self.btn_exit.width() - margin,
            margin
        )




   



# ============================================================
class SuperPlayer(QMainWindow):
   
    def __init__(self):
        super().__init__()

        
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        self.video_widget = QVideoWidget()
        self.player.setVideoOutput(self.video_widget)

        # ==============================
        # PLAYLIST (UMA ÚNICA VEZ)
        # ==============================
        self.playlist = []
        self.current_index = 0

        self.playlist_widget = QListWidget()
        self.playlist_widget.setSelectionMode(
        QListWidget.SelectionMode.SingleSelection
    )

        # ===============================
        # DOCK DA PLAYLIST (com botão)
        # ===============================
        self.playlist_dock = QDockWidget("Playlist", self)
        self.playlist_dock.setAllowedAreas(
        Qt.DockWidgetArea.LeftDockWidgetArea |
        Qt.DockWidgetArea.RightDockWidgetArea
)

       # container do dock
        dock_container = QWidget()
        dock_layout = QVBoxLayout(dock_container)
        dock_layout.setContentsMargins(6, 6, 6, 6)
        dock_layout.setSpacing(6)

        # lista ocupa o espaço principal
        dock_layout.addWidget(self.playlist_widget, stretch=1)

        # botão limpar (RODAPÉ)
        self.btn_clear_playlist = QPushButton("🧹 Limpar playlist")
        self.btn_clear_playlist.setFixedHeight(34)
        self.btn_clear_playlist.clicked.connect(self.clear_playlist)

        dock_layout.addWidget(self.btn_clear_playlist, stretch=0)

        # 🔥 ESSENCIAL
        self.playlist_dock.setWidget(dock_container)

        # adiciona dock à janela
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.playlist_dock)

        # começa fechado
        self.playlist_dock.hide()



        self.addDockWidget(
        Qt.DockWidgetArea.RightDockWidgetArea,
        self.playlist_dock
    )
         # carrega playlist salva após UI pronta
        QTimer.singleShot(0, self.load_playlist)

        

       
       

 

        # Fim do vídeo ao loop 
        self.video_loop_enabled = False
        self.player.setLoops(QMediaPlayer.Loops.Infinite)




        # Event filter modo loop 
        self.video_widget.installEventFilter(self)






        

                   
        
        ok, info = validate_local_license()
        self.is_licensed = ok
        self.license_info = info if ok else None
        
        ok, info = validate_local_license()
        self.is_licensed = ok
        self.license_info = info if ok else None

        self.setWindowTitle("Super Player")
        self.setGeometry(200,200,1000,640)
        self.setWindowIcon(QIcon(generate_icon_pixmap(256)))

         # core player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.video_widget = QVideoWidget()
        self.player.setVideoOutput(self.video_widget)

               
        # external fullscreen window
        self.external_window = VideoWindow(
    self,  # <<< passa o SuperPlayer
    exit_callback=self.restore_to_main
)
        QApplication.instance().installEventFilter(self)
         # menu
        menu = self.menuBar()
        file_menu = menu.addMenu("Arquivo")
        act_open = QAction("Abrir vídeo...", self); act_open.triggered.connect(self.open_file); file_menu.addAction(act_open)
        act_license = QAction("Ativar licença...", self); act_license.triggered.connect(self.activate_license); file_menu.addAction(act_license)
        act_machine = QAction("Mostrar Machine ID", self); act_machine.triggered.connect(self.show_machine); file_menu.addAction(act_machine)
        act_close = QAction("Fechar Player", self); act_close.triggered.connect(self.close); file_menu.addAction(act_close)
        

        # 1️⃣ cria a barra de menu
        menubar = self.menuBar()

        # 2️⃣ cria o menu Arquivo
        self.menuLoop = menubar.addMenu("Modo Loop")

        # 3️⃣ cria a ação Vídeo Loop
        self.action_video_loop = QAction("🔁 Vídeo Loop", self)
        self.action_video_loop.setCheckable(True)
        self.action_video_loop.triggered.connect(self.toggle_video_loop)
        self.menuLoop.addAction(self.action_video_loop)


        # 4️⃣ adiciona a ação ao menu
        self.menuLoop.addAction(self.action_video_loop)

        self.status = self.statusBar()

        self.loop_indicator = QLabel("🟢 LOOP ATIVO")
        self.loop_indicator.setStyleSheet("color: green; font-weight: bold;")
        self.loop_indicator.hide()  # começa oculto

        self.status.addPermanentWidget(self.loop_indicator)

        #imagen no vídeo (miniatura)

        self.playlist_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.playlist_widget.setIconSize(QSize(120, 68))
        self.playlist_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.playlist_widget.setMovement(QListWidget.Movement.Static)
        self.playlist_widget.setSpacing(10)

        self.video_icon = QIcon("icons/video.png")  # ou qualquer ícone





        
        

              

        
        # central widget
        central = QWidget()
        cl = QVBoxLayout(central)
        cl.setContentsMargins(6,6,6,6)
        cl.addWidget(self.video_widget)

        # slider
        # slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.set_position)

        cl.addWidget(self.slider)

        self.player.positionChanged.connect(self.update_position)
        self.player.durationChanged.connect(self.update_duration)
        self.slider.sliderPressed.connect(self.on_slider_pressed)
        self.slider.sliderReleased.connect(self.on_slider_released)



        # controls: prev, play, stop, next, external fullscreen, toggle dock
        ctrl = QHBoxLayout()
        self.btn_prev = QPushButton("⏮️ Anterior"); self.btn_prev.clicked.connect(self.play_previous); ctrl.addWidget(self.btn_prev)
        self.btn_play = QPushButton("⏯️ Reprodução"); self.btn_play.clicked.connect(self.toggle_play); ctrl.addWidget(self.btn_play)
        self.btn_stop = QPushButton("⏹️ Parar"); self.btn_stop.clicked.connect(self.stop_video); ctrl.addWidget(self.btn_stop)
        self.btn_next = QPushButton("⏭️ Próximo"); self.btn_next.clicked.connect(self.play_next); ctrl.addWidget(self.btn_next)
        self.btn_external = QPushButton("▶ Fullscreen (monitor)")
        self.btn_external.clicked.connect(lambda: self.play_fullscreen_on_monitor(1))
        ctrl.addWidget(self.btn_external)

        self.btn_external.setText("⛔ Fechar Tela Cheia")

        try:
            self.btn_external.clicked.disconnect()
        except TypeError:
            pass  # não havia conexão anterior (seguro)

        self.btn_external.clicked.connect(self.close_external_fullscreen)

       

        # botão playlist
        self.btn_playlist = QPushButton("📑 Playlist")
        self.btn_playlist.setCheckable(True)
        self.btn_playlist.clicked.connect(self.toggle_playlist_dock)
        ctrl.addWidget(self.btn_playlist)


        cl.addLayout(ctrl)
        self.setCentralWidget(central)

        

        # ---------------------------
        # BOTÃO: Sair Tela Cheia (CANTO SUPERIOR DIREITO - modo janela)
        # ---------------------------
    #    self.btn_exit_corner = QPushButton("⛔ Sair Tela Cheia", self)
    #    self.btn_exit_corner.setFixedSize(140, 32)
    #    self.btn_exit_corner.setStyleSheet("""
    #        QPushButton {
    #            background-color: #c62828;
    #            color: white;
    #            font-weight: bold;
    #            border-radius: 6px;
    #        }
    #        QPushButton:hover {
    #            background-color: #ff5252;
    #        }
    #    """)
        # IMPORTANT: button calls a method that only affects the main window fullscreen
        #self.btn_exit_corner.clicked.connect(self.exit_fullscreen)
        # show the button in window mode; if you prefer hidden by default use hide()
        #self.btn_exit_corner.show()

       
        # permitimos fechar, mover e flutuar
        self.playlist_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable | QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable)

       
        self.playlist_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.playlist_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.playlist_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.playlist_widget.setAlternatingRowColors(True)
        self.playlist_widget.itemDoubleClicked.connect(self.on_playlist_double_click)

        # sincroniza ordem quando o dock muda para flutuante ou quando itens movidos
        self.playlist_dock.topLevelChanged.connect(self.on_dock_top_level_changed)
        # model signals for reorder
        try:
            self.playlist_widget.model().rowsMoved.connect(self.sync_playlist_from_widget)
        except Exception:
            self.playlist_widget.model().rowsInserted.connect(self.sync_playlist_from_widget)
            self.playlist_widget.model().rowsRemoved.connect(self.sync_playlist_from_widget)

        
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.playlist_dock)
        self.playlist_dock.hide()
        self.btn_playlist.setChecked(False)


        # shortcuts and monitors
        self.create_monitor_shortcuts()
      

        self.update_license_label()    

          
    # --- license UI / actions (unchanged) ---
    def activate_license(self):
        dlg = QDialog(self); dlg.setWindowTitle("Ativar Licença"); dlg.setFixedSize(480,260)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel("<b>Cole sua chave de licença abaixo:</b>"))
        mid_layout = QHBoxLayout()
        self.mid_label = QLabel(machine_id()); self.mid_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        mid_layout.addWidget(QLabel("Machine ID:")); mid_layout.addWidget(self.mid_label)
        copy_btn = QPushButton("Copiar"); copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.mid_label.text())); mid_layout.addWidget(copy_btn)
        layout.addLayout(mid_layout)
        layout.addWidget(QLabel("<small>Envie este Machine ID para o suporte gerar sua licença.</small>"))
        self.input_key = QLineEdit(); self.input_key.setPlaceholderText("Cole sua chave de licença aqui..."); layout.addWidget(self.input_key)
        buttons = (QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box = QDialogButtonBox(buttons); layout.addWidget(btn_box)
        btn_box.accepted.connect(dlg.accept); btn_box.rejected.connect(dlg.reject)
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        key = self.input_key.text().strip()
        if not key: return
        parsed = parse_license_key(key)
        if not parsed: QMessageBox.critical(self, "Erro", "Licença inválida."); return
        if parsed["expiry"] < time.time(): QMessageBox.warning(self, "Erro", "Licença expirada."); return
        if parsed["machine"] and parsed["machine"] != machine_id(): QMessageBox.critical(self, "Erro", "Licença pertence a outra máquina."); return
        save_license_locally(key, parsed); self.is_licensed = True; self.license_info = parsed; self.update_license_label()
        QMessageBox.information(self, "Sucesso", "Licença ativada com sucesso!")

    def show_machine(self):
        QMessageBox.information(self, "Machine ID", machine_id())

    # --- player actions ---
    def update_license_label(self):
        if self.is_licensed:
            user = self.license_info["user"]
            self.setWindowTitle(f"Super Player — PREMIUM ({user})")
        else:
            self.setWindowTitle("Super Player — FREE")

    def open_file(self):
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Selecionar vídeos")
        dialog.setNameFilter("Vídeos (*.mp4 *.avi *.mkv *.mov *.wmv)")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)

        if not dialog.exec():
            return

        files = dialog.selectedFiles()

        if not files:
            return

        for path in files:
            if path in self.playlist:
                continue

        item = QListWidgetItem(self.video_icon, os.path.basename(path))
        item.setSizeHint(QSize(140, 90))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setData(Qt.ItemDataRole.UserRole, path)

        self.playlist_widget.addItem(item)
        self.playlist.append(path)

            # se ainda não estiver tocando nada, toca o primeiro
        if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self.current_index = 0
            self.play_video_from_playlist()






    def play_video(self, path: str):
        if not path:
            return

        path = str(path)

        if not os.path.exists(path):
            QMessageBox.warning(self, "Erro", f"Arquivo não encontrado:\n{path}")
            return

        try:
                # 🔥 RESET TOTAL
            self.player.stop()

                # 🔥 SEMPRE garantir o widget principal
            self.player.setVideoOutput(None)
            self.player.setVideoOutput(self.video_widget)

                # 🔥 setSource isolado
            url = QUrl.fromLocalFile(path)
            self.player.setSource(url)

                # 🔥 play isolado
            self.player.play()

            self.btn_play.setText("⏸️ Pausar")

        except Exception as e:
            QMessageBox.critical(self, "Erro ao reproduzir", str(e))



    def save_last_playlist(self):
        try:
            print("💾 Salvando playlist automática...")

            print("Playlist:", self.playlist)
            print("Index:", self.current_index)

            if not self.playlist:
                print("⚠ Playlist vazia, não salvou")
                return

            data = {
            "playlist": self.playlist,
            "current_index": self.current_index
        }

            LICENSE_DIR.mkdir(parents=True, exist_ok=True)

            with open(LAST_PLAYLIST_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            print("✅ Playlist salva em:", LAST_PLAYLIST_FILE)

        except Exception as e:
            print("❌ Erro ao salvar playlist:", e)



    

    def load_playlist(self):
        if not LAST_PLAYLIST_FILE.exists():
            return

        try:
            with open(LAST_PLAYLIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.playlist_widget.clear()
            self.playlist.clear()

            for path in data.get("playlist", []):
                if os.path.exists(path):
                    item = QListWidgetItem(os.path.basename(path))
                    item.setData(Qt.ItemDataRole.UserRole, path)
                    self.playlist_widget.addItem(item)
                    self.playlist.append(path)

            self.current_index = data.get("current_index", 0)

        except Exception as e:
            print("Erro ao carregar playlist automática:", e)



    def load_last_playlist(self):
        try:
            if not LAST_PLAYLIST_FILE.exists():
                print("ℹ️ Nenhuma playlist salva encontrada")
                return

            with open(LAST_PLAYLIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

                playlist = data.get("playlist", [])
                index = data.get("current_index", 0)

            if not playlist:
                print("ℹ️ Playlist salva vazia")
                return

                # 🔥 LIMPA TUDO PRIMEIRO
            self.playlist.clear()
            self.playlist_widget.clear()

                # 🔥 ADICIONA ITEM POR ITEM NA UI
            for path in playlist:
                if os.path.exists(path):
                    item = QListWidgetItem(os.path.basename(path))
                    item.setData(Qt.ItemDataRole.UserRole, path)
                    self.playlist_widget.addItem(item)
                    self.playlist.append(path)

                # 🔥 RESTAURA ÍNDICE
            self.current_index = min(index, len(self.playlist) - 1)

                # 🔥 DESTACA ITEM ATUAL
            if self.current_index >= 0:
                self.playlist_widget.setCurrentRow(self.current_index)

                print("✅ Playlist restaurada automaticamente")

        except Exception as e:
                print("❌ Erro ao carregar playlist automática:", e)


    def on_playlist_double_click(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return

        try:
            self.current_index = self.playlist.index(path)
        except ValueError:
            return

        self.play_video(path)




    def play_video_from_playlist(self):
            # segurança
        if not self.playlist:
            return

        if not (0 <= self.current_index < len(self.playlist)):
            return

            # ✅ DEFINE O PATH PRIMEIRO
        path = self.playlist[self.current_index]

        if not path:
            return

        path = str(path)

        if not os.path.exists(path):
            QMessageBox.warning(
            self,
            "Erro",
            f"Arquivo não encontrado:\n{path}"
        )
            return

            # 🔥 garante que o player usa o widget principal
        self.player.setVideoOutput(self.video_widget)

            # ▶️ reproduz
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()

        self.btn_play.setText("⏸️ Pausar")
        self.highlight_current_item()






    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause(); self.btn_play.setText("▶️ Reproduzir")
        else:
            self.player.play(); self.btn_play.setText("⏸️ Pausar")

    def stop_video(self):
        self.player.stop(); self.btn_play.setText("▶️ Reproduzir")

            
    def restore_to_main(self):
        """
        Volta o vídeo da janela externa para a janela principal,
        esconde a janela externa e restaura UI (dock, estado) de forma segura.
        """
        try:
        # Devolve o vídeo para o widget principal
            if hasattr(self, "player") and hasattr(self, "video_widget"):
                self.player.setVideoOutput(self.video_widget)

        # Esconde a janela externa
            if hasattr(self, "external_window") and self.external_window.isVisible():
                self.external_window.hide()

        # Mostra botão de sair fullscreen da janela principal
            if hasattr(self, "btn_exit_corner"):
                self.btn_exit_corner.show()

        
        except Exception as e:
            print("restore_to_main: erro inesperado:", e)


    def close_external_fullscreen(self):
        """
        Fecha SOMENTE a tela fullscreen externa, se estiver ativa.
        """
        if hasattr(self, "external_window") and self.external_window.isFullScreen():
            self.restore_to_main()

    def enter_fullscreen(self):
        if not hasattr(self, "video_window"):
            self.video_window = VideoWindow(
            self,
            exit_callback=self.exit_fullscreen
        )


       
    def exit_fullscreen(self):
        # ONLY exit fullscreen for the MAIN window (not the external window)
        if self.isFullScreen():
            # restore decorations and normal window state
            self.setWindowFlags(Qt.WindowType.Window)
            self.showNormal()
            # reposition and show the corner button now that we're windowed
            QTimer.singleShot(60, self.reposition_exit_button)
            return
        # if not main fullscreen, do nothing (we do not affect external_window here)
        return
    
        # === playlist methods ===
    def add_video_to_playlist(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Selecionar vídeos", "", "Vídeos (*.mp4 *.avi *.mkv *.mov *.mpg *.mpeg *.wmv)")
        if files:
            for f in files:
                item = QListWidgetItem(os.path.basename(f))
                item.setData(Qt.ItemDataRole.UserRole, f)
                self.playlist_widget.addItem(item)
            self.sync_playlist_from_widget()
            QMessageBox.information(self, "Playlist", f"{len(files)} vídeo(s) adicionados à lista!")

                        
    
    def clear_playlist(self):
        self.playlist_widget.clear()
        self.playlist.clear()
        self.current_index = 0


    def sync_playlist_from_widget(self, *args, **kwargs):
        new = []
        for i in range(self.playlist_widget.count()):
            it = self.playlist_widget.item(i)
            path = it.data(Qt.ItemDataRole.UserRole)
            if path: new.append(path)
        self.playlist = new

    def on_playlist_double_click(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path: return
        for i in range(self.playlist_widget.count()):
            if self.playlist_widget.item(i) is item:
                self.current_index = i; break
        self.play_video_from_playlist()

    def highlight_current_item(self):
        if 0 <= self.current_index < self.playlist_widget.count():
            self.playlist_widget.setCurrentRow(self.current_index)

    def play_next(self):
        self.sync_playlist_from_widget()
        if not self.playlist: return
        self.current_index = min(self.current_index + 1, len(self.playlist) - 1)
        self.play_video_from_playlist()

    def play_previous(self):
        self.sync_playlist_from_widget()
        if not self.playlist: return
        self.current_index = max(self.current_index - 1, 0)
        self.play_video_from_playlist()

    # --- dock handlers ---
    def toggle_playlist_dock(self):
        if self.playlist_dock.isVisible():
            self.playlist_dock.hide()
            self.btn_playlist.setChecked(False)
        else:
            self.playlist_dock.show()
            self.btn_playlist.setChecked(True)



    def on_dock_top_level_changed(self, top_level: bool):
        """
        called when dock is docked/undocked (floating).
        keep the toggle button state in sync so user can see it's open/floating.
        """
        self.btn_playlist.setChecked(
        self.playlist_dock.isVisible() or self.playlist_dock.isFloating()

    )
        
    def check_loop_position(self, position):
        if not self.video_loop_enabled:
            return

        duration = self.player.duration()
        if duration > 0 and position >= duration - 200:
            self.player.setPosition(0)
            self.player.play()


    def on_media_status_changed(self, status):
        print("STATUS:", status)
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            print("FIM DO VÍDEO")
            if self.video_loop_enabled:
                print("REINICIANDO LOOP")
                self.player.setPosition(0)
                self.player.play()



        
    def handle_media_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.loop_enabled:
                self.player.setPosition(0)
                self.player.play()


    def toggle_video_loop(self):
        if self.action_video_loop.isChecked():
            self.player.setLoops(QMediaPlayer.Loops.Infinite)
            self.loop_indicator.show()
        else:
            self.player.setLoops(QMediaPlayer.Loops.Once)
            self.loop_indicator.hide()

    def on_slider_pressed(self):
        self.was_playing = (
        self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
    )

    # força decodificação sem tocar "de verdade"
        self.player.setPlaybackRate(0.01)
        self.player.play()


    def set_position(self, position):
        self.player.setPosition(position)


    def on_slider_released(self):
    # volta ao normal
        self.player.setPlaybackRate(1.0)

        if not self.was_playing:
            self.player.pause()

    


    








        
                 

    def eventFilter(self, obj, event):
        if obj == self.video_widget and event.type() == QEvent.Type.ContextMenu:
            self.show_context_menu(event.globalPos())
            return True
        return super().eventFilter(obj, event)






    # === UI helpers / seek / shortcuts ===
    def update_position(self, position):
        if not self.slider.isSliderDown():
            self.slider.setValue(position)


    def update_duration(self, duration):
        self.slider.setRange(0, duration)


    def set_position(self, position):
        self.player.setPosition(position)


    def jump(self, seconds):
        newpos = self.player.position() + seconds * 1000
        newpos = max(0, min(newpos, self.player.duration()))
        self.player.setPosition(newpos)
    
    def create_monitor_shortcuts(self):
        screens = QApplication.screens()
        for i, screen in enumerate(screens, start=1):
            act = QAction(self); act.setShortcut(QKeySequence(f"Ctrl+F{i}")); act.triggered.connect(lambda _, m=i: self.play_fullscreen_on_monitor(m)); self.addAction(act)

    def play_fullscreen_on_monitor(self, monitor_index):
        screens = QApplication.screens()
        if monitor_index - 1 >= len(screens):
            QMessageBox.warning(self, "Erro", "Monitor não encontrado."); return
        screen = screens[monitor_index - 1]
        # envia saída do player para a janela externa
        self.player.setVideoOutput(self.external_window.video_widget)
        # hide dock while in external fullscreen (optional)
        self.playlist_dock.hide()
        self.btn_playlist.setChecked(False)
        # hide the corner exit button when going to external fullscreen
        self.btn_exit_corner.hide()
        self.external_window.show_on_screen(screen)
        self.external_window.activateWindow()
        self.external_window.raise_()

    # reposition exit button when the window resizes
    def resizeEvent(self, event):
        super().resizeEvent(event)

        if hasattr(self, "btn_exit_corner"):
            self.reposition_exit_button()

    
    def closeEvent(self, event):
        self.save_last_playlist()
        super().closeEvent(event)
    

                     

# --- main ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    show_splash(app)
    win = SuperPlayer()
    win.show()
    sys.exit(app.exec())
