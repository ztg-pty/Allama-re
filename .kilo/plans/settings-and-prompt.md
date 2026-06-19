# 设置选项 & 提示词编辑器

## 概述

在现有 "模型部署" / "聊天对话" 双页基础上新增第 3 页 "设置"，包含：
- 模型默认上下文大小持久化（替换硬编码 `8192`）
- 关闭程序时是否自动退出模型服务
- 系统提示词编辑器（保存为 `.md` 文件，可被 llama-server `--system-prompt-file` 引用）

## 新增 Sidebar 按钮

```
sidebar: [模型部署] [聊天对话] [⚙ 设置]
```

设置页作为 QStackedWidget 的第 3 页（索引 2）。

## 设置页 UI 布局

```
┌─────────────────────────────────────────────┐
│ 设置                                        │
│                                             │
│ 模型默认参数                                │
│ ┌─────────────────────────────────────────┐ │
│ │ 上下文窗口 (-c)       [8192        ]    │ │
│ │ GPU 层数 (-ngl)       [999         ]    │ │
│ │ 最大输出 (-n)          [4096        ]    │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ 行为设置                                    │
│ ┌─────────────────────────────────────────┐ │
│ │ [✓] 关闭程序时自动退出模型服务          │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ 系统提示词                                  │
│ ┌─────────────────────────────────────────┐ │
│ │ ┌─────────────────────────────────────┐ │ │
│ │ │ (QPlainTextEdit, 多行编辑)          │ │ │
│ │ │                                     │ │ │
│ │ └─────────────────────────────────────┘ │ │
│ │ [保存提示词到 .md]                      │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ [恢复默认值]                                │
└─────────────────────────────────────────────┘
```

## 持久化方案

设置保存到 `EXE_DIR / "settings.json"`（打包后 `dist/Allama/settings.json`，开发模式 `项目根目录/settings.json`）。

```json
{
  "default_context": "8192",
  "default_ngl": "999",
  "default_n_predict": "4096",
  "stop_model_on_exit": true,
  "system_prompt": ""
}
```

- 加载：`AppSettings` 类在 `QtApp.__init__()` 中实例化，从 JSON 读取
- 保存：设置变更时调用 `save()`，写入 JSON
- 懒加载：仅首次读，后续走内存

## 代码改动点

### 1. 新增 `AppSettings` 类（llama.py 常量区后）

```python
class AppSettings:
    _FILE = _EXE_DIR / "settings.json"
    _DEFAULTS = {
        "default_context": "8192",
        "default_ngl": "999",
        "default_n_predict": "4096",
        "stop_model_on_exit": True,
        "system_prompt": "",
    }

    def __init__(self):
        self._data = dict(self._DEFAULTS)
        self.load()

    def load(self):
        if self._FILE.exists():
            try:
                with open(self._FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self._data.update(loaded)
            except Exception:
                pass

    def save(self):
        try:
            with open(self._FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get(self, key):
        return self._data.get(key, self._DEFAULTS.get(key))

    def set(self, key, value):
        self._data[key] = value
        self.save()
```

### 2. 修改 `QtApp.__init__()`（~line 755）

```python
# 在 _init_ui() 前加入
self._settings = AppSettings()
```

### 3. 新增 `_build_settings_page()` 方法

在 `_build_chat_page()` 后（~line 997）添加。构建 QWidget：
- 3 个 QLineEdit 对应 `-c` / `-ngl` / `-n`
- 1 个 QCheckBox 对应 `stop_model_on_exit`
- 1 个 QPlainTextEdit 对应系统提示词
- "保存提示词到 .md" 按钮
- "恢复默认值" 按钮
- 所有控件初始值从 `self._settings` 读取
- 控件变更自动调用 `self._settings.set(...)` 持久化

### 4. 修改 `_init_ui()` 注册设置页

```python
self._stack.addWidget(self._build_settings_page())  # 索引 2
```

### 5. 新增 sidebar 按钮 `_btn_settings`

与 `_btn_deploy`、`_btn_chat` 同级，`clicked.connect(lambda: self._switch_page(2))`。

### 6. 修改 `_switch_page()`

```python
def _switch_page(self, index: int):
    self._stack.setCurrentIndex(index)
    self._btn_deploy.setChecked(index == 0)
    self._btn_chat.setChecked(index == 1)
    self._btn_settings.setChecked(index == 2)
```

### 7. 修改 `_on_model_select_internal()`（~line 1056）

将硬编码默认值改为从 `self._settings` 读取：

```python
# 改前:
self._param_edits["-c"].setText(str(default_params.get("-c", "8192")))
self._param_edits["-ngl"].setText("999")
self._param_edits["-n"].setText(str(default_params.get("-n", "4096")))

# 改后:
self._param_edits["-c"].setText(str(default_params.get("-c", self._settings.get("default_context"))))
self._param_edits["-ngl"].setText(self._settings.get("default_ngl"))
self._param_edits["-n"].setText(str(default_params.get("-n", self._settings.get("default_n_predict"))))
```

### 8. 修改 `closeEvent()`（~line 1253）

```python
def closeEvent(self, event):
    if self._settings.get("stop_model_on_exit"):
        if self._deploy_manager:
            self._deploy_manager.stop()
        if self._ollama_api:
            self._ollama_api.stop()
    event.accept()
```

### 9. 修改 `_cleanup()`（~line 1260）

同样检查 `stop_model_on_exit`。如果为 False，跳过 kill 和 cleanup：
```python
def _cleanup(self):
    if not self._settings.get("stop_model_on_exit"):
        return
    # ... 原有逻辑
```

### 10. 提示词保存

"保存提示词到 .md" 按钮点击：
- 从 QPlainTextEdit 获取文本
- 使用 `QFileDialog.getSaveFileName()` 选择保存路径（默认 `MODELS_DIR / "system_prompt.md"`）
- 直接写入 UTF-8 文本

注：提示词内容也通过 `self._settings.set("system_prompt", text)` 持久化到 settings.json，下次打开设置页自动回填。

## 文件清单

| 文件 | 改动 |
|------|------|
| `llama.py` | 新增 `AppSettings` 类 (~30行)，新增 `_build_settings_page()` (~80行)，修改 `__init__`/`_init_ui`/`_switch_page`/`_on_model_select_internal`/`closeEvent`/`_cleanup` |
| `Allama.spec` | 无需改动（settings.json 是运行时产物） |

## 注意事项

- `_EXE_DIR` 在开发模式 = `Path(__file__).parent`（项目根），settings.json 写到这里不会进入 git（已在 .gitignore 或手动排除）
- 面板残骸：`closeEvent` 跳过 kill 后，llama-server 进程继续运行；用户下次启动程序可重新连接（端口不变，需额外实现，暂不纳入本次范围——先做基础开关）
- 提示词编辑器内容自动同步到 settings.json，无需额外 .md 持久化读取（用户手动保存 .md 仅为分发/备份用）
