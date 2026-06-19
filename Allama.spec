# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

PROJECT_DIR = Path(SPECPATH)

runtime_dir = PROJECT_DIR / "RunTime"
binaries = []
for f in runtime_dir.glob("*"):
    if f.is_file() and f.suffix.lower() in ('.dll', '.exe'):
        binaries.append((str(f), 'RunTime'))

# Add bat files to datas
bat_files = []
for f in runtime_dir.glob("*.bat"):
    bat_files.append((str(f), 'RunTime'))

models_dir = PROJECT_DIR / "models"
datas = [(str(models_dir), 'models')] if models_dir.exists() else []

# Add WebView2 runtime from Web directory
web_dir = PROJECT_DIR / "Web"
if web_dir.exists():
    datas.append((str(web_dir), 'Web'))

a = Analysis(
    ['main.py'],
    pathex=[str(PROJECT_DIR)],
    binaries=binaries,
    datas=datas + bat_files,
    hiddenimports=[
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebChannel',
        'PySide6.QtPrintSupport',
        'psutil',
        'Agent.agent_wizard',
        'Agent.agent_chat',
        'Agent.api_client',
        'Agent.tool_executor',
        'Agent.system_prompts',
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
        'PySide6.QtQuick',
        'PySide6.QtQuickWidgets',
        'PySide6.QtWebEngine',
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
    [],
    exclude_binaries=True,
    name='Allama',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Allama',
)
