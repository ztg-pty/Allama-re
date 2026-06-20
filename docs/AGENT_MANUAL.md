# Allama Agent 插件维护手册

## 概述

Agent 插件系统基于 PySide6 + llama.cpp，提供工具调用（Function Calling）自动推理循环，支持文件读写、命令行执行等操作。详见 [Agent 模型部署手册](./AGENT_PLUGIN.md)。

## 目录结构

```
Agent/
├── agent_chat.py        # Agent 聊天界面
├── agent_wizard.py      # 配置向导 (URL/Key/Model)
├── api_client.py        # OpenAI/Ollama API 客户端
├── tool_executor.py     # 工具执行（文件/命令）
├── system_prompts.py    # 系统提示词模板
├── core/                # Agent 核心
│   ├── agent_loop.py    # 推理循环
│   ├── context_compaction.py  # 上下文压缩
│   └── event_bus.py     # 事件总线
├── plugin/              # 插件系统
└── adapter/             # Provider 适配层
```

## 核心组件

### 1. Agent Loop (`agent_loop.py`)

**功能**：自动推理循环，负责：
- 管理对话上下文
- 调用工具（Function Calling）
- 处理工具执行结果
- 重新推理决策

**关键方法**：
```python
class AgentLoop:
    async def run(self, user_message: str) -> str:
        """执行完整的 Agent 推理循环"""

    async def call_tool(self, tool_name: str, tool_args: dict) -> dict:
        """调用工具并返回结果"""
```

### 2. Context Compaction (`context_compaction.py`)

**功能**：压缩对话历史，避免上下文溢出

**压缩策略**：
- 保留最近 6 轮对话
- 保留关键工具调用和结果
- 超过 8192 tokens 自动压缩

**关键方法**：
```python
class ContextCompactor:
    def compress(self, history: list) -> list:
        """压缩对话历史"""

    def estimate_tokens(self, text: str) -> int:
        """估算文本 token 数"""
```

### 3. Tool Executor (`tool_executor.py`)

**功能**：安全执行工具调用

**支持的工具**：
- 文件读写（`read_file`, `write_file`, `list_directory`）
- 命令执行（`execute_command`）
- 网络请求（`http_request`）
- 自定义插件（`plugin_execute`）

**安全措施**：
- 命令白名单
- 文件路径限制
- 超时控制
- 错误隔离

### 4. API Client (`api_client.py`)

**功能**：OpenAI / Ollama 双协议 API 客户端

**配置**：
```python
class ApiClient:
    def __init__(self, api_url: str, api_key: str = "", model: str = ""):
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
```

**请求格式**：
- OpenAI: `POST /v1/chat/completions`
- Ollama: `POST /api/chat` 或 `/api/generate`

## 系统提示词

**位置**：`system_prompts.py`

**模板**：
```python
SYSTEM_PROMPT = """
你是一个有用的 AI 助手，拥有工具调用能力。

可用工具：
{tools}

使用规则：
1. 分析用户请求，判断是否需要调用工具
2. 如果需要工具，调用最合适的工具
3. 工具返回后，根据结果继续推理
4. 最终回复用户
"""
```

## 配置向导 (`agent_wizard.py`)

**功能**：引导用户配置 Agent

**配置步骤**：
1. **第一步**：API 地址（如 `http://localhost:7890`）
2. **第二步**：API Key（Ollama 模式可为空）
3. **第三步**：模型名称（如 `qwen3-coder:30b`）

**保存位置**：`settings.json`
```json
{
  "agent_api_url": "http://localhost:7890",
  "agent_api_key": "",
  "agent_model": "qwen3-coder:30b"
}
```

## 故障排查

### 问题 1：工具调用失败

**症状**：工具执行返回错误

**排查步骤**：
1. 检查工具权限配置
2. 查看工具执行日志（`RunTime/Debug/app.log`）
3. 验证命令白名单
4. 确认文件路径存在

**解决方案**：
```python
# 检查工具列表
tools = tool_executor.list_available_tools()
print(tools)

# 添加自定义工具
tool_executor.register_tool("my_tool", my_tool_func)
```

### 问题 2：上下文溢出

**症状**：推理循环卡死或报错

**排查步骤**：
1. 检查对话历史长度
2. 查看上下文压缩日志
3. 确认模型上下文限制

**解决方案**：
```python
# 手动压缩上下文
compactor = ContextCompactor()
compressed = compactor.compress(history)
```

### 问题 3：API 连接失败

**症状**：无法连接到 llama-server

**排查步骤**：
1. 检查 API 地址是否正确
2. 验证端口是否被占用（`netstat -ano | findstr "7890"`）
3. 查看 llama-server 日志
4. 测试 API 连通性

**解决方案**：
```bash
# 测试 API
curl http://localhost:7890/api/tags

# 检查端口占用
netstat -ano | findstr "7890"
```

## 扩展指南

### 添加新工具

1. 在 `tool_executor.py` 中定义工具函数：
```python
def my_tool_function(args: dict) -> dict:
    """工具描述"""
    # 实现工具逻辑
    return {"success": True, "result": "数据"}
```

2. 注册工具：
```python
tool_executor.register_tool("my_tool", my_tool_function)
```

3. 更新系统提示词，添加工具描述

### 添加新 Provider

1. 在 `adapter/` 目录创建适配器：
```python
class MyProviderAdapter:
    def __init__(self, config: dict):
        self.config = config

    def chat(self, messages: list) -> dict:
        # 实现聊天逻辑
        pass
```

2. 在 `api_client.py` 中集成
3. 更新配置向导

## 日志查看

**日志位置**：`RunTime/Debug/app.log`

**关键日志**：
- `AgentLoop`: 推理循环执行
- `ToolExecutor`: 工具调用
- `ContextCompactor`: 上下文压缩
- `ApiClient`: API 请求

**日志级别**：
- `INFO`: 正常流程
- `DEBUG`: 详细调试信息
- `WARNING`: 警告信息
- `ERROR`: 错误信息

## 性能优化

### 上下文压缩优化

- 调整 `keep_last` 参数（默认 6）
- 根据模型上下文限制调整压缩策略
- 保留关键对话轮次

### 工具调用优化

- 缓存常用工具结果
- 限制并发工具调用数量
- 设置合理的超时时间

### API 请求优化

- 使用连接池
- 启用请求重试
- 压缩请求体

## 参考资源

- [llama.cpp 文档](https://github.com/ggerganov/llama.cpp)
- [OpenAI API 文档](https://platform.openai.com/docs/api-reference/chat)
- [Ollama API 文档](https://�ollama.com/docs/api)
