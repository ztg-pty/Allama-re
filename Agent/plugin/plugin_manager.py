"""
Plugin Manager - Manages extensible plugins/tools.
Equivalent to Cline's Plugin and Extension system.
"""

import importlib
import inspect
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

from .tool_registry import ToolRegistry, ToolSpec


class BasePlugin:
    '''Base class for plugins.'''
    
    @property
    def name(self) -> str:
        raise NotImplementedError
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return ""
    
    def register_tools(self, registry: ToolRegistry) -> None:
        '''Override to register tools.'''
        pass
    
    def on_load(self) -> None:
        '''Called when plugin is loaded.'''
        pass
    
    def on_unload(self) -> None:
        '''Called when plugin is unloaded.'''
        pass


class PluginManager:
    '''
    Manages plugin loading, registration, and lifecycle.
    '''
    
    def __init__(self, tool_registry: ToolRegistry):
        self._registry = tool_registry
        self._plugins: Dict[str, BasePlugin] = {}
        self._plugin_dirs: List[Path] = []
    
    def add_plugin_dir(self, path: Path) -> None:
        '''Add a directory to scan for plugins.'''
        self._plugin_dirs.append(path)
    
    def load_builtin_plugins(self) -> None:
        '''Load built-in plugins from this package.'''
        from .. import tool_executor
        self._register_tool_plugin(
            "core_tools",
            tool_executor.BUILTIN_TOOLS,
        )
    
    def _register_tool_plugin(self, name: str, tools: Dict[str, Dict[str, Any]]) -> None:
        '''Register a tool-based plugin.'''
        
        class ToolPlugin(BasePlugin):
            @property
            def name(self):
                return name
            
            def register_tools(self, registry: ToolRegistry):
                for tool_name, tool_info in tools.items():
                    registry.register(ToolSpec(
                        name=tool_name,
                        description=tool_info.get("description", ""),
                        parameters=tool_info.get("parameters", {}),
                        handler=tool_info.get("handler"),
                        is_builtin=True,
                    ))
        
        plugin = ToolPlugin()
        self._plugins[name] = plugin
        plugin.register_tools(self._registry)
    
    def load_discovery_plugins(self) -> None:
        '''Scan plugin directories for discoverable plugins.'''
        for plugin_dir in self._plugin_dirs:
            if not plugin_dir.exists():
                continue
            for py_file in plugin_dir.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue
                try:
                    spec = importlib.util.spec_from_file_location(
                        py_file.stem, str(py_file)
                    )
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Look for classes that inherit from BasePlugin
                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and 
                            issubclass(obj, BasePlugin) and 
                            obj is not BasePlugin):
                            plugin = obj()
                            self._plugins[plugin.name] = plugin
                            plugin.register_tools(self._registry)
                            plugin.on_load()
                except Exception:
                    pass
    
    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        return self._plugins.get(name)
    
    def list_plugins(self) -> List[Dict[str, str]]:
        return [
            {
                "name": p.name,
                "version": p.version,
                "description": p.description,
            }
            for p in self._plugins.values()
        ]
    
    def unload_plugin(self, name: str) -> bool:
        plugin = self._plugins.pop(name, None)
        if plugin:
            plugin.on_unload()
            return True
        return False
