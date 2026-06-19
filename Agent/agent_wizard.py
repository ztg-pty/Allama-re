from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QLineEdit, QPushButton, QLabel, QComboBox, QFrame,
)
from PySide6.QtCore import Qt, QEvent


class AgentWizard(QWidget):
    def __init__(self, on_configured=None, deploy_port=None):
        super().__init__()
        self._on_configured = on_configured
        self._deploy_port = deploy_port or 11434
        self._base_url = ""
        self._api_key = ""
        self._model = ""
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._stack = QStackedWidget()
        layout.addWidget(self._stack)
        self._stack.addWidget(self._build_step1())
        self._stack.addWidget(self._build_step2())
        self._stack.addWidget(self._build_step3())
        self._stack.setCurrentIndex(0)

    def _build_step1(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QFrame()
        card.setObjectName("wizardCard")
        card.setStyleSheet("""
            QFrame#wizardCard {
                background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;
                padding: 32px; max-width: 480px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)
        title = QLabel("步骤 1：服务地址")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b;")
        card_layout.addWidget(title)
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("http://localhost:11434")
        self._url_input.setStyleSheet("padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 13px;")
        card_layout.addWidget(self._url_input)
        quick_row = QHBoxLayout()
        quick_row.setSpacing(8)
        local_btn = QPushButton("使用本地部署")
        local_btn.setStyleSheet("""
            QPushButton { background: #ffffff; color: #3b82f6; border: 1px solid #3b82f6;
                          border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: bold; }
            QPushButton:hover { background: #3b82f6; color: #ffffff; }
        """)
        local_btn.clicked.connect(lambda: self._url_input.setText(f"http://127.0.0.1:{self._deploy_port}"))
        quick_row.addWidget(local_btn)
        ollama_btn = QPushButton("使用 Ollama")
        ollama_btn.setStyleSheet("""
            QPushButton { background: #ffffff; color: #3b82f6; border: 1px solid #3b82f6;
                          border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: bold; }
            QPushButton:hover { background: #3b82f6; color: #ffffff; }
        """)
        ollama_btn.clicked.connect(lambda: self._url_input.setText("http://localhost:11434"))
        quick_row.addWidget(ollama_btn)
        quick_row.addStretch()
        card_layout.addLayout(quick_row)
        nav_row = QHBoxLayout()
        nav_row.addStretch()
        next_btn = QPushButton("下一步")
        next_btn.setStyleSheet("""
            QPushButton { background: #3b82f6; color: #ffffff; border: none;
                          border-radius: 6px; padding: 8px 20px; font-size: 12px; font-weight: bold; }
            QPushButton:hover { background: #2563eb; }
        """)
        next_btn.clicked.connect(self._to_step2)
        nav_row.addWidget(next_btn)
        card_layout.addLayout(nav_row)
        card.setFixedWidth(480)
        layout.addWidget(card)
        return page

    def _build_step2(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QFrame()
        card.setObjectName("wizardCard")
        card.setStyleSheet("""
            QFrame#wizardCard {
                background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;
                padding: 32px; max-width: 480px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)
        title = QLabel("步骤 2：API 密钥（可选）")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b;")
        card_layout.addWidget(title)
        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("留空则跳过密钥验证")
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setStyleSheet("padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 13px;")
        card_layout.addWidget(self._key_input)
        toggle_btn = QPushButton("👁 显示/隐藏")
        toggle_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #64748b; border: none;
                          font-size: 11px; }
            QPushButton:hover { color: #3b82f6; }
        """)
        toggle_btn.clicked.connect(self._toggle_key_visibility)
        card_layout.addWidget(toggle_btn)
        nav_row = QHBoxLayout()
        skip_btn = QPushButton("跳过")
        skip_btn.setStyleSheet("""
            QPushButton { background: #ffffff; color: #64748b; border: 1px solid #cbd5e1;
                          border-radius: 6px; padding: 8px 20px; font-size: 12px; }
            QPushButton:hover { background: #f1f5f9; }
        """)
        skip_btn.clicked.connect(self._to_step3)
        nav_row.addWidget(skip_btn)
        nav_row.addStretch()
        back_btn = QPushButton("上一步")
        back_btn.setStyleSheet("""
            QPushButton { background: #ffffff; color: #64748b; border: 1px solid #cbd5e1;
                          border-radius: 6px; padding: 8px 20px; font-size: 12px; }
            QPushButton:hover { background: #f1f5f9; }
        """)
        back_btn.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        nav_row.addWidget(back_btn)
        next_btn = QPushButton("下一步")
        next_btn.setStyleSheet("""
            QPushButton { background: #3b82f6; color: #ffffff; border: none;
                          border-radius: 6px; padding: 8px 20px; font-size: 12px; font-weight: bold; }
            QPushButton:hover { background: #2563eb; }
        """)
        next_btn.clicked.connect(self._to_step3)
        nav_row.addWidget(next_btn)
        card_layout.addLayout(nav_row)
        card.setFixedWidth(480)
        layout.addWidget(card)
        return page

    def _build_step3(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QFrame()
        card.setObjectName("wizardCard")
        card.setStyleSheet("""
            QFrame#wizardCard {
                background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;
                padding: 32px; max-width: 480px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)
        title = QLabel("步骤 3：模型名称")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b;")
        card_layout.addWidget(title)
        self._model_input = QLineEdit()
        self._model_input.setPlaceholderText("llama3 / gpt-4o-mini")
        self._model_input.setStyleSheet("padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 13px;")
        card_layout.addWidget(self._model_input)
        nav_row = QHBoxLayout()
        back_btn = QPushButton("上一步")
        back_btn.setStyleSheet("""
            QPushButton { background: #ffffff; color: #64748b; border: 1px solid #cbd5e1;
                          border-radius: 6px; padding: 8px 20px; font-size: 12px; }
            QPushButton:hover { background: #f1f5f9; }
        """)
        back_btn.clicked.connect(lambda: self._stack.setCurrentIndex(1))
        nav_row.addWidget(back_btn)
        nav_row.addStretch()
        start_btn = QPushButton("开始对话")
        start_btn.setStyleSheet("""
            QPushButton { background: #3b82f6; color: #ffffff; border: none;
                          border-radius: 6px; padding: 8px 20px; font-size: 12px; font-weight: bold; }
            QPushButton:hover { background: #2563eb; }
        """)
        start_btn.clicked.connect(self._finish)
        nav_row.addWidget(start_btn)
        card_layout.addLayout(nav_row)
        card.setFixedWidth(480)
        layout.addWidget(card)
        return page

    def _to_step2(self):
        url = self._url_input.text().strip()
        if not url:
            return
        self._base_url = url
        self._stack.setCurrentIndex(1)

    def _to_step3(self):
        self._api_key = self._key_input.text().strip()
        self._stack.setCurrentIndex(2)

    def _toggle_key_visibility(self):
        if self._key_input.echoMode() == QLineEdit.EchoMode.Password:
            self._key_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self._key_input.setEchoMode(QLineEdit.EchoMode.Password)

    def _finish(self):
        self._model = self._model_input.text().strip()
        if not self._model:
            return
        if self._on_configured:
            self._on_configured({
                "base_url": self._base_url,
                "api_key": self._api_key,
                "model": self._model,
            })
