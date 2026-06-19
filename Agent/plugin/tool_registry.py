"""
Tool Registry - Central registry for available tools.
Equivalent to Cline's tool registration system.
"""

from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class ToolSpec:
    '''Specification for a registered tool.'''
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    handler: Optional[Callable] = None
    is_builtin: bool = False
    enabled: bool = True


class ToolRegistry:
    '''
    Central registry for agent tools.
    Supports registration, validation, and discovery of tools.
    '''
    
    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}
    
    def register(self, tool: ToolSpec) -> None:
        '''Register a tool.'''
        self._tools[tool.name] = tool
    
    def unregister(self, name: str) -> bool:
        '''Unregister a tool by name.'''
        if name in self._tools:
            del self._tools[name]
            return True
        return False
    
    def has(self, name: str) -> bool:
        '''Check if a tool is registered.'''
        return name in self._tools
    
    def get(self, name: str) -> Optional[ToolSpec]:
        '''Get a tool spec by name.'''
        return self._tools.get(name)
    
    def list_tools(self) -> List[ToolSpec]:
        '''List all registered tools.'''
        return list(self._tools.values())
    
    def enabled_tools(self) -> List[ToolSpec]:
        '''List only enabled tools.'''
        return [t for t in self._tools.values() if t.enabled]
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        '''Get tool definitions in a format suitable for LLM system prompts.'''
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in self.enabled_tools()
        ]
    
    def execute(self, name: str, params: Dict[str, Any]) -> Any:
        '''Execute a registered tool.'''
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Tool not found: {name}")
        if not tool.enabled:
            raise ValueError(f"Tool disabled: {name}")
        if not tool.handler:
            raise ValueError(f"Tool has no handler: {name}")
        return tool.handler(params)
