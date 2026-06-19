# Qt6 (PySide6) + QWebEngineView 迁移方案

## 背景

Tkinter 三次嵌入式尝试均失败（DirectComposition 冲突、COM VTable bug），pywebview 只能打开独立窗口无法嵌入。**Qt WebEngine** 基于 Chromium，原生支持同窗口嵌入，是唯一可靠的方案。

## 方案

```
PySide6 (Qt6) + QWebEngineView
├── 侧边栏: QFrame + QPushButton（模型部署 / 聊天对话）
├── 部署页: 保留现有业务逻辑，UI 控件用 Qt 重写
│   ├── QComboBox（模型选择）
│   ├── QLineEdit / QSpinBox（参数输入）
│   ├── QPushButton（启动/停止/刷新）
│   └── QPlainTextEdit（日志）
└── 聊天页: QWebEngineView ← 直接嵌入 llama-ui（http://127.0.0.1:{port}）
    ├── toolbar: 重新加载按钮、浏览器打开按钮、URL 标签
    └── QWebEngineView（填满剩余空间）
```

## 技术选型

| 方案 | 许可 | 嵌入 | 大小 |
|------|------|------|------|
| PySide6 + QWebEngineView | LGPL | **同一窗口嵌入** | ~120MB |
| PyQt5 + QWebEngineView | GPL/商业 | 同一窗口嵌入 | ~100MB |
| CEFPython + Tkinter | BSD | 可嵌入但双事件循环 | ~80MB |

**选 PySide6**：LGPL 无许可证问题，Qt 官方支持，QWebEngineView 成熟稳定，同一窗口嵌入。

## 依赖变更

```
requirements.txt:
  - customtkinter>=5.2.0
  + PySide6>=6.5.0
  + PySide6-WebEngine>=6.5.0  (或 PySide6-Essentials 已包含)
    psutil>=5.9.0
    pywebview>=5.0  （可移除，Qt 已内置 WebEngine）
```

## 实现要点

### 1. 窗口结构

```python
class MainWindow(QMainWindow):
    def __init__(self):
        # 主窗口
        self.setWindowTitle("Allama")
        self.resize(1100, 700)

        # 中心 widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        # 侧边栏 (160px)
        sidebar = QFrame()
        sidebar.setFixedWidth(160)
        sidebar_layout = QVBoxLayout(sidebar)

        btn_deploy = QPushButton("🚀 模型部署")
        btn_chat = QPushButton("💬 聊天对话")
        sidebar_layout.addWidget(btn_deploy)
        sidebar_layout.addWidget(btn_chat)
        sidebar_layout.addStretch()

        # 内容区 (QStackedWidget 切换页面)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.build_deploy_page())  # 索引 0
        self.stack.addWidget(self.build_chat_page())    # 索引 1

        layout.addWidget(sidebar)
        layout.addWidget(self.stack)
```

### 2. 聊天页嵌入 WebEngine

```python
def build_chat_page(self):
    page = QWidget()
    layout = QVBoxLayout(page)

    # Toolbar
    toolbar = QHBoxLayout()
    self.chat_url_label = QLabel("")
    btn_reload = QPushButton("🔄 重新加载")
    btn_browser = QPushButton("🌐 在浏览器打开")
    toolbar.addWidget(QLabel("💬 聊天对话"))
    toolbar.addStretch()
    toolbar.addWidget(self.chat_url_label)
    toolbar.addWidget(btn_reload)
    toolbar.addWidget(btn_browser)
    layout.addLayout(toolbar)

    # WebEngine 嵌入
    self.webview = QWebEngineView()
    self.webview.setUrl(QUrl("about:blank"))
    layout.addWidget(self.webview)

    # 状态标签
    self.chat_status = QLabel("")
    layout.addWidget(self.chat_status)

    return page
```

### 3. WebView2 Runtime 处理

QWebEngineView 自带 Chromium，**无需外部 WebView2 Runtime**。删除 `_find_webview2_runtime()`、`_download_webview2_runtime()`、`_PyWebViewBridge` 等全部 Runtime 相关代码。

### 4. 部署页控件映射

| CTkinter | PySide6 |
|----------|---------|
| `CTkComboBox` | `QComboBox` |
| `CTkEntry` | `QLineEdit` |
| `CTkButton` | `QPushButton` |
| `CTkLabel` | `QLabel` |
| `CTkTextbox` | `QPlainTextEdit` |
| `CTkCheckBox` | `QCheckBox` |
| `CTkProgressBar` | `QProgressBar` |
| `CTkFrame` | `QFrame` |
| `StringVar` | `QLineEdit.text()` |

### 5. 信号连接

```python
# 替代 Tkinter event bindings
btn_start.clicked.connect(self._start_deployment)
btn_stop.clicked.connect(self._stop_deployment)
combo_model.currentTextChanged.connect(self._on_model_select)
combo_mmproj.currentTextChanged.connect(self._on_mmproj_select)
webview.loadFinished.connect(self._on_webview_loaded)
```

### 6. 保留不变的后端

以下模块**完全不变**：
- `ModelScanner` — 模型扫描
- `BatParamMapper` — 参数映射
- `PortAllocator` — 端口分配
- `TempBatGenerator` — Bat 生成
- `DeploymentManager` — 进程管理
- `ApiServer` — Ollama API
- `OllamaConverter` / `OpenAIConverter` — 协议转换
- `_cleanup()` 退出清理逻辑

### 7. 需要删除的模块

- `_find_webview2_runtime()` — QWebEngine 自带 Chromium
- `_download_webview2_runtime()` — 不再需要下载
- `_install_webview2()` — 不再需要安装
- `_PyWebViewBridge` — QWebEngineView 替代
- `_run_webview()` — QWebEngineView 替代
- `_extract_webview2_runtime()` — 不再需要解压
- `_check_runtime()` — 不再需要运行时检测
- `_download_webview2()` — 不再需要下载 UI
- `_wv_status_label` / `_wv_download_btn` / `_wv_progress` — 不再需要

### 8. 简化后的聊天页逻辑

```python
def _launch_embed(self):
    port = self._deploy_manager.effective_openai_port
    url = f"http://127.0.0.1:{port}"
    self.webview.setUrl(QUrl(url))
    self.chat_status.setText("✅ llama-ui 已嵌入")
    return True

def _reload_chat(self):
    self.webview.reload()

def _open_in_browser(self):
    import webbrowser
    port = self._deploy_manager.effective_openai_port
    webbrowser.open(f"http://127.0.0.1:{port}")
```

## 文件变更

| 文件 | 变更 | 说明 |
|------|------|------|
| `requirements.txt` | customtkinter → PySide6 | 替换 GUI 框架 |
| `main.py` | 更新依赖检查列表 | +PySide6 |
| `llama.py` | **重写** App 类 UI | ~300 行 Qt 替换 ~500 行 Tkinter |
| `llama.py` | **删除** Runtime 检测/下载 | ~60 行 |
| `llama.py` | **删除** pywebview 封装 | ~50 行 |
| `llama.py` | **保留** 所有后端模块 | 不变 |

**净变化**：~1500 行 → ~1200 行（删除 Runtime/pywebview 代码，Qt UI 更紧凑）

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| PySide6 安装失败 | 提供 pip 镜像源备用 |
| QWebEngineView 空白 | 检查 WebView2 Runtime（Evergreen 通常已安装） |
| Qt 样式与平台不一致 | 使用 `QApplication.setStyle("Fusion")` 统一跨平台样式 |
| 首次启动慢 | QWebEngine 初始化 ~2-3 秒，启动时预加载 |

## 实施步骤

1. 更新 `requirements.txt` 和 `main.py`
2. 在 `llama.py` 中新增 `QtApp` 类（QMainWindow）
3. 实现侧边栏 + QStackedWidget 页面切换
4. 实现部署页（组合框、参数输入、按钮、日志）
5. 实现聊天页（QWebEngineView + toolbar）
6. 迁移所有事件处理（信号/槽）
7. 删除 Runtime 检测/pywebview 相关代码
8. 删除旧 `App` 类和 `ctk` 导入
9. 更新 `main()` 入口
10. 测试：部署、聊天嵌入、停止服务、重新加载
