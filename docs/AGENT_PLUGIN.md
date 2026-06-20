# Allama Agent 插件模型部署手册

## 概述

Agent 插件系统允许用户自定义 Agent 行为，通过配置不同的模型、API 和工具集来实现多样化的 AI 助手功能。

## 目录结构

```
Agent/
├── agent_chat.py        # Agent 聊天界面
├── agent_wizard.py      # 配置向导
├── api_client.py        # API 客户端
├── tool_executor.py     # 工具执行
├── system_prompts.py    # 提示词模板
├── core/
│   ├── agent_loop.py    # 推理循环
│   ├── context_compaction.py  # 上下文压缩
│   └── event_bus.py     # 事件总线
└── plugins/             # 自定义插件
    └── my_plugin.py
```

## 部署步骤

### 1. 基础配置

**配置文件位置**：`settings.json`

```json
{
  "agent_api_url": "http://localhost:7890",
  "agent_api_key": "",
  "agent_model": "qwen3-coder:30b",
  "agent_tools": ["file", "command", "web_search"],
  "agent_context_size": 8192
}
```

### 2. 配置向导

**启动配置向导**：
1. 打开"Agent 模式"标签页
2. 点击"配置 Agent"
3. 按步骤填写信息：
   - 第一步：API 地址
   - 第二步：API Key（可选）
   - 第三步：模型名称

### 3. 选择工具集

**内置工具**：
- `file` - 文件读写
- `command` - 命令执行
- `web_search` - 网络搜索

**自定义工具**：
1. 在 `plugins/` 目录创建插件文件
2. 继承 `BaseTool` 类
3. 实现 `execute()` 方法
4. 在配置中注册

## 模型选择

### 推荐模型

| 模型类型 | 推荐模型 | 用途 |
|----------|----------|------|
| 代码助手 | `qwen2.5-coder:32b` | 代码生成和调试 |
| 文档助手 | `qwen2.5-72b-instruct` | 文档编写 |
| 对话助手 | `llama3.2-3b-instruct` | 日常对话 |
| 翻译助手 | `qwen2.5-translate` | 翻译任务 |

### 模型配置

**参数优化**：
```json
{
  "agent_model": "qwen2.5-coder:32b",
  "agent_context_size": 16384,
  "agent_temperature": 0.7,
  "agent_max_tokens": 4096
}
```

**模型选择指南**：
- **代码任务**：使用 Q4_K_M 量化版本
- **长文档处理**：使用更大的上下文窗口
- **实时对话**：使用更快的模型

## 工具配置

### 内置工具配置

**文件工具**：
```json
{
  "tools": {
    "file": {
      "read": true,
      "write": true,
      "list_directory": true,
      "allowed_paths": ["/path/to/allowed"]
    }
  }
}
```

**命令工具**：
```json
{
  "tools": {
    "command": {
      "execute": true,
      "timeout": 30,
      "allowed_commands": ["ls", "cat", "grep", "python"]
    }
  }
}
```

### 自定义工具开发

**创建插件**：
```python
# plugins/custom_tool.py
from agent_core import BaseTool

class CustomTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="custom_tool",
            description="自定义工具描述",
            parameters={
                "param1": {"type": "string", "description": "参数说明"}
            }
        )

    async def execute(self, param1: str) -> dict:
        """工具执行逻辑"""
        # 实现工具功能
        return {
            "success": True,
            "result": "执行结果",
            "data": {}
        }
```

**注册工具**：
```python
# 在 agent_chat.py 中注册
from plugins.custom_tool import CustomTool

tool_executor.register_tool("custom_tool", CustomTool())
```

## 提示词配置

### 系统提示词

**位置**：`system_prompts.py`

```python
AGENT_SYSTEM_PROMPT = """
你是一个专业的 AI 助手，具有以下能力：

# 工具能力
{tools}

# 工作流程
1. 分析用户请求
2. 决定是否需要工具
3. 执行工具调用
4. 根据结果生成回复

# 安全规则
- 不要执行危险命令
- 不要访问敏感文件
- 不要泄露用户数据
"""
```

### 自定义提示词

**修改提示词**：
```python
# 在 settings.json 中
{
  "agent_system_prompt": "你的自定义系统提示词..."
}
```

## 上下文管理

### 上下文压缩

**配置**：
```json
{
  "agent_context_size": 8192,
  "agent_compression_threshold": 0.9,
  "agent_keep_last": 6
}
```

**压缩策略**：
- 保留最近 6 轮对话
- 保留关键工具调用
- 自动压缩历史记录

### 上下文使用

**监控上下文使用**：
```python
# 在 UI 中显示
context_used = len(history) * estimate_tokens
context_available = settings.agent_context_size
context_ratio = context_used / context_available
```

## API 配置

### OpenAI 模式

```json
{
  "agent_api_url": "http://localhost:8080/v1",
  "agent_api_key": "sk-xxx",
  "agent_model": "gpt-3.5-turbo"
}
```

### Ollama 模式

```json
{
  "agent_api_url": "http://localhost:7890",
  "agent_api_key": "",
  "agent_model": "qwen2.5-coder:32b"
}
```

### API 测试

```bash
# 测试连接
curl http://localhost:7890/api/tags

# 测试聊天
curl -X POST http://localhost:7890/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5-coder:32b",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

## 故障排查

### 问题 1：工具调用失败

**检查**：
1. 工具是否正确注册
2. 工具参数是否正确
3. 工具执行权限是否足够

**解决**：
```bash
# 查看工具列表
python -c "from tool_executor import tool_executor; print(tool_executor.list_available_tools())"

# 检查工具日志
grep "ToolExecutor" RunTime/Debug/app.log
```

### 问题 2：上下文溢出

**症状**：推理循环卡死

**解决**：
```json
{
  "agent_context_size": 4096,  // 降低上下文大小
  "agent_keep_last": 3          // 减少保留轮数
}
```

### 问题 3：API 连接失败

**检查**：
1. API 地址是否正确
2. 端口是否被占用
3. 模型是否已加载

**解决**：
```bash
# 测试 API
curl http://localhost:7890/api/tags

# 查看端口
netstat -ano | findstr "7890"

# 重启服务
# 在 Allama UI 中停止并重新启动模型
```

## 性能优化

### 推理优化

**模型选择**：
- 使用量化模型（Q4_K_M, Q5_K_M）
- 根据任务选择合适大小

**参数优化**：
```json
{
  "agent_temperature": 0.7,  // 降低温度提高稳定性
  "agent_max_tokens": 2048,  // 限制最大输出
  "agent_timeout": 60        // 设置超时
}
```

### 上下文优化

**压缩策略**：
```python
# 增加压缩频率
compactor.compress_interval = 5  # 每 5 轮压缩一次

# 调整保留轮数
compactor.keep_last = 4
```

### 工具优化

**缓存工具结果**：
```python
# 实现工具结果缓存
tool_executor.enable_cache = True
tool_executor.cache_ttl = 3600  # 缓存 1 小时
```

## 监控和维护

### 日志监控

**关键日志**：
- `AgentLoop`: 推理循环执行
- `ToolExecutor`: 工具调用
- `ApiClient`: API 请求
- `ContextCompactor`: 上下文压缩

### 性能监控

**指标监控**：
```python
# 推理延迟
latency = request_end - request_start

# Token 生成速度
tokens_per_second = tokens_generated / latency

# 工具调用成功率
success_rate = successful_calls / total_calls
```

### 资源监控

**GPU 使用**：
```bash
nvidia-smi -l 1
```

**内存使用**：
```bash
Get-Process | Where-Object {$_.ProcessName -like "*llama-server*"} | Select-Object Name,WorkingSet64
```

## 扩展开发

### 创建新 Agent

**步骤**：
1. 继承 `AgentLoop` 类
2. 实现自定义推理逻辑
3. 注册到 Agent 系统中

```python
# custom_agent.py
from agent_core import AgentLoop

class CustomAgent(AgentLoop):
    async def run(self, user_message: str) -> str:
        # 自定义推理逻辑
        return "自定义回复"
```

### 集成第三方服务

**示例**：集成 GitHub API

```python
# plugins/github_tool.py
from agent_core import BaseTool

class GitHubTool(BaseTool):
    async def execute(self, repo: str, action: str) -> dict:
        # 调用 GitHub API
        response = await github_api_call(repo, action)
        return {"success": True, "data": response}
```

## 参考资源

- [Agent 插件维护手册](./AGENT.md)
- [模型部署维护手册](./MODEL_DEPLOYMENT.md)
- [日志解析 Skill](./skills/log-parser.md)
