# Allama

🖥️ 基于 PySide6 + llama.cpp 的本地大模型推理桌面应用

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D6.svg)](https://www.microsoft.com/windows)
[![PySide6](https://img.shields.io/badge/PySide6-6.5+-green.svg)](https://www.qt.io/)

## ✨ 功能特性

- 🚀 **本地推理** — 基于 llama.cpp，支持 GGUF 格式模型，CUDA 硬件加速
- 🎨 **Qt6 GUI** — PySide6 桌面应用，嵌入 WebView2 聊天界面
- 🤖 **Agent 模式** — 工具调用（Function Calling）自动推理循环，支持文件读写、命令行执行
- 🔄 **Ollama 兼容 API** — 提供 OpenAI 和 Ollama 双协议接口，支持第三方工具集成
- 📦 **一键打包** — PyInstaller 构建，开箱即用的 Windows 分发版
- 🖼️ **多模态支持** — 加载 mmproj 视觉模型，支持图片理解
- ⚙️ **灵活配置** — 上下文窗口、NG-Layer、预测长度等参数可调

## 📂 项目结构

```
allama/
├── main.py                  # 应用入口，依赖检查与初始化
├── llama.py                 # 核心逻辑 (GUI + llama-server 管理)
├── settings.json            # 用户配置（模型路径、参数）
├── requirements.txt         # Python 依赖
├── Allama.spec              # PyInstaller 打包配置
├── Agent/                   # Agent 插件系统
│   ├── agent_chat.py        # Agent 聊天界面
│   ├── agent_wizard.py      # 配置向导 (URL/Key/Model)
│   ├── api_client.py        # OpenAI/Ollama API 客户端
│   ├── tool_executor.py     # 工具执行（文件/命令）
│   ├── system_prompts.py    # 系统提示词模板
│   ├── core/                # Agent 核心
│   │   ├── agent_loop.py    # 推理循环
│   │   ├── context_compaction.py  # 上下文压缩
│   │   └── event_bus.py     # 事件总线
│   ├── plugin/              # 插件系统
│   └── adapter/             # Provider 适配层
├── RunTime/                 # 运行时二进制（llama.cpp + CUDA）
│   ├── llama-server.exe     # 推理服务器
│   ├── *.dll                # llama.cpp CUDA/CPU 后端
│   └── Debug/app.log        # 应用日志
├── Web/                     # WebView2 运行时
├── docs/                    # 文档
└── _runtime/                # 运行时辅助模块（日志等）
```

## 📋 环境要求

- **操作系统**: Windows 10/11 (x64)
- **Python**: 3.12+ (推荐 3.14)
- **显卡**: NVIDIA GPU + CUDA 12+ (可选，CPU 推理也可用)

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

依赖项:
- `PySide6>=6.5.0` — Qt6 Python 绑定
- `PySide6-WebEngine>=6.5.0` — 嵌入式浏览器
- `psutil>=5.9.0` — 进程管理

### 2. 配置模型

编辑 `settings.json`，添加你的 GGUF 模型路径:

```json
{
  "default_context": "8192",
  "default_ngl": "999",
  "default_n_predict": "4096",
  "stop_model_on_exit": true,
  "text_models": ["D:/path/to/your/model.gguf"],
  "mmproj_models": ["D:/path/to/your/mmproj.gguf"]
}
```

### 3. 启动应用

```bash
python main.py
```

或直接运行打包后的 `dist\Allama\Allama.exe`（如有）。

## 💡 使用模式

### 聊天模式
1. 启动 llama-server（加载本地模型）
2. 在聊天界面输入消息，模型自动推理

### Agent 模式
1. 点击 Agent 标签页
2. 配置步骤：
   - 第一步：填入 API 地址 (如 `http://localhost:7890`)
   - 第二步：API Key（Ollama 模式可为空）
   - 第三步：模型名称（如 `qwen3-coder:30b`）
3. Agent 自动进行工具调用推理循环

## ⚙️ 配置说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `default_context` | 8192 | 上下文窗口大小 |
| `default_ngl` | 999 | GPU 加载层数（999=全部） |
| `default_n_predict` | 4096 | 最大预测 token 数 |
| `stop_model_on_exit` | true | 退出时停止 llama-server |

## 🔧 常用命令

```bash
# 查看 GPU 显存
nvidia-smi

# 检查端口占用
netstat -ano | findstr "8080 7890"

# 清理临时脚本
Remove-Item "RunTime\TempDeploy_*.bat" -Force

# 查看日志
Get-Content "RunTime/Debug/app.log" -Tail 50
```

## 🐛 常见问题

| 问题 | 解决方案 |
|------|----------|
| CUDA OOM | 减小 `default_ngl` 或换用小量化模型 |
| 端口冲突 | 自动切换到下一个可用端口 |
| 模型加载失败 | 检查路径和 GGUF 格式完整性 |
| UI 无响应 | 查看 `RunTime/Debug/app.log` 日志 |

## 📝 日志

运行时日志记录到 `RunTime/Debug/app.log`，包含：
- 应用启动/关闭
- llama-server 状态
- API 请求与响应
- Agent 工具调用详情
- 错误与警告

## 🏗️ 构建

```bash
# 清理旧构建
rm -rf build/ dist/

# PyInstaller 打包
pyinstaller --clean Allama.spec

# 输出在 dist/Allama/
```

## 📄 License

MIT License

## 🙏 致谢

- [llama.cpp](https://github.com/ggerganov/llama.cpp) — 高效的 C++ 大模型推理引擎
- [PySide6](https://www.qt.io/pyside6) — Qt for Python
- [Ollama](https://ollama.com) — API 协议参考
