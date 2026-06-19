# Allama Agent 设计蓝皮书

> **在编写前务必已阅读项目代码。**

---

## 1. 架构总览

### 1.1 Agent 系统定位

Allama 的 Agent 模块运行于 PySide6 桌面应用的 **Agent 模式页面**（`_build_agent_page`），作为独立于 llama-ui 嵌入式聊天界面的 **工具增强型对话智能体**。Agent 通过 OpenAI 兼容 API 协议与 LLM Provider 交互，支持工具调用（Function Calling）的自动循环推理。

### 1.2 Agent 生命周期

```

QtApp._build_agent_page()
  |
  +-> AgentWizard (三步配置: URL -> API Key -> Model Name)
  |      |
  |      -> on_configured(config)
  |             |
  |             -> AgentApiClient(base_url, api_key, model)
  |             -> AgentChatWidget(client)
  |                     |
  |                     -> StatelessAgentLoop
  |                               |
  |                    +----------+----------+
  |                    |  run_loop() 循环      |
  |                    |                       |
  |              +-----+-----+        +------+------+
  |              | Provider   |        | ToolExecutor |
  |              | chat()     |        | execute_tool |
  |              +-----+-----+        +------+------+
  |                    |                      |
  |              Ollama API -> llama-server    |
  |                          (GGUF 推理)      |
  |                      +----+              |
  |                      |解析| <-- tool 标签|
  |                      +----+              |
  |                    +----+   +------------+
  |                    |完成| <-- 无 tool 调用
  +--------------------+----+

循环终止条件:
  1. 响应中无 <name>/<params> tool 调用标签
  2. 达到 max_tool_rounds (默认 10)
  3. API 请求异常
```

### 1.3 消息传递路径

```
用户输入 (AgentChatWidget._input)
  |
  v
AgentChatWidget._send()
  |  追加 user 消息到 self._messages
  |
  v
StatelessAgentLoop.run_loop()  (后台线程)
  |
  +---> ProviderAdapter.chat()
  |       |
  |       v
  |    AgentApiClient.chat()
  |       |
  |       +---> HTTP POST -> {base_url}/v1/chat/completions
  |       |      (含 messages, model, temperature, max_tokens)
  |       |
  |       +---> HTTP POST -> {base_url}/api/chat  (Ollama 端点)
  |              |
  |              v
  |           ApiServer._handle_llama()  (llama.py)
  |              |
  |              +---> HTTP POST -> 127.0.0.1:{llama_port}/generate
  |              |      (含 prompt, n_predict, temperature)
  |              |
  |              +---> llama-server.exe
  |                     |
  |                     v
  |                  GGUF 模型推理 (CUDA/CPU)
  |
  v
解析 <name>/<params> 工具调用标签
  |
  +---> ToolExecutor.execute_tool(tool_name, params)
  |       |
  |       +---> read_file(params["path"]) -> Path.read_text()
  |       +---> write_file(params["path"], params["content"]) -> Path.write_text()
  |       +---> execute_command(params["command"]) -> subprocess.run(command, shell=True)
  |
  v
将 tool 结果追加为 {"role": "tool", "content": result}
  |
  v
循环 (tool_rounds += 1) -> 回到 ProviderAdapter.chat()
  |
  v
[完成] -> 最终响应返回 UI
```

### 1.4 上下文压缩策略

`Agent/core/context_compaction.py` 提供三种策略，通过 `CompactionStrategyRegistry` 统一管理：

| 策略 | 类名 | 说明 | 默认参数 |
|------|------|------|----------|
| 保留最近N条 | `KeepLastStrategy` | 裁剪早期消息，仅保留最近的 N 条对话 | `keep_last=6` |
| Token 预算 | `TokenBudgetStrategy` | 按 token 估算（4字符/token）裁剪 | `max_tokens=8192` |
| 摘要压缩 | `SummarizeStrategy` | 保留最近消息，对早期对话生成摘要前缀 | `keep_recent=6` |

Token 估算公式：`tokens = len(text) / 4`

### 1.5 事件系统

`SimpleEventBus` 是线程安全的发布-订阅机制，使用 `threading.Lock` 保证并发安全：

| 事件名 | 触发时机 | 携带数据 |
|--------|----------|----------|
| `agent.turn.start` | 每轮推理开始 | `turn`, `messages` |
| `agent.turn.complete` | 每轮推理完成 | `result` (AgentTurnResult) |
| `agent.tool.call` | 工具被调用前 | `tool`, `params` |
| `agent.tool.result` | 工具执行返回后 | `tool`, `result` |
| `agent.stream.token` | 流式输出每个 token | `token`, `turn` |
| `agent.stream.complete` | 流式输出结束 | — |
| `agent.error` | 推理或工具出错 | `error`, `messages` |
| `agent.loop.complete` | Agent 循环终止 | `rounds` |

---

## 2. Agent 目录树与模块职责

```
Agent/
├── __init__.py                     # 模块初始化 (空)
│
├── agent_chat.py                   # Agent 聊天 UI
│   ├── AgentChatWidget             # 主 UI 组件
│   │   ├── _send()                 # 用户消息发送入口
│   │   ├── _run_agent_loop()       # 后台线程执行 Agent 推理
│   │   ├── MessageBubble           # 对话气泡 UI
│   │   ├── ToolCallBubble          # 工具调用显示
│   │   └── ToolResultBubble        # 工具结果显示
│   ├── MAX_TOOL_ROUNDS = 10        # 最大工具轮次常量
│
├── agent_wizard.py                 # Agent 配置向导
│   └── AgentWizard                 # 三步引导式配置
│       ├── Step 1: 服务地址 (localhost / Ollama / 自定义)
│       ├── Step 2: API Key (可选，密码输入框)
│       └── Step 3: 模型名称 (必填)
│
├── api_client.py                   # API 客户端
│   └── AgentApiClient              # OpenAI/Ollama 兼容 API 客户端
│       ├── chat()                  # 非流式调用
│       ├── chat_stream()           # 流式调用
│       ├── get_model_info()        # 模型信息缓存
│       ├── list_models()           # 模型列表
│       ├── _parse_response()       # SSE/JSON 响应解析
│       └── 接口: ProviderAdapter
│
├── tool_executor.py                # 工具执行器
│   └── ToolExecutor
│       ├── registry: ToolRegistry  # 工具注册表引用
│       ├── execute_tool()          # 统一执行入口
│       ├── _read_file()            # 文件读取工具
│       ├── _write_file()           # 文件写入工具
│       ├── _execute_command()      # Shell 命令执行
│       ├── _confirm()              # 用户确认对话框
│       └── BUILTIN_TOOLS           # 内置工具定义常量
│
├── system_prompts.py               # System Prompt 构建器
│   └── build_system_prompt()       # 注入工具定义+规则
│
├── rules.py                        # 文件驱动规则系统
│   ├── ProjectRules                # 规则加载器
│   │   ├── RULE_FILES              # [".clinerules", ".allama/rules", "rules.md", "AGENTS.md"]
│   │   ├── load()                  # 加载项目+用户规则
│   │   └── get_rules_text()        # 返回合并规则文本
│   └── RuleLoader                  # 规则变更监听器
│
├── core/
│   ├── agent_loop.py               # Agent 推理循环核心
│   │   ├── AgentTurnResult         # 单轮推理结果
│   │   ├── StatelessAgentLoop      # 无状态 Agent 循环
│   │   │   ├── run_turn()          # 单轮推理
│   │   │   ├── run_loop()          # 多轮循环 (工具执行)
│   │   │   ├── run_loop_stream()   # 流式循环
│   │   │   └── _parse_tool_calls() # 正则解析 tool 标签
│   │   └── 接口依赖: ProviderAdapter, EventBus, ToolRegistry
│   │
│   ├── event_bus.py                # 事件总线
│   │   └── SimpleEventBus          # 线程安全发布-订阅
│   │
│   └── context_compaction.py       # 上下文压缩
│       ├── CompactionStrategy      # 抽象基类
│       ├── KeepLastStrategy        # 保留最近N条
│       ├── TokenBudgetStrategy     # Token 预算裁剪
│       ├── SummarizeStrategy       # 摘要压缩
│       └── CompactionStrategyRegistry  # 策略注册表
│
├── adapter/
│   ├── interfaces.py               # 抽象接口定义
│   │   ├── LoggerAdapter           # 日志适配器接口
│   │   ├── StorageAdapter          # 存储适配器接口
│   │   ├── ProviderAdapter         # LLM Provider 适配器接口
│   │   ├── EventBus                # 事件总线接口
│   │   ├── ToolDefinition          # 工具定义类型
│   │   └── HookPhase               # 生命周期钩子阶段
│   │
│   └── implementations.py          # 接口实现
│       ├── QtLoggerAdapter         # Qt 信号日志桥接
│       ├── FileStorageAdapter      # JSON 文件存储
│       └── InMemoryStorageAdapter  # 内存存储
│
└── plugin/
    ├── tool_registry.py            # 工具注册表
    │   ├── ToolSpec                # 工具规格 (dataclass)
    │   └── ToolRegistry            # 工具注册/查询/执行
    │
    └── plugin_manager.py           # 插件管理器
        ├── BasePlugin              # 插件基类
        └── PluginManager           # 插件生命周期管理
```

---

## 3. 核心协议

### 3.1 工具调用协议

Agent 模型响应中嵌入的工具调用采用 XML 风格标签格式：

```xml
<name>tool_name</name>
<params>
{ "param": "value" }
</params>
</tool_call>
```

**解析正则**：`r'<name>(.*?)</name><params>(\{.*?\})</params>'`

**规则**：

- 每次响应最多包含一个工具调用块
- 工具调用标签必须在响应开头或结尾，前后无其他文本
- params 必须为合法 JSON 对象
- 解析失败时降级为不区分大小写匹配

### 3.2 Provider API 请求格式

**非流式 (chat)** — `AgentApiClient.chat()`：
```json
POST {base_url}/v1/chat/completions
{
  "model": "model_name",
  "messages": [{"role": "user", "content": "..."}, ...],
  "stream": false,
  "temperature": 0.7,
  "max_tokens": 4096
}
```

**流式 (chat_stream)** — `AgentApiClient.chat_stream()`：
```json
POST {base_url}/v1/chat/completions
{
  "model": "model_name",
  "messages": [...],
  "stream": true,
  "temperature": 0.7,
  "max_tokens": 4096
}
```

**Ollama 端点映射**（`ApiServer` 在 `llama.py` 中实现）：
| Ollama 端点 | 转发目标 |
|-------------|----------|
| `/api/chat` | `127.0.0.1:{llama_port}/generate` |
| `/api/generate` | `127.0.0.1:{llama_port}/generate` |
| `/api/tags` | 返回当前模型元信息 |

### 3.3 超时与重试策略

| 组件 | 超时 | 重试 | 备注 |
|------|------|------|------|
| `AgentApiClient.chat()` | 120s | 无 | 非流式 HTTP 请求 |
| `AgentApiClient.chat_stream()` | 120s | 无 | 流式 HTTP 请求 |
| `ApiServer._handle_llama()` | 600s | 无 | Ollama 代理转发 |
| `DeploymentManager.start()` | 端口冲突时自动重试 | 最多搜索 50 个端口 | 基于 `PortAllocator` |
| `ToolExecutor._execute_command()` | 60s | 无 | `subprocess.run(timeout=60)` |
| Agent 循环 | — | `max_tool_rounds=10` | 达到上限自动终止 |

### 3.4 错误处理约定

`DeploymentManager` 内置错误模式匹配（`ERROR_PATTERNS` 列表），自动识别并分类：

| 错误模式 | 处理动作 |
|----------|----------|
| `GGML_CUDA: mm_malloc failed` | 提示降低 `-ngl` / 选择低精度模型 |
| `port already in use` | 自动分配新端口并热重启 |
| `context size exceeded` | 提示压缩对话历史或增大 `-c` 参数 |
| `flash_attn not supported` | 自动禁用 Flash Attention |
| `EOS token not found` | 提示模型文件可能损坏或不完整 |

---

## 4. 扩展指南

### 4.1 新增内置工具 CheckList

目标：在不修改 `_runtime/` 的前提下，为 Agent 添加一个新的工具能力。

| 步骤 | 文件 | 操作 |
|------|------|------|
| 1 | `Agent/tool_executor.py` | 在 `ToolExecutor` 类中添加 `_new_tool(self, params: dict) -> str` 方法 |
| 2 | `Agent/tool_executor.py` | 在 `_register_builtins()` 中调用 `self._registry.register(ToolSpec(...))` |
| 3 | `Agent/tool_executor.py` | 如适用，在 `DANGEROUS_COMMANDS` 列表中添加匹配模式 |
| 4 | `Agent/tool_registry.py` | 确认 `ToolSpec` dataclass 字段覆盖新工具的需求 |
| 5 | `Agent/system_prompts.py` | 确认 `build_system_prompt()` 中的 prompt 模板包含新工具说明 |
| 6 | `Agent/tool_executor.py` | 在 `BUILTIN_TOOLS` 字典中添加新工具的描述信息 |
| 7 | 测试验证 | 启动 Allama -> 进入 Agent 模式 -> 发送含工具调用的消息 |

### 4.2 新增外部插件 CheckList

目标：通过插件系统注入工具，无需修改现有 Python 文件。

| 步骤 | 操作 |
|------|------|
| 1 | 创建插件目录，如 `%APPDATA%\allama\plugins\` |
| 2 | 编写 `my_plugin.py`，继承 `BasePlugin`，实现 `register_tools()` |
| 3 | 修改 `PluginManager.load_discovery_plugins()` 或调用 `add_plugin_dir()` 添加扫描路径 |
| 4 | 验证：插件命名不能以 `_` 开头，类必须继承 `BasePlugin`，异常被静默捕获 |

### 4.3 新增上下文压缩策略 CheckList

| 步骤 | 文件 | 操作 |
|------|------|------|
| 1 | `Agent/core/context_compaction.py` | 继承 `CompactionStrategy`，实现 `compress()` 方法 |
| 2 | `Agent/core/context_compaction.py` | 在 `CompactionStrategyRegistry._register_defaults()` 中注册 |

---

## 5. 待确认事项

以下项在代码中存在但缺乏明确文档，需进一步确认：

1. **`AppSettings._DEFAULTS` 中 `enable_mmproj_default` 的默认值为 `False`**，但 `settings.json` 中配置为 `true`，两者不一致。以哪个为准？
2. **`AgentApiClient.chat_stream()` 方法**目前未被 `StatelessAgentLoop.run_loop_stream()` 以外的组件调用，是否为预留能力？
3. **`MessageHistory` 类**（`llama.py` 中定义）在聊天页面中使用，但 Agent 模式使用独立的 `self._messages` 列表，两者互不通信。是否需要统一消息历史管理？
4. **`PluginManager.load_builtin_plugins()` 目前只注册 `core_tools` 插件**，`load_discovery_plugins()` 的扫描目录未配置。是否计划在运行时动态指定？
5. **`CompactionStrategyRegistry` 已定义但尚未在任何地方实例化和使用**。上下文压缩的实际触发时机和策略选择机制待定。
6. **`ApiServer._handle_llama()` 对 `/api/chat` 的请求中**，`messages` 列表被拼接为单一 `prompt` 字段发送给 llama-server，历史对话的上下文合并逻辑在 Provider 侧还是 API 代理侧？当前实现似乎仅传递用户最后一条消息的 prompt。
7. **`_runtime/logger.py` 的日志目录路径**：已确认日志写入 `RunTime/Debug/app.log`。`_runtime/` 是一个 Python 模块（含 `__init__.py` 和 `logger.py`），位于项目根目录，负责初始化日志记录器并将日志输出到 `RunTime/Debug/` 目录。`RunTime/` 包含 llama.cpp 的二进制文件和 DLL。
