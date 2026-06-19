# WebView2 COM 原生嵌入方案

## 背景

当前 `_EmbeddedBrowser` 使用 `subprocess` 启动 Edge `--app` 模式 + `SetParent` 重父窗口化，但 **总是失败**。根因：

1. **DirectComposition 渲染管线断裂** — 现代 Chromium/Edge 使用 DirectComposition 硬件加速渲染，`SetParent` 会断开渲染管线与合成器的连接，导致空白/黑窗口。这是 Chromium 已知限制。
2. **PID 匹配不可靠** — Edge 多进程架构下，`Popen.pid` 可能与实际窗口所属进程不一致。

## 解决方案

使用 **WebView2 COM API**（`WebView2Loader.dll` + ctypes），直接以目标 HWND 为父窗口创建 WebView2 控制器。从创建之初就是正确的父子关系，无需重父窗口化。

```
Tkinter (CTkinter)
  └── CTkFrame (_embed_frame)
        └── HWND (frame.winfo_id())
              └── ICoreWebView2Controller  ← COM 创建时指定此 HWND 为父
                    └── ICoreWebView2
                          ├── Navigate(url)
                          ├── Reload()
                          └── [渲染 llama-ui 在此]
```

## 实现细节

### 1. WebView2Loader.dll 查找

按优先级搜索：

1. `%LOCALAPPDATA%\Microsoft\EdgeWebView\Application\{version}\` — Evergreen Runtime（Windows 10+ 默认安装）
2. `C:\Program Files (x86)\Microsoft\EdgeWebView\Application\{version}\` — 系统级安装
3. `{exe_dir}\WebView2Loader.dll` — 本地打包（可选，约 1.5MB）

### 2. COM 接口定义（ctypes）

需要定义 5 个核心 COM 接口，每个方法通过 VTable 索引调用：

| VTable Index | 接口 | 方法 |
|---|---|---|
| IUnknown(0-2) | All | QueryInterface, AddRef, Release |
| 3 | ICoreWebView2Environment | CreateCoreWebView2Controller |
| 3 | ICoreWebView2Controller | get_CoreWebView2 |
| 4 | ICoreWebView2Controller | put_IsVisible |
| 5 | ICoreWebView2Controller | put_Bounds |
| 6 | ICoreWebView2Controller | Close |
| 5 | ICoreWebView2 | Navigate |
| 7 | ICoreWebView2 | Reload |
| 9 | ICoreWebView2 | add_NavigationCompleted |
| 23 | ICoreWebView2 | add_WebResourceRequested |

回调接口（继承 IUnknown + IUnknown(3 methods) + Invoke = 共 4 方法）：

| 接口 | VTable Index 3 方法 |
|---|---|
| ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler | Invoke(hr, env) |
| ICoreWebView2CreateCoreWebView2ControllerCompletedHandler | Invoke(hr, controller) |

使用统一辅助函数避免逐个定义 VTable 结构体：

```python
def _com_call(this_ptr, vtable_idx, argtypes, restype=ctypes.HRESULT, *args):
    vtable = ctypes.cast(this_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))
    func_ptr = vtable[0][vtable_idx]
    func = ctypes.WINFUNCTYPE(restype, *argtypes)(func_ptr)
    return func(this_ptr, *args)
```

### 3. WebView2Host 类

```python
class WebView2Host:
    def __init__(self, parent_widget):
        self._parent = parent_widget     # CTkFrame
        self._env = None                  # ICoreWebView2Environment
        self._controller = None           # ICoreWebView2Controller
        self._webview = None              # ICoreWebView2
        self._ready = False
        self._url = ""
        self._resize_job = None

    @classmethod
    def is_available(cls) -> bool:
        """检查 WebView2 Runtime 是否可用"""
        ...

    def create(self, url: str) -> bool:
        """异步创建环境 + 控制器，同步等待完成（最多 10 秒）"""
        # 1. 加载 WebView2Loader.dll
        # 2. CreateCoreWebView2EnvironmentWithOptions(...)
        #    → 回调 _on_env_created(hr, env)
        # 3. _on_env_created: env.CreateCoreWebView2Controller(parent_hwnd, cb)
        #    → 回调 _on_ctrl_created(hr, controller)
        # 4. _on_ctrl_created:
        #    controller.get_CoreWebView2() → webview
        #    webview.Navigate(url)
        #    启动 resize poll
        #    标记 ready
        ...

    def navigate(self, url: str):
        ...

    def reload(self):
        ...

    def resize(self, width, height):
        ...

    def destroy(self):
        # controller.Close(), 取消 resize poll
        ...
```

### 4. 异步变同步

WebView2 创建是异步的（回调模式），但 Tkinter 是单线程。使用以下模式使其同步：

```python
def create(self, url):
    self._create_env(url)     # 发起异步创建
    deadline = time.time() + 10
    while not self._ready and time.time() < deadline:
        # 泵送 Tkinter 消息，让回调在主线程执行
        if self._parent.winfo_exists():
            self._parent.update()
        time.sleep(0.05)
    return self._ready
```

### 5. 回调对象的 ctypes 实现

COM 回调需要返回实现特定接口的 Python 对象。使用 ctypes 创建 IUnknown VTable + 回调函数的 C 函数指针：

```python
def _make_env_handler(on_invoke):
    """创建 ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler"""
    # 构建 VTable (IUnknown 3 方法 + Invoke 1 方法)
    vtable = (ctypes.c_void_p * 4)()
    # 填充 QueryInterface, AddRef, Release, Invoke
    ...
    # 返回 ctypes 对象指针
```

### 6. Resize 处理

```python
def _poll_resize(self):
    if not self._ready:
        return
    if self._parent.winfo_exists():
        w = self._parent.winfo_width()
        h = self._parent.winfo_height()
        if w > 1 and h > 1:
            # controller.put_Bounds(0, 0, w, h)
            self._set_bounds(w, h)
    self._resize_job = self._parent.after(500, self._poll_resize)
```

## 需要变更的文件

| 文件 | 行数 | 变更 |
|------|------|------|
| `llama.py` | ~700-830 | **替换** `_EmbeddedBrowser` (120行) → `WebView2Host` (~250行) |
| `llama.py` | ~1320-1355 | **修改** `_launch_embed`/`_reload_chat` 对接 `WebView2Host` API |
| `llama.py` | ~1363-1365 | **修改** `_on_closing` 调用 `WebView2Host.destroy()` |
| `requirements.txt` | — | **无变更**（纯 ctypes + Windows API，零外部依赖） |

### 不变的部分

- `_build_chat_tab` 的 UI 布局（`_embed_frame`, `_fallback_frame`, `_reload_btn`, `_open_chat_btn`）完全不变
- 部署标签的所有逻辑不变
- `_scan_models`, `_build_deploy_tab`, `DeploymentManager`, `ApiServer` 等全部不变

## 行为

```
启动部署成功
    │
    ▼ (3秒后)
_load_chat_with_fallback()
    │
    ├── WebView2Host.is_available()?
    │     ├── 是 → WebView2Host.create(url)
    │     │         → 如果 WebView2 加载成功:
    │     │             隐藏 _fallback_frame
    │     │             llama-ui 覆盖整个 _embed_frame
    │     │             显示 "✅ llama-ui 已嵌入"
    │     │
    │     └── 否 → _open_in_browser()
    │              → webbrowser.open(url)
    │              → 显示 "✅ 已在浏览器打开"
    │
    ├── 用户点 🔄重新加载 → WebView2Host.reload()
    ├── 用户点 🌐在浏览器打开 → webbrowser.open()
    └── 停止部署 / 关闭窗口 → WebView2Host.destroy()
```

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| WebView2 Runtime 未安装 | `is_available()` 自动检测，fallback 到浏览器 |
| COM 回调中 Tkinter 线程安全 | 回调仅设置标志，主线程 `update()` loop 中轮询 |
| WebView2Loader.dll 版本不匹配 | 多路径搜索，按版本号降序尝试 |
| ctypes COM VTables 定义错误 | 每个 VTable 索引对照 WebView2 C++ SDK 头文件 |

## Todo

- [ ] 实现 `WebView2Host.is_available()` — WebView2Loader.dll 查找
- [ ] 实现 COM VTable 辅助函数 `_com_call()`
- [ ] 实现回调对象工厂（Environment / Controller completion handlers）
- [ ] 实现 `WebView2Host.create()` — 环境 + 控制器创建 + 导航
- [ ] 实现 `WebView2Host` 的 navigate/reload/destroy/resize
- [ ] 替换 `_EmbeddedBrowser` → `WebView2Host`
- [ ] 修改 `_launch_embed` / `_reload_chat` / `_on_closing` 对接新 API
- [ ] 测试：WebView2 可用时嵌入成功
- [ ] 测试：WebView2 不可用时 fallback 浏览器
- [ ] 测试：重新加载按钮功能
- [ ] 测试：停止部署时清理
