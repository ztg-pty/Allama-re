import json
import threading
from typing import Any, Dict, Optional
from pathlib import Path
from .interfaces import LoggerAdapter, StorageAdapter, ProviderAdapter


class QtLoggerAdapter(LoggerAdapter):
    '''
    Qt signal-based logging adapter.
    Bridges to Qt event loop for thread-safe UI updates.
    '''
    
    def __init__(self, log_callback=None):
        self._log_callback = log_callback
        self._level = "info"
    
    def debug(self, message: str, **kwargs):
        self.log("debug", message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self.log("info", message, **kwargs)
    
    def warn(self, message: str, **kwargs):
        self.log("warn", message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self.log("error", message, **kwargs)
    
    def log(self, level: str, message: str, **kwargs):
        if self._log_callback:
            try:
                self._log_callback(message, level)
            except Exception:
                pass


class FileStorageAdapter(StorageAdapter):
    '''
    File-based storage adapter using JSON.
    Equivalent to Cline's FileAdapter.
    '''
    
    def __init__(self, storage_dir: Path):
        self._storage_dir = storage_dir
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cache = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._cache.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._cache[key] = value
    
    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
    
    def keys(self) -> list:
        with self._lock:
            return list(self._cache.keys())
    
    def save_session(self, session_id: str, data: Dict) -> None:
        with self._lock:
            self._cache[session_id] = data
        session_file = self._storage_dir / f"session_{session_id}.json"
        try:
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def load_session(self, session_id: str) -> Optional[Dict]:
        session_file = self._storage_dir / f"session_{session_id}.json"
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    
    def list_sessions(self) -> list:
        sessions = []
        try:
            for f in self._storage_dir.glob("session_*.json"):
                sessions.append(f.stem.replace("session_", ""))
        except Exception:
            pass
        return sessions


class InMemoryStorageAdapter(StorageAdapter):
    '''
    Simple in-memory storage adapter.
    Good for testing or ephemeral sessions.
    '''
    
    def __init__(self):
        self._data = {}
        self._lock = threading.Lock()
    
    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
    
    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._data:
                del self._data[key]
                return True
            return False
    
    def clear(self) -> None:
        with self._lock:
            self._data.clear()
    
    def keys(self) -> list:
        with self._lock:
            return list(self._data.keys())
    
    def save_session(self, session_id: str, data: Dict) -> None:
        with self._lock:
            self._data[f"session:{session_id}"] = data
    
    def load_session(self, session_id: str) -> Optional[Dict]:
        with self._lock:
            return self._data.get(f"session:{session_id}")
    
    def list_sessions(self) -> list:
        with self._lock:
            return [k.replace("session:", "") for k in self._data.keys() if k.startswith("session:")]
