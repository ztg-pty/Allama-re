"""
System prompt builder - incorporates project rules.
"""

from pathlib import Path
from .plugin.tool_registry import ToolRegistry


def build_system_prompt(
    tool_registry: ToolRegistry = None,
    workspace_dir: Path = None,
) -> str:
    '''
    Build the system prompt for the agent.
    
    If workspace_dir is provided, loads project rules from .clinerules files.
    If tool_registry is provided, includes registered tool definitions.
    '''
    prompt_parts = []
    
    # Tool definitions
    tools = tool_registry.enabled_tools() if tool_registry else []
    if tools:
        prompt_parts.append("You are an AI programming assistant with access to the following tools:")
        for tool in tools:
            prompt_parts.append(f"\n{tool.name}({tool.name}) - {tool.description}")
            if tool.parameters:
                prompt_parts.append(f"  Parameters: {tool.parameters}")
    else:
        # Default tools
        prompt_parts.append("""You are an AI programming assistant with access to the following tools:

1. read_file(path: str) - Read file contents at the specified path
2. write_file(path: str, content: str) - Write content to a file
3. execute_command(command: str) - Execute a system command and return output""")
    
    prompt_parts.append("""
When using tools, output tool calls in this format:
<tool_call>
<name>tool_name</name>
<params>
{ "param": "value" }
</params>
</tool_call>

Rules:
- After user message, you can reply with text directly or use tools to complete tasks.
- Each response contains at most one tool call block.
- Tool calls must be at the beginning or end of your response, with no other text before/after.
- Use UTF-8 encoding when reading files.
- Command execution timeout is 60 seconds, output truncated to 4000 characters.
- Reply to the user in Chinese.
""")
    
    # Load project rules if workspace provided
    if workspace_dir:
        try:
            from .rules import ProjectRules
            project_rules = ProjectRules(workspace_dir)
            rules_text = project_rules.get_rules_text()
            if rules_text:
                prompt_parts.append(f"\n\nProject Rules:\n{rules_text}")
        except Exception:
            pass  # Non-critical, continue without rules
    
    return "\n".join(prompt_parts)
