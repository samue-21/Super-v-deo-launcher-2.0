import sys
import time
import uuid
import platform
import hashlib
import hmac
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QCheckBox, QMessageBox
)
from PyQt6.QtCore import Qt

# -------------------------------------------------------
# MESMO SECRET DO PLAYER  (MUITO IMPORTANTE!)
# -------------------------------------------------------
SECRET = b"TROQUE-Essa-SECRET-ANTES-DE-DISTRIBUIR"  # COPIE O MESMO DO PLAYER!!!


# -------------------------------------------------------
# FUNÇÕES DE LICENCIAMENTO (MESMAS DO PLAYER)
# -------------------------------------------------------

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


def make_license(user: str, days_valid=365, bind_machine=True, target_machine_id=None):
    expiry_ts = int(time.time()) + (days_valid * 86400)

    if bind_machine:
        if not target_machine_id:
            target_machine_id = machine_id()
    else:
        target_machine_id = ""

    payload = f"{user}|{expiry_ts}|{target_machine_id}".encode()
    payload_hex = payload.hex()
    signature = make_hmac(payload)

    return f"PLR-{payload_hex}-{signature}"


# -------------------------------------------------------
# JANELA DO GERADOR DE LICENÇA
# -------------------------------------------------------

class LicenseGenerator(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Gerador de Licenças — Super Player")
        self.setFixedSize(520, 350)

        layout = QVBoxLayout()

        # CAMPO DE USUÁRIO
        layout.addWidget(QLabel("<b>Nome do usuário/cliente:</b>"))
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Ex: João Silva")
        layout.addWidget(self.user_input)

        # MACHINE ID
        layout.addWidget(QLabel("<b>Machine ID:</b>"))
        mid_layout = QHBoxLayout()

        self.machine_input = QLineEdit()
        self.machine_input.setPlaceholderText("Cole ou digite o Machine ID")
        self.machine_input.setText("")  # vazio inicialmente
        mid_layout.addWidget(self.machine_input)

        btn_paste_mid = QPushButton("Local")
        btn_paste_mid.setToolTip("Usar o Machine ID desta máquina")
        btn_paste_mid.clicked.connect(lambda: self.machine_input.setText(machine_id()))
        mid_layout.addWidget(btn_paste_mid)

        layout.addLayout(mid_layout)

        # DIAS DE VALIDADE
        layout.addWidget(QLabel("<b>Validade (dias):</b>"))
        self.days_input = QLineEdit()
        self.days_input.setPlaceholderText("Ex: 365")
        self.days_input.setText("365")
        layout.addWidget(self.days_input)

        # AMARRAR À MÁQUINA
        self.bind_checkbox = QCheckBox("Amarrar licença ao Machine ID")
        self.bind_checkbox.setChecked(True)
        layout.addWidget(self.bind_checkbox)

        # BOTÃO GERAR
        btn_generate = QPushButton("Gerar Licença")
        btn_generate.clicked.connect(self.generate_license)
        layout.addWidget(btn_generate)

        # SAÍDA DA LICENÇA
        layout.addWidget(QLabel("<b>Licença Gerada:</b>"))
        self.output = QLineEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

        # BOTÃO COPIAR
        btn_copy = QPushButton("Copiar Licença")
        btn_copy.clicked.connect(self.copy_license)
        layout.addWidget(btn_copy)

        self.setLayout(layout)

    # -------------------------------------------------------
    # GERAR LICENÇA
    # -------------------------------------------------------
    def generate_license(self):
        user = self.user_input.text().strip()
        if not user:
            QMessageBox.warning(self, "Erro", "Informe o nome do usuário.")
            return

        try:
            days = int(self.days_input.text().strip())
        except:
            QMessageBox.warning(self, "Erro", "Dias inválidos.")
            return

        bind = self.bind_checkbox.isChecked()
        mid = self.machine_input.text().strip()

        if bind and not mid:
            QMessageBox.warning(self, "Erro", "Você marcou para amarrar à máquina, mas não forneceu Machine ID.")
            return

        license_key = make_license(
            user=user,
            days_valid=days,
            bind_machine=bind,
            target_machine_id=mid
        )

        self.output.setText(license_key)

    # -------------------------------------------------------
    # COPIAR LICENÇA PARA ÁREA DE TRANSFERÊNCIA
    # -------------------------------------------------------
    def copy_license(self):
        text = self.output.text().strip()
        if not text:
            QMessageBox.warning(self, "Erro", "Nenhuma licença gerada.")
            return

        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copiado", "Licença copiada para a área de transferência.")


# -------------------------------------------------------
# RUN
# -------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LicenseGenerator()
    window.show()
    sys.exit(app.exec())
