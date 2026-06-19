import logging
import threading
_logger = logging.getLogger("event_bus")
from typing import Any, Callable, Dict, List, Optional


class SimpleEventBus:
    '''
    Simple in-process event bus.
    Replaces manual _safe_* methods with a unified event system.
    
    Events emitted:
    - agent.turn.start: Before agent processes a turn
    - agent.turn.complete: After agent completes a turn
    - agent.tool.call: When a tool is called
    - agent.tool.result: When a tool returns a result
    - agent.stream.token: Each token received during streaming
    - agent.stream.complete: When streaming finishes
    - agent.error: When an error occurs
    - settings.changed: When settings are updated
    '''
    
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}
        self._once_listeners: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()
    
    def on(self, event: str, callback: Callable) -> None:
        with self._lock:
            if event not in self._listeners:
                self._listeners[event] = []
            self._listeners[event].append(callback)
    
    def off(self, event: str, callback: Callable) -> None:
        with self._lock:
            if event in self._listeners:
                self._listeners[event] = [
                    cb for cb in self._listeners[event] if cb != callback
                ]
    
    def once(self, event: str, callback: Callable) -> None:
        with self._lock:
            if event not in self._once_listeners:
                self._once_listeners[event] = []
            self._once_listeners[event].append(callback)
    
    def emit(self, event: str, *args, **kwargs) -> None:
        callbacks = []
        once_callbacks = []
        
        with self._lock:
            if event in self._listeners:
                callbacks.extend(self._listeners[event])
            if event in self._once_listeners:
                once_callbacks.extend(self._once_listeners[event])
                del self._once_listeners[event]
        
        for cb in callbacks:
            try:
                cb(*args, **kwargs)
            except Exception as e:
                print(f"Event handler error for '{event}': {e}")
        
        for cb in once_callbacks:
            try:
                cb(*args, **kwargs)
            except Exception as e:
                print(f"Once handler error for '{event}': {e}")

