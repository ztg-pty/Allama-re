from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class LoggerAdapter(ABC):
    '''
    Logging adapter interface.
    Host implementations (CLI/Pino, Qt signals) bridge to this interface.
    '''
    
    @abstractmethod
    def debug(self, message: str, **kwargs):
        pass
    
    @abstractmethod
    def info(self, message: str, **kwargs):
        pass
    
    @abstractmethod
    def warn(self, message: str, **kwargs):
        pass
    
    @abstractmethod
    def error(self, message: str, **kwargs):
        pass
    
    @abstractmethod
    def log(self, level: str, message: str, **kwargs):
        pass


class StorageAdapter(ABC):
    '''
    Storage adapter interface.
    Supports file-based and in-memory storage backends.
    '''
    
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        pass
    
    @abstractmethod
    def clear(self) -> None:
        pass
    
    @abstractmethod
    def keys(self) -> list:
        pass
    
    @abstractmethod
    def save_session(self, session_id: str, data: Dict) -> None:
        pass
    
    @abstractmethod
    def load_session(self, session_id: str) -> Optional[Dict]:
        pass
    
    @abstractmethod
    def list_sessions(self) -> list:
        pass


class ProviderAdapter(ABC):
    '''
    LLM provider adapter interface.
    Isolates provider-specific behavior, similar to Cline's @cline/llms layer.
    '''
    
    @abstractmethod
    def chat(self, messages: list, model: str, **kwargs) -> str:
        pass
    
    @abstractmethod
    def chat_stream(self, messages: list, model: str, **kwargs):
        '''Yields tokens as they arrive.'''
        pass
    
    @abstractmethod
    def get_model_info(self, model: str) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def list_models(self) -> list:
        pass


class EventBus(ABC):
    '''
    Event bus interface for decoupled communication.
    Replaces manual _safe_* methods with a unified event system.
    '''
    
    @abstractmethod
    def on(self, event: str, callback) -> None:
        pass
    
    @abstractmethod
    def off(self, event: str, callback) -> None:
        pass
    
    @abstractmethod
    def emit(self, event: str, *args, **kwargs) -> None:
        pass
    
    @abstractmethod
    def once(self, event: str, callback) -> None:
        pass


# Registry types
class ToolDefinition:
    '''Standard tool definition for the plugin system.'''
    
    def __init__(self, name: str, description: str, parameters: Dict[str, Any]):
        self.name = name
        self.description = description
        self.parameters = parameters


class HookPhase:
    '''Lifecycle hook phases.'''
    BEFORE_TURN = "before_turn"
    AFTER_TURN = "after_turn"
    BEFORE_TOOL_CALL = "before_tool_call"
    AFTER_TOOL_CALL = "after_tool_call"
    BEFORE_STREAM = "before_stream"
    AFTER_STREAM = "after_stream"
