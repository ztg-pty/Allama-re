import logging
logger = logging.getLogger("api_client")

"""
API Client - Provider implementation for OpenAI-compatible APIs.
Implements the ProviderAdapter interface from the adapter layer.
"""

import json
import re
import urllib.request
import urllib.error
import time
from typing import Any, Dict, List, Optional

from .adapter.interfaces import ProviderAdapter


class AgentApiClient(ProviderAdapter):
    def __init__(self, base_url: str, api_key: str = "", model: str = "", deploy_manager=None):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._deploy_manager = deploy_manager
        self._model_cache = {}
        logger.info("AgentApiClient 初始化, base_url=%s, model=%s", self._base_url, model)
    
    def chat(self, messages: list, model: str = "", **kwargs) -> str:
        model_name = model or self._model
        logger.info("API chat 请求, model=%s, message_count=%d", model_name, len(messages))
        
        body = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4096),
        }
        data = json.dumps(body).encode("utf-8")
        url = f"{self._base_url}/v1/chat/completions"
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        if self._api_key:
            req.add_header("Authorization", f"Bearer {self._api_key}")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                text = self._parse_response(raw)
                logger.info("API chat 完成, 回复长度=%d", len(text))
                return text
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")
            logger.error("API chat HTTP错误: %s", body_text[:500])
            raise RuntimeError(f"HTTP {e.code}: {body_text[:500]}")
        except urllib.error.URLError as e:
            logger.error("API chat 连接失败: %s", e.reason)
            raise RuntimeError(f"Connection failed: {e.reason}")
        except Exception as e:
            logger.error("API chat 请求错误: %s", e)
            raise RuntimeError(f"Request error: {e}")
    
    def chat_stream(self, messages: list, model: str = "", **kwargs):
        model_name = model or self._model
        logger.info("API chat_stream 请求, model=%s, message_count=%d", model_name, len(messages))
        
        body = {
            "model": model_name,
            "messages": messages,
            "stream": True,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4096),
        }
        full_text = ""
        data = json.dumps(body).encode("utf-8")
        url = f"{self._base_url}/v1/chat/completions"
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        if self._api_key:
            req.add_header("Authorization", f"Bearer {self._api_key}")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                buffer = ""
                while True:
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    buffer += chunk.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                obj = json.loads(data_str)
                                delta = obj["choices"][0].get("delta", {})
                                token = delta.get("content", "")
                                if token:
                                    full_text += token
                                    yield token
                            except Exception:
                                pass
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")
            logger.error("API chat_stream HTTP错误: %s", body_text[:500])
            raise RuntimeError(f"HTTP {e.code}: {body_text[:500]}")
        
        logger.info("API chat_stream 完成, 总长度=%d", len(full_text))
        yield full_text
    
    def get_model_info(self, model: str = "") -> Dict[str, Any]:
        model_name = model or self._model
        if model_name in self._model_cache:
            return self._model_cache[model_name]
        
        info = {
            "model": model_name,
            "endpoint": self._base_url,
        }
        self._model_cache[model_name] = info
        return info
    
    def list_models(self) -> list:
        try:
            url = f"{self._base_url}/v1/models"
            req = urllib.request.Request(url, method="GET")
            if self._api_key:
                req.add_header("Authorization", f"Bearer {self._api_key}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
                return data.get("data", [])
        except Exception as e:
            logger.warning("list_models 失败: %s", e)
            if self._model:
                return [{"id": self._model, "name": self._model}]
            return []
    
    @staticmethod
    def _parse_response(raw: str) -> str:
        stripped = raw.strip()
        if stripped.startswith("data: "):
            text_parts = []
            for line in raw.split("\n"):
                line = line.strip()
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        continue
                    try:
                        obj = json.loads(data_str)
                        delta = obj.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            text_parts.append(content)
                    except Exception:
                        pass
            return "".join(text_parts)
        else:
            result = json.loads(stripped)
            return result["choices"][0]["message"]["content"]
