# PyInstaller EXE 打包方案

## 背景

将 Allama (PySide6 + QWebEngineView) 打包为 Windows EXE，连同 llama-server.exe、依赖 DLL、bat 模板一起分发。模型文件 (.gguf) 不打包，由用户自行放入 `RunTime/models/`。

## 核心挑战

| 问题 | 说明 |
|------|------|
| QWebEngineView 的 Chromium 引擎 | ~120MB Qt 资源文件需完整收集 |
| `__file__` 在冻结后指向只读临时目录 | 需区分「捆绑资源路径」(只读) 和「工作目录路径」(可写) |
| llama-server.exe + 几十个 DLL | 需作为 binary 打包到 RunTime 子目录 |
| 模型文件 60+ GB | 不打包，用户手动放置 |

## 选型

**PyInstaller `--onedir`（文件夹分发）**，不用 `--onefile`：

| | --onedir | --onefile |
|---|---|---|
| 启动速度 | 快 | 每次解压 ~120MB 到临时目录，慢 |
| 杀软误报 | 低 | 高（自解压 EXE 特征明显） |
| QWebEngineView | 正常 | Chromium 进程路径可能异常 |
| 调试 | 容易 | 困难 |

## 文件结构设计

```
dist/Allama/                          # 打包输出目录
├── Allama.exe                         # 入口（等同于 python main.py）
├── *.dll / *.pyd                     # Python + Qt 运行时
├── PySide6/                          # Qt 库（自动收集）
├── RunTime/                          # 捆绑的 llama 运行时（只读，来自 sys._MEIPASS）
│   ├── llama-server.exe
│   ├── llama.dll, ggml.dll, ggml-cuda.dll, ...
│   ├── *.dll（所有 cublas/cudart/ggml-* 共 30+ 文件）
│   └── 越狱版模型启动器.bat           # bat 模板（只读）
└── RunTime/models/                   # ← 用户自行创建并放入 .gguf 文件

用户分发步骤:
  1. 解压 dist/Allama.zip
  2. 在 RunTime/ 下创建 models/ 文件夹
  3. 将 .gguf 模型文件放入 models/
  4. 双击 Allama.exe
```

## 代码改动：冻结路径解析

`llama.py` 顶部常量区需加入冻结检测（~20 行改动，不影响开发模式）：

```python
# === 冻结路径解析 ===
_FROZEN = getattr(sys, 'frozen', False)
if _FROZEN:
    _BUNDLE_DIR = Path(sys._MEIPASS)          # 只读，PyInstaller 解压目录
    _EXE_DIR = Path(sys.executable).parent    # 可写，EXE 所在目录
else:
    _BUNDLE_DIR = BASE_DIR
    _EXE_DIR = BASE_DIR

# 只读资源 → 从 bundle 读取
BAT_TEMPLATE = _BUNDLE_DIR / "RunTime" / "越狱版模型启动器.bat"
LLAMA_SERVER_EXE = _BUNDLE_DIR / "RunTime" / "llama-server.exe"

# 可写目录 → 用 EXE 所在目录
TEMP_BAT_DIR = _EXE_DIR / "RunTime"
MODELS_DIR = _EXE_DIR / "RunTime" / "models"
```

**注意**：
- `DeploymentManager.start()` 用 `cwd=bat_dir` 执行 bat，bat 内 `cd /d "%~dp0"` 会切到 TEMP_BAT_DIR。由于 llama-server.exe 也在同一目录，相对路径仍有效。
- `TempBatGenerator._to_relative()` 尝试用 `Path.relative_to(TEMP_BAT_DIR)` 计算相对路径，当 EXE 和 DLL 都在同一 RunTime 目录时，相对路径能正确计算出类似 `llama-server.exe` 的简短路径。
- 但开发模式下 `_BUNDLE_DIR == _EXE_DIR`，所以 TEMP_BAT_DIR 指向 `BASE_DIR / "RunTime"`，模型文件和 llama-server.exe 都在那里。打包后 `_EXE_DIR` 指向 `dist/Allama/`，模型文件需要在 `dist/Allama/RunTime/models/`。

**潜在问题**：`TempBatGenerator._to_relative()` 试图将 llama-server.exe 的路径转为相对于 TEMP_BAT_DIR 的相对路径。打包后：
- llama-server.exe 在 `_BUNDLE_DIR / "RunTime" / "llama-server.exe"`（只读 bundle 中）
- TEMP_BAT_DIR = `_EXE_DIR / "RunTime"`（可写，EXE 目录下）
- 如果 `_BUNDLE_DIR != _EXE_DIR`，两处都有 `RunTime/`，相对路径计算会有问题

**解决方案**：在冻结模式下，将 bundle 中的 llama-server.exe 和相关 DLL 复制到 `_EXE_DIR / "RunTime"`（可写），或者把 `TEMP_BAT_DIR` 改为直接指向 `_BUNDLE_DIR / "RunTime"` + 确保它是可写的... 但实际上 `_BUNDLE_DIR` 在 `--onedir` 模式下就是 `_EXE_DIR`！PyInstaller `--onedir` 不会解压到临时目录——EXE 直接在 `dist/Allama/` 运行，`sys._MEIPASS` 指向 `dist/Allama/`。

**重要发现**：PyInstaller `--onedir` 模式下，`sys._MEIPASS == Path(sys.executable).parent`，即 `_BUNDLE_DIR == _EXE_DIR`。Read-only 不适用。但 `llama-server.exe` 等文件是 Analysis 中声明的 binaries，会被复制到 EXE 同级的 `RunTime/` 目录。

所以最简单的方案：
- 开发模式：所有文件在 `BASE_DIR / "RunTime"/` 下
- 打包后：所有文件在 `dist/Allama/RunTime/` 下
- `BASE_DIR` 改为 `Path(sys._MEIPASS) if frozen else Path(__file__).parent`
- 其余常量不变

```python
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent
```

**但这不够**：用户需要在 `RunTime/models/` 放模型文件。打包后 `RunTime/` 可能在 `dist/Allama/RunTime/`——用户可写。只需确保初始创建 `models/` 目录即可。

## PyInstaller 配置

### 安装

```bash
pip install pyinstaller
```

### Spec 文件：`Allama.spec`

```python
# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

PROJECT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))

# 收集 RunTime 下所有 dll 和 exe（排除 models/ 子目录）
runtime_dir = PROJECT_DIR / "RunTime"
binaries = []
for f in runtime_dir.glob("*"):
    if f.is_file() and f.suffix.lower() in ('.dll', '.exe'):
        binaries.append((str(f), 'RunTime'))

datas = [
    (str(runtime_dir / "越狱版模型启动器.bat"), "RunTime"),
]

a = Analysis(
    ['main.py'],
    pathex=[str(PROJECT_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngine',
        'PySide6.QtWebChannel',
        'PySide6.QtPrintSupport',
        'PySide6.QtQuick',
        'PySide6.QtQuickWidgets',
        'psutil',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'customtkinter',
        'pywebview',
        'PyQt5',
        'PyQt6',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Allama',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # ← 无控制台窗口（GUI 应用）
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # 可指定 .ico 文件
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Allama',
)
```

### 构建命令

```bash
pyinstaller --clean Allama.spec
```

输出在 `dist/Allama/`，包含：
- `Allama.exe`（主程序）
- `RunTime/`（llama-server.exe + DLL + bat 模板）
- `PySide6/`（Qt 库，自动收集）
- `_internal/` 或分散的 .pyd/.dll

### 测试

```bash
# 确保 models 目录存在
mkdir dist\Allama\RunTime\models
# 复制一个小模型测试
copy RunTime\models\*.gguf dist\Allama\RunTime\models\
# 运行
dist\Allama\Allama.exe
```

## 流程概览

```
1. pip install pyinstaller
2. 创建 Allama.spec
3. 修改 llama.py 中的 BASE_DIR（加入 frozen 检测）
4. pyinstaller --clean Allama.spec
5. 创建 dist/Allama/RunTime/models/ → 放入 .gguf
6. 分发 dist/Allama/ 整个目录（压缩为 zip）
```

## 预估大小

| 组件 | 大小 |
|------|------|
| Python + psutil | ~30 MB |
| PySide6 + QWebEngineView (Chromium) | ~130 MB |
| llama-server.exe + DLLs | ~200 MB |
| **分发目录合计** | **~360 MB**（不含模型） |

模型文件单独由用户放入 `RunTime/models/`。

## 注意事项

- `--onedir` 下 `sys._MEIPASS` 指向 EXE 所在目录，非临时目录，所以 `RunTime/` 可写
- QWebEngineView 需要 `QtWebEngineProcess.exe`（PyInstaller 会自动收集到 `PySide6/Qt/` 下）
- 首次运行时如 `RunTime/models/` 不存在，`ModelScanner.scan_text_models()` 返回空列表（不会报错）
- 打包时排除 `web/` 目录（WebView2 Runtime 源码残留，已不需要）
- 建议用 `--clean` 清除上次构建缓存，避免 Qt 插件残留
