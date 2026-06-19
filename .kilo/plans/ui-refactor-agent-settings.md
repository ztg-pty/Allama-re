# Allama UI 重构与 Agent 模式开发计划

## 概述

对 Allama 客户端进行纯视觉 UI 重构，新增「Agent 模式」模块，并补全「设置」功能。窗口固定 1600×800，全局白底，侧边栏透明悬浮联动效果。

---

## 一、全局 UI 重构

### 1.1 窗口约束

**文件**: `llama.py` - `QtApp.__init__()`（~line 793）

| 变更 | 改前 | 改后 |
|------|------|------|
| 尺寸 | `resize(1200, 750)` | `setFixedSize(1600, 800)` |
| 最小尺寸 | `setMinimumSize(900, 600)` | 删除 |
| 居中 | 无 | 启动后调用 `self._center_window()` |

```python
def _center_window(self):
    screen = QApplication.primaryScreen().availableGeometry()
    self.move((screen.width() - 1600) // 2, (screen.height() - 800) // 2)
```

### 1.2 全局背景色纯白

**作用范围**: `QMainWindow` centralWidget、`QStackedWidget`、各页面、弹窗。

| 位置 | 改法 |
|------|------|
| `_init_ui()` | `central.setStyleSheet("background-color: #ffffff;")` |
| `_build_sidebar()` | `QFrame#sidebar { background-color: #ffffff; border-right: 1px solid #e2e8f0; }` |
| `_build_deploy_page()` | 删除 `background: #f8fafc` 分组背景，全部改为 `#ffffff`；`#1e293b` 暗色区域改为 `#ffffff` 浅色 |
| `_build_chat_page()` | toolbar / status 背景透明，继承白底 |
| `_build_settings_page()` | 删除 `#f8fafc` 分组背景，全部 `#ffffff`，边框保留 `#e2e8f0` |

日志区域（`_log_text`）保留暗色 `#1e293b` 代码风格，不属于全局白底范围。

### 1.3 侧边栏重构

**文件**: `llama.py` - `_build_sidebar()`（~line 852）

**按钮顺序**: `部署模型` → `聊天` → `设置` → `Agent 模式`

**按钮文案调整**:

- `模型部署` → `部署模型`
- `聊天对话` → `聊天`
- `⚙ 设置` → `设置`（去掉齿轮 emoji，保持纯文字风格）

**按钮间距**: `layout.setSpacing(20)`（≈5mm at 96dpi）

**侧边栏宽度**: 从 160px 扩到 200px（适配 4 个按钮 + 更大窗口）

**核心交互——悬浮联动变色**:

```python
# 安装 eventFilter 到每个按钮
for btn in [self._btn_deploy, self._btn_chat, self._btn_settings, self._btn_agent]:
    btn.installEventFilter(self)
```

在 `eventFilter` 中：

```python

HOVER_COLOR = "#3b82f6"  # 主视觉蓝

def eventFilter(self, obj, event):
    if event.type() == QEvent.Type.Enter:
        obj.setStyleSheet(f"background-color: {HOVER_COLOR}; color: #ffffff; ...")
        self._sidebar.setStyleSheet(
            f"QFrame#sidebar {{ background-color: {HOVER_COLOR}; border-right: 1px solid {HOVER_COLOR}; }}"
            f"QPushButton {{ background-color: transparent; color: #ffffff; ... }}"
            f"QPushButton:hover {{ background-color: rgba(255,255,255,0.15); color: #ffffff; }}"
            f"QPushButton:checked {{ background-color: rgba(255,255,255,0.25); color: #ffffff; font-weight: bold; }}"
        )
    elif event.type() == QEvent.Type.Leave:
        obj.setStyleSheet("")
        self._sidebar.setStyleSheet(RESET_SIDEBAR_STYLE)
    return super().eventFilter(obj, event)
```

**默认态（无悬浮）**:

```css
QFrame#sidebar { background-color: #ffffff; border-right: 1px solid #e2e8f0; }
QPushButton {
    background-color: transparent; color: #64748b;
    border: none; border-radius: 8px; padding: 12px 16px;
    text-align: left; font-size: 13px;
}
QPushButton:hover { background-color: transparent; color: #64748b; }
QPushButton:checked { background-color: #eff6ff; color: #3b82f6; font-weight: bold; }
```

**悬浮态**:
- 按钮: 填充 `#3b82f6`，文字白色
- 侧边栏整体: 背景 `#3b82f6`
- 其他按钮: 文字白色，悬浮时 `rgba(255,255,255,0.15)` 背景
- 选中按钮: `rgba(255,255,255,0.25)` 背景

**离开悬浮**:
- 全部恢复默认态样式

### 1.4 部署页视觉调整

**文件**: `llama.py` - `_build_deploy_page()`（~line 897）

- 分组框 `#f8fafc` → `#ffffff`，添加 `border: 1px solid #e2e8f0; border-radius: 8px;`
- `QComboBox / QLineEdit` 保留白色输入框样式
- 日志区 `QPlainTextEdit` 保留暗色 `#1e293b` 风格（代码日志）
- 按钮（启动/停止/测试）改为白底蓝字幽灵按钮风格：
  
  ```css
  QPushButton {
      background-color: #ffffff; color: #3b82f6;
      border: 1px solid #3b82f6; border-radius: 6px;
      padding: 6px 14px; font-size: 11px; font-weight: bold;
  }
  QPushButton:hover { background-color: #3b82f6; color: #ffffff; }
  QPushButton:disabled { border-color: #cbd5e1; color: #cbd5e1; }
  ```
- 主要行动按钮（启动部署等）保留实色 `background: #3b82f6; color: #fff;`

### 1.5 聊天页视觉调整

**文件**: `llama.py` - `_build_chat_page()`（~line 1006）

- 页面背景 `#ffffff`
- toolbar 按钮改为白底蓝字幽灵按钮（同上）
- `_chat_status` 文字颜色适配白底
- WebView 内 llama-ui 自行适配，不干预

### 1.6 状态栏

- 背景 `#ffffff`，文字 `#64748b`
- 状态指示灯保留彩色

---

## 二、设置模块补全

### 2.1 新增配置项

**文件**: `llama.py` - `AppSettings._DEFAULTS`（~line 62）

```python
_DEFAULTS = {
    "default_context": "8192",
    "default_ngl": "999",
    "default_n_predict": "4096",
    "stop_model_on_exit": True,
    "enable_mmproj_default": False,  # 新增：全局视觉模型默认开关
}
```

### 2.2 设置页新增控件

**文件**: `llama.py` - `_build_settings_page()`（~line 1044）

在「行为设置」分组中，新增一行：

```python
self._settings_mmproj = QCheckBox("默认启用视觉模型（部署时自动勾选）")
self._settings_mmproj.setChecked(self._settings.get("enable_mmproj_default"))
self._settings_mmproj.toggled.connect(
    lambda checked: self._settings.set("enable_mmproj_default", checked)
)
```

### 2.3 部署页联动

**文件**: `llama.py` - `_scan_models()`（~line 1181）或 `_build_deploy_page()`

在模型扫描完成后，根据 `self._settings.get("enable_mmproj_default")` 自动设置 `_mmproj_check` 状态：

```python
# _scan_models() 末尾追加
if self._settings.get("enable_mmproj_default") and self._mmproj_models:
    self._mmproj_check.setChecked(True)
```

### 2.4 恢复默认值

`_restore_defaults()` 增加对 `_settings_mmproj` 的 blockSignals + setChecked 处理。

### 2.5 样式适配

设置页控件继承全局白底风格，按钮改为白底蓝字幽灵按钮，分组框 `#ffffff` + `border`。

---

## 三、Agent 模式（全新模块）

### 3.1 目录结构

```
Agent/
├── __init__.py          # 空文件或导出
├── agent_wizard.py      # 三步向导页面（QWidget）
├── agent_chat.py        # Agent 原生聊天界面（QWidget）
├── api_client.py        # API 调用客户端（本地 + 外部）
├── tool_executor.py     # 工具执行器（文件读取、命令执行、提示词注入）
└── system_prompts.py    # Cline 风格的 system prompt 模板
```

### 3.2 入口

**文件**: `llama.py` - `_build_sidebar()` + `_init_ui()`

- 第 4 个按钮 `_btn_agent = QPushButton("Agent 模式")`
- Stack 索引 3: `self._stack.addWidget(self._build_agent_page())`
- `_switch_page()` 追加 `self._btn_agent.setChecked(index == 3)`

**`_build_agent_page()` 方法**（~400 行新代码）:
```python
def _build_agent_page(self) -> QWidget:
    from Agent.agent_wizard import AgentWizard
    from Agent.agent_chat import AgentChatWidget

    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)

    self._agent_stack = QStackedWidget()
    self._agent_wizard = AgentWizard(self._on_agent_configured)
    self._agent_chat = None
    self._agent_stack.addWidget(self._agent_wizard)  # index 0
    layout.addWidget(self._agent_stack)
    return page

def _on_agent_configured(self, config: dict):
    from Agent.agent_chat import AgentChatWidget
    from Agent.api_client import AgentApiClient

    client = AgentApiClient(
        base_url=config["base_url"],
        api_key=config.get("api_key", ""),
        model=config["model"],
        deploy_manager=self._deploy_manager,
    )
    self._agent_chat = AgentChatWidget(client)
    self._agent_stack.addWidget(self._agent_chat)  # index 1
    self._agent_stack.setCurrentIndex(1)
```

### 3.3 向导 `Agent/agent_wizard.py`

**AgentWizard** 继承 `QWidget`，内部使用 `QStackedWidget` 分 3 步：

**步骤一：服务地址**
- `QLineEdit` placeholder `"http://localhost:11434"`
- 下方两个快捷按钮：`[使用本地部署]` `[使用 Ollama]`
  - "使用本地部署" → 自动填充 `http://127.0.0.1:{deploy_port}`
  - "使用 Ollama" → 自动填充 `http://localhost:11434`
- `[下一步]` 按钮 → 校验 URL 非空 → 切换到步骤二

**步骤二：API 密钥（可选）**
- `QLineEdit` 设置 `echoMode(QLineEdit.EchoMode.Password)` 密文显示
- 眼睛图标切换明文/密文（可选）
- `[跳过]` 按钮跳过密钥
- `[下一步]` 按钮 → 切换到步骤三

**步骤三：模型名称**
- `QLineEdit` placeholder `"llama3"` 或 `"gpt-4o-mini"`
- 从 API 获取模型列表按钮（可选，调用 `/v1/models`）
- `[开始对话]` 按钮 → 调用回调 `on_configured(config_dict)`

**向导样式**: 纯白背景，居中卡片式布局（max-width 480px），每步标题 + 输入 + 导航按钮。

### 3.4 Agent 聊天 `Agent/agent_chat.py`

**AgentChatWidget** 继承 `QWidget`，纯原生组件，无 WebView。

**布局**:
```
┌──────────────────────────────────────────────┐
│ Agent 对话                          [清除]   │
├──────────────────────────────────────────────┤
│                                              │
│  QScrollArea (消息列表)                       │
│  ┌──────────────────────────────────────────┐│
│  │ [User] 帮我分析这段代码                   ││
│  ├──────────────────────────────────────────┤│
│  │ [Agent] 我需要先读取文件...               ││
│  │ 📄 read_file: main.py (54 lines)         ││
│  │ 分析结果：该文件包含...                   ││
│  └──────────────────────────────────────────┘│
│                                              │
├──────────────────────────────────────────────┤
│ [📎 选择文件] [▶ 允许执行命令]                │
│ ┌──────────────────────────────────────────┐ │
│ │ 输入消息...                     [发送 →] │ │
│ └──────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

**消息气泡**:
- 用户消息: 右对齐，蓝色背景 `#3b82f6`，白色文字
- Agent 消息: 左对齐，白色背景 `#ffffff`，灰色边框，深色文字
- 工具调用: 左对齐，缩进，灰色底 `#f1f5f9`，带图标前缀（📄 文件 / ⚡ 命令）
- 工具结果: 左对齐，缩进，代码块风格，等宽字体

**输入区**:
- `QTextEdit` 多行输入（2-3 行高度自适应）
- `QPushButton` 发送按钮（蓝色实色）
- Enter 发送，Shift+Enter 换行

**文件选择**:
- `QPushButton "📎 选择文件"` → `QFileDialog.getOpenFileName()`
- 读取文件内容 → 注入当前消息上下文
- 文件内容在消息中以引用块显示

**命令执行**:
- `QCheckBox "允许执行命令"`（默认关闭，每次对话需手动开启作为安全确认）
- Agent 返回命令执行请求时：
  - 弹出 `QMessageBox` 显示完整命令 + "是否执行？"
  - 用户确认 → `subprocess.run()` 执行 → 结果回显 + 发送给模型
  - 用户拒绝 → 告知模型"用户拒绝执行该命令"

### 3.5 API 客户端 `Agent/api_client.py`

**AgentApiClient** 类:

```python
class AgentApiClient:
    def __init__(self, base_url: str, api_key: str, model: str, deploy_manager=None):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._deploy_manager = deploy_manager  # 用于判断本地是否就绪

    def chat(self, messages: list[dict], tools: list[dict] = None) -> str:
        """发送聊天请求，返回模型文本响应"""
        ...

    def chat_stream(self, messages: list[dict], tools: list[dict] = None):
        """流式聊天，生成器返回 token"""
        ...
```

**API 调用逻辑**:
1. 构建 OpenAI 兼容请求体 `POST {base_url}/v1/chat/completions`
2. 如果 `base_url` 使用本地部署端口且 `deploy_manager` 存在 → 验证部署状态
3. 流式模式：`stream=True`，逐 token 返回
4. 错误处理：连接失败、超时、模型不存在等友好提示

### 3.6 工具执行器 `Agent/tool_executor.py`

**ToolExecutor** 类:

```python
class ToolExecutor:
    def __init__(self, parent_widget=None):
        self._parent = parent_widget
        self._workspace = Path.cwd()

    def execute_tool(self, tool_name: str, params: dict) -> str:
        if tool_name == "read_file":
            return self._read_file(params["path"])
        elif tool_name == "write_file":
            return self._write_file(params["path"], params["content"])
        elif tool_name == "execute_command":
            return self._execute_command(params["command"])
        ...

    def _read_file(self, path: str) -> str: ...
    def _write_file(self, path: str, content: str) -> str: ...
    def _execute_command(self, command: str) -> str: ...
```

**命令执行安全措施**:
- 执行前弹出 `QMessageBox` 确认
- 命令在工作目录下执行
- 超时限制 60 秒
- 输出截断至 8000 字符
- 危险命令提示（`rm -rf`, `format`, `del /f` 等）

### 3.7 提示词注入方案 `Agent/system_prompts.py`

参考 Cline 设计，构建 tool-aware system prompt：

```
你是一个 AI 编程助手，可以访问以下工具：

1. read_file(path: str) - 读取指定文件内容
2. write_file(path: str, content: str) - 写入文件
3. execute_command(command: str) - 执行系统命令并返回输出

使用工具时，以以下格式输出工具调用：
<tool_call>
<name>工具名</name>
<params>
{ "param": "value" }
</params>
</tool_call>

用户消息后，你可以直接回复文本，或使用工具完成任务。
```

消息构建流程：
1. System: 工具描述 prompt
2. User: 用户输入 + 附加上下文（如文件内容）
3. Assistant: 模型回复（可能包含 `<tool_call>` 标签）
4. Tool: 工具执行结果
5. Assistant: 模型继续回复

循环直到不再有工具调用，或达到最大轮次（10 轮）。

### 3.8 Agent 页面集成回 llama.py

`_build_agent_page()` 方法（放在 `_build_chat_page` 后），约 30 行：
- 创建 `QStackedWidget`
- 添加 `AgentWizard` + `AgentChatWidget`
- `_on_agent_configured` 回调切换视图

---

## 四、文件改动清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `llama.py` | 修改 | 窗口固定尺寸、全局白底、侧边栏重构（4 按钮 + hover 联动）、部署页/聊天页/设置页样式重写、`_switch_page` 4 按钮互斥、`_build_agent_page` 入口、`eventFilter` |
| `llama.py` - `AppSettings` | 修改 | 新增 `enable_mmproj_default` 字段 |
| `llama.py` - `_build_settings_page` | 修改 | 新增视觉模型开关、样式重写 |
| `llama.py` - `_restore_defaults` | 修改 | 新增视觉模型开关的恢复 |
| `llama.py` - `_scan_models` | 修改 | 根据设置自动勾选视觉模型 |
| `Agent/__init__.py` | 新建 | 空模块文件 |
| `Agent/agent_wizard.py` | 新建 | 三步向导（~150 行） |
| `Agent/agent_chat.py` | 新建 | 原生聊天界面（~300 行） |
| `Agent/api_client.py` | 新建 | API 客户端（~80 行） |
| `Agent/tool_executor.py` | 新建 | 工具执行（~120 行） |
| `Agent/system_prompts.py` | 新建 | 提示词模板（~60 行） |

---

## 五、实现顺序

1. **Agent/ 目录 + 模块骨架**: 先建立文件结构，确保 import 不报错
2. **全局 UI 重构**: 窗口、侧边栏、白底、按钮联动（影响面最大，优先完成）
3. **部署页 + 聊天页样式适配**: 在全局白底基础上调整各页面
4. **设置模块补全**: 视觉模型开关 + 联动
5. **Agent API 客户端**: 独立可测
6. **Agent 工具执行器**: 独立可测
7. **Agent 向导**: 三步流程
8. **Agent 聊天界面**: 消息气泡 + 流式 + 工具循环
9. **集成测试**: 确保原有功能不受影响

## 六、风险与约束

- **WebView 保留**: 聊天页的 `QWebEngineView` 不动，Agent 聊天用原生组件，两者独立
- **原有功能禁改**: 部署逻辑、模型扫描、bat 生成、Ollama API、closeEvent、_cleanup 等不动
- **Agent 模块独立**: 所有新代码在 `Agent/` 下，llama.py 仅增加入口方法和 import
- **eventFilter 重写**: QtApp 需重写 `eventFilter`，注意与现有事件处理不冲突
