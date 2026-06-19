import logging
logger = logging.getLogger("agent_loop")
import re
import json
import asyncio
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..adapter.interfaces import ProviderAdapter, LoggerAdapter, EventBus
from ..plugin.tool_registry import ToolRegistry


class AgentTurnResult:
    '''Result of a single agent turn.'''
    
    def __init__(self):
        self.text_response: str = ""
        self.tool_calls: List[Dict[str, Any]] = []
        self.is_complete: bool = False
        self.error: Optional[str] = None


class StatelessAgentLoop:
    '''
    Stateless agent iteration loop (Cline's @cline/agents equivalent).
    
    This is the core agent loop that:
    - Takes messages as input (not owned by this class)
    - Calls the LLM provider
    - Parses tool calls from response
    - Returns results for the host to process
    
    Design rule: agents layer owns no persistence or host lifecycle.
    '''
    
    def __init__(
        self,
        provider: ProviderAdapter,
        tool_registry: ToolRegistry,
        logger: LoggerAdapter,
        event_bus: EventBus,
        max_tool_rounds: int = 10,
    ):
        self.provider = provider
        self.tool_registry = tool_registry
        self.logger = logger or logging.getLogger("agent_loop")
        self.event_bus = event_bus
        self.max_tool_rounds = max_tool_rounds
        self.logger.info("StatelessAgentLoop 初始化, max_tool_rounds=%d", max_tool_rounds)
    
    def run_turn(self, messages: List[Dict[str, Any]], model: str, **kwargs) -> AgentTurnResult:
        '''
        Run a single agent turn.
        
        Args:
            messages: Complete message history
            model: Model name to use
            **kwargs: Additional provider parameters
            
        Returns:
            AgentTurnResult with response and tool calls
        '''
        result = AgentTurnResult()
        
        self.event_bus.emit("agent.turn.start", messages=messages)
        self.logger.info("Agent turn started")
        
        try:
            response = self.provider.chat(messages=messages, model=model, **kwargs)
            result.text_response = response
            
            tool_calls = self._parse_tool_calls(response)
            if tool_calls:
                result.tool_calls = tool_calls
                # Validate tool calls against registry
                valid_calls = []
                for tc in tool_calls:
                    if self.tool_registry.has(tc["name"]):
                        valid_calls.append(tc)
                    else:
                        self.logger.warning("Unknown tool: %s", tc["name"])
                result.tool_calls = valid_calls
            else:
                result.is_complete = True
            
            self.event_bus.emit("agent.turn.complete", result=result)
            
        except Exception as e:
            result.error = str(e)
            self.logger.error(f"Agent turn error: {e}")
            self.event_bus.emit("agent.error", error=e, messages=messages)
        
        return result
    
    def run_loop(self, messages: List[Dict[str, Any]], model: str, 
                 tool_executor: Callable, **kwargs) -> List[Dict[str, Any]]:
        '''
        Run the full agent loop with tool execution.
        
        This orchestrates multiple turns until the agent completes
        or reaches max_tool_rounds.
        
        Args:
            messages: Message history (modified in place)
            model: Model name
            tool_executor: Function to execute tool calls
            **kwargs: Provider parameters
            
        Returns:
            Updated messages list
        '''
        tool_rounds = 0
        logger.info("Agent 循环开始, model=%s", model)
        
        while tool_rounds < self.max_tool_rounds:
            self.event_bus.emit("agent.turn.start", turn=tool_rounds, messages=messages)
            self.logger.info(f"Agent turn {tool_rounds + 1}/{self.max_tool_rounds}")
            
            result = self.run_turn(messages, model, **kwargs)
            
            if result.error:
                error_msg = f"API Error: {result.error}"
                messages.append({"role": "assistant", "content": error_msg})
                break
            
            # Append assistant response
            messages.append({"role": "assistant", "content": result.text_response})
            
            if result.is_complete or not result.tool_calls:
                break
            
            # Execute tool calls
            for tool_call in result.tool_calls:
                tool_name = tool_call["name"]
                tool_params = tool_call.get("params", {})
                
                self.event_bus.emit("agent.tool.call", tool=tool_name, params=tool_params)
                self.logger.info(f"Executing tool: {tool_name}")
                
                try:
                    tool_result = tool_executor(tool_name, tool_params)
                    logger.info("工具 %s 执行成功", tool_name)
                except Exception as e:
                    logger.error("工具 %s 执行失败: %s", tool_name, e)
                    tool_result = f"Tool execution error: {e}"
                
                self.event_bus.emit("agent.tool.result", tool=tool_name, result=tool_result)
                self.logger.info(f"Tool {tool_name} completed")
                
                messages.append({
                    "role": "tool",
                    "content": str(tool_result)[:8000],
                    "tool_call_id": tool_name,
                })
            
            tool_rounds += 1
        
        logger.info("Agent 循环完成, 工具轮次=%d", tool_rounds)
        self.event_bus.emit("agent.loop.complete", rounds=tool_rounds)
        return messages
    
    def run_loop_stream(self, messages: List[Dict[str, Any]], model: str,
                        tool_executor: Callable, **kwargs):
        '''
        Run the agent loop with streaming support.
        Yields (text_chunk, is_final) tuples.
        '''
        tool_rounds = 0
        final_response = ""
        
        while tool_rounds < self.max_tool_rounds:
            messages.append({"role": "assistant", "content": ""})
            
            response_chunks = []
            for chunk in self.provider.chat_stream(messages=messages, model=model, **kwargs):
                response_chunks.append(chunk)
                final_response += chunk
                self.event_bus.emit("agent.stream.token", token=chunk, turn=tool_rounds)
                yield chunk, False
            
            full_response = "".join(response_chunks)
            messages[-1]["content"] = full_response
            
            tool_calls = self._parse_tool_calls(full_response)
            if not tool_calls:
                yield full_response, True
                break
            
            for tool_call in tool_calls:
                if not self.tool_registry.has(tool_call["name"]):
                    continue
                tool_result = tool_executor(tool_call["name"], tool_call.get("params", {}))
                messages.append({
                    "role": "tool",
                    "content": str(tool_result)[:8000],
                    "tool_call_id": tool_call["name"],
                })
            
            tool_rounds += 1
        
        self.event_bus.emit("agent.loop.complete", rounds=tool_rounds)
        yield "", True
    
    @staticmethod
    def _parse_tool_calls(text: str) -> List[Dict[str, Any]]:
        '''Parse tool calls from model response text.'''
        results = []
        pattern = r'<tool_call>\s*<name>(.*?)</name>\s*<params>\s*(\{.*?\})\s*</params>\s*</tool_call>'
        
        for match in re.finditer(pattern, text, re.DOTALL):
            name = match.group(1).strip()
            params_str = match.group(2).strip()
            try:
                params = json.loads(params_str)
            except json.JSONDecodeError:
                params = {}
            results.append({"name": name, "params": params})
        
        if not results:
            # Case-insensitive fallback
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                try:
                    params = json.loads(match.group(2).strip())
                except json.JSONDecodeError:
                    params = {}
                results.append({"name": match.group(1).strip(), "params": params})
        
        return results


