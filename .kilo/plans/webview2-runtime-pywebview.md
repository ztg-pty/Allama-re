# WebView2 Runtime 下载 + pywebview 双方案

## 背景

三次嵌入尝试均失败：

1. **Edge --app + SetParent** → DirectComposition 渲染管线断裂**
2. **ctypes COM WebView2Host** → COM 回调/VTable bug，无法定位修复

根因：Tkinter 窗口无法可靠承载现代 Chromium 渲染引擎。

## 新方案

放弃嵌入式幻想，采用 **pywebview 独立桌面窗口**（pywebview 内部已正确封装 WebView2 COM，久经测试）。同时增加 **WebView2 Runtime 自动检测/下载**。

```
启动应用
  │
  ├── 检测 WebView2 Runtime（WebView2Loader.dll）
  │     ├── 已安装 → 正常使用
  │     └── 未安装 → 提示下载（Evergreen Bootstrapper ~1.7MB）
  │
部署成功 (3秒延迟)
  │
  ▼
_load_chat_with_fallback()
  │
  ├── WebView2 Runtime 可用 + pywebview 可用?
  │     ├── 是 → pywebview.create_window(url)
  │     │         → webview.start() 在 daemon 线程
  │     │         → 独立桌面窗口显示 llama-ui
  │     │         → 显示 "✅ llama-ui 已打开"
  │     │
  │     └── 否 → webbrowser.open(url)
  │              → 显示 "✅ 已在浏览器打开"
  │
  ├── 用户点 🔄重新加载 → 关闭旧窗口 + 打开新窗口
  ├── 用户点 🌐在浏览器打开 → webbrowser.open()
  └── 停止部署 / 关闭窗口 → webview.destroy()
```

## 实现细节

### 1. WebView2 Runtime 检测

```python
def _find_webview2_runtime():
    """检测 WebView2 Evergreen Runtime 是否已安装"""
    paths = [
        os.path.expandvars("%LOCALAPPDATA%\\Microsoft\\EdgeWebView\\Application"),
        "C:\\Program Files (x86)\\Microsoft\\EdgeWebView\\Application",
    ]
    for base in paths:
        if os.path.isdir(base):
            for d in sorted(glob.glob(os.path.join(base, "*")), reverse=True):
                dll = os.path.join(d, "WebView2Loader.dll")
                if os.path.isfile(dll):
                    return True
    return False
```

### 2. WebView2 Runtime 下载

```python
_EVERGREEN_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"

def _download_webview2_runtime(progress_callback=None):
    """下载 WebView2 Evergreen Bootstrapper (~1.7MB)"""
    import urllib.request
    tmp = os.path.join(BASE_DIR, "MicrosoftEdgeWebview2Setup.exe")
    urllib.request.urlretrieve(_EVERGREEN_URL, tmp, reporthook=progress_callback)
    return tmp

def _install_webview2_runtime(setup_path):
    """静默安装 WebView2 Runtime"""
    subprocess.run([setup_path, "/silent", "/install"], check=True)
    os.remove(setup_path)
```

### 3. 聊天标签页 UI 调整

```python
def _build_chat_tab(self, w, parent):
    # ... header with reload button, browser button ...
    
    # 嵌入区域改为信息面板
    info_frame = w.CTkFrame(chat_frame, ...)
    info_frame.pack(fill="both", expand=True, padx=12, pady=4)
    
    # WebView2 状态
    self._wv_status_label = w.CTkLabel(info_frame, text="检测 WebView2 Runtime...")
    self._wv_status_label.pack(pady=(40, 5))
    
    # 下载按钮（如果 Runtime 缺失）
    self._wv_download_btn = w.CTkButton(info_frame, text="📥 下载 WebView2 Runtime",
                                         command=self._download_webview2,
                                         state="disabled")
    self._wv_download_btn.pack(pady=5)
    
    # 下载进度条
    self._wv_progress = w.CTkProgressBar(info_frame, width=300)
    self._wv_progress.pack(pady=10)
    self._wv_progress.set(0)
    
    # llama-ui 说明
    ...
```

### 4. pywebview 封装（替换 WebView2Host）

```python
class _PyWebViewBridge:
    def __init__(self):
        self._window = None
        self._url = ""
    
    def open(self, url):
        import webview
        self.close()
        self._url = url
        self._window = webview.create_window(
            "llama-ui - 聊天对话", url,
            width=1200, height=800,
            confirm_close=False
        )
        threading.Thread(target=webview.start, daemon=True).start()
    
    def reload(self):
        if self._url:
            self.open(self._url)
    
    def close(self):
        if self._window:
            try:
                self._window.destroy()
            except Exception:
                pass
            self._window = None
    
    @property
    def is_running(self):
        return self._window is not None
```

## 需要变更的文件

| 文件 | 变更 | 行数变化 |
|------|------|----------|
| `requirements.txt` | 添加 `pywebview>=5.0` | +1 |
| `main.py` | 依赖列表添加 `pywebview` | 1 行改 |
| `llama.py` 706-960 | **删除** WebView2Host COM 全部代码 (~250行) | -250 |
| `llama.py` 新增 | **添加** Runtime 检测/下载逻辑 (~30行) | +30 |
| `llama.py` 新增 | **添加** `_PyWebViewBridge` 类 (~30行) | +30 |
| `llama.py` 1010-1060 | **修改** `_build_chat_tab` — 嵌入区→信息面板 | ~20行改 |
| `llama.py` 1320-1360 | **修改** `_launch_embed`→`_open_llama_ui` 使用 pywebview | ~15行改 |
| `llama.py` 1330-1350 | **修改** `_stop/_on_closing` 调用 pywebview.destroy() | ~5行改 |

**净变化**：~1557 行 → ~1370 行（删除 200+ COM 代码，增加 80 行 pywebview + Runtime 代码）

## 行为

```
启动应用
  │
  ├── _find_webview2_runtime() → True
  │     ├── 显示 "✅ WebView2 Runtime 已安装"
  │     └── 下载按钮隐藏
  │
  └── _find_webview2_runtime() → False
        ├── 显示 "⚠ WebView2 Runtime 未安装"
        └── 下载按钮启用

点击"启动部署" → 成功
  │
  ▼ (3秒后)
_open_llama_ui()
  │
  ├── WebView2 Runtime 已安装?
  │     ├── pywebview 可用?
  │     │     ├── 是 → pywebview 独立窗口打开 llama-ui
  │     │     │        显示 "✅ llama-ui 已打开"
  │     │     └── 否 → webbrowser.open()
  │     │              → "✅ 已在浏览器打开"
  │     │
  │     └── 未安装 → webbrowser.open()
  │                 → "⚠ 请先安装 WebView2 Runtime"
  │
  ├── 🔄重新加载 → 关闭旧窗口 + 打开新窗口
  ├── 🌐在浏览器打开 → 强制 webbrowser.open()
  └── 停止部署 → pywebview.destroy() → 恢复提示面板
```

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| pywebview 未安装 | `requirements.txt` 自动安装；运行时 `import webview` 失败 → fallback webbrowser |
| WebView2 Runtime 未安装 | 启动时检测 + 提示下载按钮；手动安装后刷新 |
| pywebview + CTkinter 主线程冲突 | `webview.start()` 运行在 daemon 线程；主线程 `CTk.mainloop()` 不受影响 |
| 用户关闭 pywebview 窗口后状态不同步 | `open()` 时先 `close()` 旧窗口；`_on_closing` 时主动 destroy |

## Todo

- [ ] 删除 llama.py 中 WebView2Host 全部 ctypes COM 代码 (~706-960)
- [ ] 新增 `_find_webview2_runtime()` 检测函数
- [ ] 新增 `_download_webview2_runtime()` + 进度回调
- [ ] 新增 `_install_webview2()` 静默安装
- [ ] 新增 `_PyWebViewBridge` 类（open/reload/close/is_running）
- [ ] 修改 `_build_chat_tab` — 嵌入区→信息面板（Runtime 状态、下载按钮、进度条）
- [ ] 修改 `_open_llama_ui`（原 `_launch_embed`）— 使用 pywebview
- [ ] 修改 `_reload_chat` / `_on_closing` / `_stop_deployment` — 适配新 API
- [ ] 更新 `requirements.txt` — 添加 `pywebview`
- [ ] 更新 `main.py` — 添加 `pywebview` 到依赖检查
- [ ] 测试：WebView2 已安装 + pywebview 可用 → 窗口打开
- [ ] 测试：pywebview 未安装 → 浏览器 fallback
- [ ] 测试：WebView2 未安装 → 下载流程
- [ ] 测试：重新加载 + 停止部署清理
