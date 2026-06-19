
import threading
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QTextEdit, QCheckBox, QFileDialog,
)
from PySide6.QtCore import Qt, QEvent, QTimer

import logging

from Agent.core.event_bus import SimpleEventBus

logger = logging.getLogger("agent_chat")

MAX_TOOL_ROUNDS = 10
from Agent.tool_executor import ToolExecutor
from Agent.core.agent_loop import StatelessAgentLoop


class MessageBubble(QWidget):
    def __init__(self, sender, text):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel(sender)
        title.setStyleSheet("font-weight: bold; color: #1e293b;")
        content = QLabel(text)
        content.setStyleSheet("background: #f1f5f9; border-radius: 8px; padding: 8px; color: #334155;")
        content.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(content)


class ToolCallBubble(QWidget):
    def __init__(self, tool, params):
        super().__init__()
        layout = QHBoxLayout(self)
        label = QLabel(f"工具: {tool} ({params})")
        label.setStyleSheet("background: #eff6ff; color: #3b82f6; border-radius: 6px; padding: 6px;")
        layout.addWidget(label)


class ToolResultBubble(QWidget):
    def __init__(self, result):
        super().__init__()
        layout = QHBoxLayout(self)
        label = QLabel(f"结果: {result}")
        label.setStyleSheet("background: #f0fdf4; color: #22c55e; border-radius: 6px; padding: 6px;")
        layout.addWidget(label)


class AgentChatWidget(QWidget):
    def __init__(self, client, parent=None):
        super().__init__(parent)
        self._client = client
        self._event_bus = SimpleEventBus()
        self._tool_executor = ToolExecutor(parent_widget=self)
        self._tool_registry = self._tool_executor.registry
        self._agent_loop = StatelessAgentLoop(provider=client, tool_registry=self._tool_registry, logger=logger, event_bus=self._event_bus, max_tool_rounds=MAX_TOOL_ROUNDS)
        self._messages = [{"role": "system", "content": "AI programming assistant"}]
        self._allow_exec = False
        self._streaming = False
        self._event_bus.on("agent.tool.call", self._on_tool_call_event)
        self._event_bus.on("agent.tool.result", self._on_tool_result_event)
        self._event_bus.on("agent.error", self._on_agent_error_event)
        self._init_ui()

    def _on_tool_call_event(self, tool, params, **kwargs):
        self._safe_append_bubble(ToolCallBubble(tool, str(params)))

    def _on_tool_result_event(self, tool, result, **kwargs):
        self._safe_append_bubble(ToolResultBubble(result[:4000]))

    def _on_agent_error_event(self, error, **kwargs):
        self._safe_append_text(f"Agent error: {error}")

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header = QHBoxLayout()
        header.setContentsMargins(16, 8, 16, 8)
        title = QLabel("Agent Chat")
        header.addWidget(title)
        header.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_chat)
        header.addWidget(clear_btn)
        layout.addLayout(header)
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._messages_container = QWidget()
        self._messages_layout = QVBoxLayout(self._messages_container)
        self._messages_layout.setContentsMargins(16, 8, 16, 8)
        self._messages_layout.setSpacing(4)
        self._messages_layout.addStretch()
        self._scroll_area.setWidget(self._messages_container)
        layout.addWidget(self._scroll_area, 1)
        toolbar = QHBoxLayout()
        file_btn = QPushButton("Select File")
        file_btn.clicked.connect(self._select_file)
        toolbar.addWidget(file_btn)
        self._exec_check = QCheckBox("Allow command execution")
        self._exec_check.toggled.connect(lambda checked: setattr(self, "_allow_exec", checked))
        toolbar.addWidget(self._exec_check)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        input_row = QHBoxLayout()
        self._input = QTextEdit()
        self._input.setPlaceholderText("Type a message...")
        self._input.setMaximumHeight(80)
        self._input.installEventFilter(self)
        input_row.addWidget(self._input, 1)
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self._send)
        self._send_btn = send_btn
        input_row.addWidget(send_btn)
        layout.addLayout(input_row)

    def eventFilter(self, obj, event):
        if obj == self._input and event.type() == QEvent.Type.KeyPress:
            key_event = event
            if key_event.key() == Qt.Key.Key_Return and not (key_event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self._send()
                return True
        return super().eventFilter(obj, event)

    def _append_bubble(self, bubble):
        self._messages_layout.insertWidget(self._messages_layout.count() - 1, bubble)

    def _scroll_to_bottom(self):
        QTimer.singleShot(50, lambda: self._scroll_area.verticalScrollBar().setValue(self._scroll_area.verticalScrollBar().maximum()))

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Select File')
        if path:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            truncated = content[:4000]
            if len(content) > 4000:
                truncated += chr(10) + '... truncated'
            new_text = self._input.toPlainText() + chr(10) + '[File: ' + path + ']' + chr(10) + truncated
            self._input.setPlainText(new_text)

    def _send(self):
        text = self._input.toPlainText().strip()
        if not text or self._streaming:
            return
        self._input.clear()
        self._streaming = True
        self._send_btn.setEnabled(False)
        msg = {'role': 'user', 'content': text}
        self._messages.append(msg)
        self._append_bubble(MessageBubble('You', text))
        self._scroll_to_bottom()
        threading.Thread(target=self._run_agent_loop, daemon=True).start()

    def _run_agent_loop(self):
        try:
            messages = list(self._messages)
            self._agent_loop.run_loop(
                messages=messages,
                model=self._client._model,
                tool_executor=self._tool_executor.execute_tool,
                temperature=0.7,
                max_tokens=4096,
            )
            self._messages = messages
        except Exception as e:
            self._safe_append_text(f'Error: {e}')
        self._streaming = False
        self._safe_enable_send()

    def _safe_append_bubble(self, bubble):
        QTimer.singleShot(0, lambda: self._append_bubble(bubble))

    def _safe_append_text(self, text):
        QTimer.singleShot(0, lambda: self._append_bubble(MessageBubble('Agent', text)))

    def _safe_enable_send(self):
        QTimer.singleShot(0, lambda: self._send_btn.setEnabled(True))

    def _clear_chat(self):
        self._messages = [{'role': 'system', 'content': 'AI programming assistant'}]
        while self._messages_layout.count() > 1:
            item = self._messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
