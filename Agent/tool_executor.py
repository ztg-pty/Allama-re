import os
import subprocess
import tempfile
from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from .plugin.tool_registry import ToolRegistry, ToolSpec

DANGEROUS_COMMANDS = ["rm -rf", "format", "del /f", "del /s", "rd /s", "shutdown",
                      "dd if=", "mkfs", ":(){ :|:& };:", "> /dev/sda"]


class ToolExecutor:
    '''
    Tool executor that integrates with the plugin system.
    Wraps the ToolRegistry for backward compatibility.
    '''
    
    def __init__(self, parent_widget=None, workspace: Path = None):
        self._parent = parent_widget
        self._workspace = workspace or Path.cwd()
        self._registry = ToolRegistry()
        self._register_builtins()
    
    def _register_builtins(self):
        '''Register built-in tools.'''
        self._registry.register(ToolSpec(
            name="read_file",
            description="Read the contents of a file at the given path.",
            parameters={"path": "string"},
            handler=self._read_file,
            is_builtin=True,
        ))
        self._registry.register(ToolSpec(
            name="write_file",
            description="Write content to a file at the given path.",
            parameters={"path": "string", "content": "string"},
            handler=self._write_file,
            is_builtin=True,
        ))
        self._registry.register(ToolSpec(
            name="execute_command",
            description="Execute a shell command and return the output.",
            parameters={"command": "string"},
            handler=self._execute_command,
            is_builtin=True,
        ))
    
    @property
    def registry(self) -> ToolRegistry:
        '''Access the underlying tool registry.'''
        return self._registry
    
    def execute_tool(self, tool_name: str, params: dict) -> str:
        '''Execute a tool by name with the given params.'''
        if self._registry.has(tool_name):
            try:
                return self._registry.execute(tool_name, params)
            except Exception as e:
                return f"Tool execution error: {e}"
        return f"Unknown tool: {tool_name}"
    
    def _read_file(self, params: dict) -> str:
        path = params.get("path", "")
        if not path:
            return "Error: No file path specified"
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = self._workspace / file_path
        try:
            resolved = file_path.resolve()
            if self._workspace.resolve() not in resolved.parents and resolved != self._workspace.resolve():
                if not self._confirm(f"File is outside workspace:\n{resolved}\n\nRead anyway?"):
                    return "User declined to read file outside workspace"
            content = resolved.read_text(encoding="utf-8", errors="replace")
            if len(content) > 8000:
                content = content[:8000] + f"\n... (truncated, total {len(content)} chars)"
            return content
        except Exception as e:
            return f"Read failed: {e}"
    
    def _write_file(self, params: dict) -> str:
        path = params.get("path", "")
        content = params.get("content", "")
        if not path:
            return "Error: No file path specified"
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = self._workspace / file_path
        if self._parent and not self._confirm(f"Write to file?\n{file_path}\n\nContinue?"):
            return "User declined to write"
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return f"Written to: {file_path}"
        except Exception as e:
            return f"Write failed: {e}"
    
    def _execute_command(self, params: dict) -> str:
        command = params.get("command", "")
        if not command:
            return "Error: No command specified"
        for dangerous in DANGEROUS_COMMANDS:
            if dangerous.lower() in command.lower():
                if self._parent and not self._confirm(f"Warning: Command may be dangerous:\n{command}\n\nContinue?"):
                    return f"User declined to execute: {command}"
        if self._parent:
            from .agent_chat import AgentChatWidget
            if isinstance(self._parent, AgentChatWidget):
                if not self._parent._allow_exec:
                    return "Command execution disabled (check 'Allow command execution' checkbox)"
                if not self._confirm(f"Execute command:\n{command}\n\nRun?"):
                    return "User declined to execute this command"
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(self._workspace),
                encoding="utf-8",
                errors="replace",
            )
            output = result.stdout
            if result.stderr:
                output += "\n[stderr]\n" + result.stderr
            if len(output) > 4000:
                output = output[:4000] + f"\n... (truncated, total {len(output)} chars)"
            output += f"\n[exit code: {result.returncode}]"
            return output
        except subprocess.TimeoutExpired:
            return "Error: Command execution timed out (60s)"
        except Exception as e:
            return f"Execution failed: {e}"
    
    def _confirm(self, message: str) -> bool:
        if self._parent:
            reply = QMessageBox.question(
                self._parent, "Confirm Operation", message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            return reply == QMessageBox.StandardButton.Yes
        return True


# Builtin tool definitions for system prompts
BUILTIN_TOOLS = {
    "read_file": {
        "description": "Read the contents of a file at the given path.",
        "parameters": {"path": "string"},
    },
    "write_file": {
        "description": "Write content to a file at the given path.",
        "parameters": {"path": "string", "content": "string"},
    },
    "execute_command": {
        "description": "Execute a shell command and return the output.",
        "parameters": {"command": "string"},
    },
}
