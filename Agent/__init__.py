"""
Agent module - Layered architecture per Cline architecture analysis.

Architecture layers:
- adapter: Logger/Storage/Provider adapter interfaces and implementations
- core: Stateless agent loop, event bus, context compaction
- plugin: Tool registry and plugin manager
- api_client: LLM API client (provider layer)
- tool_executor: Tool execution (uses plugin system)
- system_prompts: System prompt builder (incorporates rules)
- rules: File-driven project rules
- agent_chat: UI integration (uses event-driven agent)
"""

# Adapter layer
from .adapter.interfaces import (
    LoggerAdapter,
    StorageAdapter,
    ProviderAdapter,
    EventBus as EventBusInterface,
    ToolDefinition,
    HookPhase,
)
from .adapter.implementations import (
    QtLoggerAdapter,
    FileStorageAdapter,
    InMemoryStorageAdapter,
)

# Core layer
from .core.agent_loop import StatelessAgentLoop, AgentTurnResult
from .core.event_bus import SimpleEventBus
from .core.context_compaction import (
    CompactionStrategyRegistry,
    CompactionStrategy,
    KeepLastStrategy,
    TokenBudgetStrategy,
    SummarizeStrategy,
)

# Plugin layer
from .plugin.tool_registry import ToolRegistry, ToolSpec
from .plugin.plugin_manager import BasePlugin, PluginManager

# Rules layer
from .rules import ProjectRules, RuleLoader

# Backward compatibility
from .api_client import AgentApiClient
from .tool_executor import ToolExecutor, BUILTIN_TOOLS
from .system_prompts import build_system_prompt

__all__ = [
    # Adapters
    "LoggerAdapter",
    "StorageAdapter", 
    "ProviderAdapter",
    "EventBusInterface",
    "ToolDefinition",
    "HookPhase",
    "QtLoggerAdapter",
    "FileStorageAdapter",
    "InMemoryStorageAdapter",
    # Core
    "StatelessAgentLoop",
    "AgentTurnResult",
    "SimpleEventBus",
    "CompactionStrategyRegistry",
    "CompactionStrategy",
    "KeepLastStrategy",
    "TokenBudgetStrategy",
    "SummarizeStrategy",
    # Plugin
    "ToolRegistry",
    "ToolSpec",
    "BasePlugin",
    "PluginManager",
    # Rules
    "ProjectRules",
    "RuleLoader",
    # Backward compat
    "AgentApiClient",
    "ToolExecutor",
    "BUILTIN_TOOLS",
    "build_system_prompt",
]
