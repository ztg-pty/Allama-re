import os
import sys
import re
import json
import time
import queue
import shutil
import socket
import random
import base64
import threading
import subprocess
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import logging

import psutil

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QPushButton, QStackedWidget, QComboBox, QLineEdit, QCheckBox,
    QPlainTextEdit, QLabel, QStatusBar, QFileDialog, QMessageBox, QDialog,
    QDialogButtonBox, QTextEdit,
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QUrl, QEvent
from PySide6.QtGui import QFont, QColor, QPalette, QIcon
from PySide6.QtWebEngineWidgets import QWebEngineView

# ============================================================
# 常量定义
# ============================================================
_FROZEN = getattr(sys, 'frozen', False)
if _FROZEN:
    _BUNDLE_DIR = Path(sys._MEIPASS)
    _EXE_DIR = Path(sys.executable).parent
else:
    _BUNDLE_DIR = Path(__file__).parent
    _EXE_DIR = Path(__file__).parent

RUNTIME_DIR = _BUNDLE_DIR / "RunTime"
BAT_TEMPLATE = _BUNDLE_DIR / "RunTime" / "越狱版模型启动器.bat"
LLAMA_SERVER_EXE = _BUNDLE_DIR / "RunTime" / "llama-server.exe"

TEMP_BAT_PREFIX = "TempDeploy_"
TEMP_BAT_DIR = _EXE_DIR / "RunTime"
MODELS_DIR = _EXE_DIR / "models"

OPENAI_DEFAULT_PORT = 8080
OLLAMA_DEFAULT_PORT = 7890

POLL_INTERVAL = 0.1
MAX_PORT_SEARCH = 50

# 网络常量
DEFAULT_BUFFER_SIZE = 65536
API_TIMEOUT = 600  # 秒
MAX_CONNECTIONS = 16

# 日志常量
MAX_LOG_LINES = 5000
LOG_FLUSH_INTERVAL = 80  # 毫秒

_logger = logging.getLogger("llama")
class AppSettings:
    _FILE = _EXE_DIR / "settings.json"
    _DEFAULTS = {
        "default_context": "8192",
        "default_ngl": "999",
        "default_n_predict": "4096",
        "stop_model_on_exit": True,
        "enable_mmproj_default": False,
        "text_models": [],
        "mmproj_models": [],
    }

    def __init__(self):
        self._data = dict(self._DEFAULTS)
        self._dirty = False
        self.load()

    def load(self):
        if self._FILE.exists():
            try:
                with open(self._FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self._data.update(loaded)
            except Exception:
                pass

    def save(self):
        if not self._dirty:
            return
        try:
            with open(self._FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            self._dirty = False
        except Exception:
            pass

    def get(self, key):
        return self._data.get(key, self._DEFAULTS.get(key))

    def set(self, key, value):
        self._data[key] = value
        self._dirty = True


# ============================================================
# 消息历史记录
# ============================================================
class MessageHistory:
    def __init__(self):
        self.messages = []

    def add_user(self, content: str):
        self.messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str):
        self.messages.append({"role": "assistant", "content": content})

    def get_history(self) -> list:
        return list(self.messages)

    def clear(self):
        self.messages = []

    def compress(self, keep_last: int = 6) -> int:
        removed = len(self.messages) - keep_last
        if removed > 0:
            self.messages = self.messages[-keep_last:]
        return removed

    def estimate_tokens(self) -> int:
        text = "\n".join(m.get("content", "") for m in self.messages)
        return max(1, len(text) // 4)


# ============================================================
# Bat 参数映射器
# ============================================================
class BatParamMapper:
    GENE_MAP = {
        "Q4_K_P": {
            "-c": "200000", "-n": "180000", "--n-cpu-moe": "25",
        },
        "Q4_K_M": {
            "-c": "256000", "-n": "200000", "--n-cpu-moe": "25",
        },
        "IQ4_NL": {
            "-c": "131072", "-n": "8192", "--n-cpu-moe": "25",
        },
        "IQ2_M": {
            "-c": "8192", "-n": "4096", "--n-cpu-moe": "0",
        },
    }

    DEFAULT_PARAMS = {
        "-c": "8192", "-n": "4096", "--n-cpu-moe": "0",
    }

    FIXED_PARAMS = {
        "-ctk": "q4_0",
        "-ctv": "q4_0",
        "--flash-attn": "on",
        "--parallel": "1",
        "--mlock": "",
        "--host": "127.0.0.1",
    }

    @classmethod
    def get_model_config(cls, filename: str) -> dict:
        """获取模型配置，根据文件名中的量化类型自动应用优化参数"""
        base_name = Path(filename).stem
        
        # 查找匹配的量化类型
        for qual_name, params in cls.GENE_MAP.items():
            if qual_name in base_name:
                final_model_name = base_name.replace("-" + qual_name, "")
                return cls._build_config(filename, final_model_name, base_name, params)
        
        # 默认配置
        return cls._build_config(filename, base_name, base_name, cls.DEFAULT_PARAMS)
    
    @classmethod
    def _build_config(cls, filename: str, final_name: str, display_name: str, base_params: dict) -> dict:
        """构建模型配置字典"""
        return {
            "model_path": filename,
            "model_name": final_name,
            "display_name": display_name,
            "fixed_params": dict(cls.FIXED_PARAMS),
            "base_params": base_params,
        }

    @classmethod
    def parse_bat_script(cls) -> list[dict]:
        if not BAT_TEMPLATE.exists():
            return []
        with open(BAT_TEMPLATE, "r", encoding="utf-8") as f:
            content = f.read()
        labels = re.findall(r":run\d+", content)
        segments = re.split(r":run\d+", content)
        results = []
        for seg in segments[1:]:
            seg = seg.strip()
            lines = seg.split("\n")
            cmd_lines = []
            for line in lines:
                line = line.strip()
                if line.startswith("llama-server.exe") or \
                   line.startswith("^") or \
                   (cmd_lines and not line.startswith("goto") and not line.startswith("set") and not line.startswith("echo") and not line.startswith("cls")):
                    cmd_lines.append(line)
            if not cmd_lines:
                continue
            full_cmd = " ".join(cmd_lines).replace("^\n", " ")
            model_path = ""
            mmproj_path = ""
            m = re.search(r'-m\s+"([^"]+)"', full_cmd)
            if m:
                model_path = m.group(1)
            m = re.search(r'--mmproj\s+"([^"]+)"', full_cmd)
            if m:
                mmproj_path = m.group(1)
            results.append({
                "model_path": model_path,
                "mmproj_path": mmproj_path,
                "cmd": full_cmd,
            })
        return results


# ============================================================
# 端口分配器
# ============================================================
class PortAllocator:
    def __init__(self):
        self._lock = threading.Lock()

    def is_port_in_use(self, port: int) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
                return False
        except OSError:
            return True

    def find_free_port(self, start_port: int) -> int:
        with self._lock:
            if not self.is_port_in_use(start_port):
                return start_port
            for offset in range(1, MAX_PORT_SEARCH + 1):
                candidate = start_port + offset
                if not self.is_port_in_use(candidate):
                    return candidate
            raise RuntimeError(f"无法找到空闲端口 (从 {start_port} 起搜索 {MAX_PORT_SEARCH} 次)")

    def get_effective_port(self, default_port: int) -> int:
        with self._lock:
            if not self.is_port_in_use(default_port):
                return default_port
            for offset in range(1, MAX_PORT_SEARCH + 1):
                candidate = default_port + offset
                if not self.is_port_in_use(candidate):
                    return candidate
            raise RuntimeError(f"无法找到空闲端口 (默认 {default_port})")


# ============================================================
# 临时 Bat 生成器
# ============================================================
class TempBatGenerator:
    @staticmethod
    def generate(model_config: dict, mmproj_config: Optional[dict],
                 user_params: dict, port: int) -> str:
        model_path_rel = TempBatGenerator._to_relative(model_config["model_path"])
        parts = ["@echo off", "chcp 65001 >nul",
                 f"title Allama - {model_config['display_name']}",
                 "cd /d \"%~dp0\"", "",
                 f"\"{LLAMA_SERVER_EXE}\" ^"]

        parts.append(f'  -m "{model_path_rel}" ^')

        if mmproj_config:
            mmproj_rel = TempBatGenerator._to_relative(mmproj_config["path"])
            parts.append(f'  --mmproj "{mmproj_rel}" ^')

        ngvl = user_params.get("-ngl", "999")
        parts.append(f"  -ngl {ngvl} ^")

        cpu_moe = user_params.get("--n-cpu-moe", model_config["base_params"].get("--n-cpu-moe", "0"))
        parts.append(f"  --n-cpu-moe {cpu_moe} ^")

        ctx = user_params.get("-c", model_config["base_params"].get("-c", "8192"))
        parts.append(f"  -c {ctx} ^")

        n_pred = user_params.get("-n", model_config["base_params"].get("-n", "4096"))
        parts.append(f"  -n {n_pred} ^")

        for k, v in model_config["fixed_params"].items():
            if v == "":
                parts.append(f"  {k} ^")
            else:
                parts.append(f"  {k} {v} ^")

        parts.append(f"  --port {port}")

        bat_content = "\n".join(parts) + "\n"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rand_suffix = hex(random.randint(0, 0xFFFF))[2:].upper()
        temp_bat_name = f"{TEMP_BAT_PREFIX}{timestamp}_{rand_suffix}.bat"
        temp_bat_path = TEMP_BAT_DIR / temp_bat_name
        TEMP_BAT_DIR.mkdir(parents=True, exist_ok=True)

        with open(temp_bat_path, "w", encoding="utf-8-sig") as f:
            f.write(bat_content)

        return str(temp_bat_path)

    @staticmethod
    def _to_relative(abs_path: str) -> str:
        try:
            rel = Path(abs_path).relative_to(TEMP_BAT_DIR)
            return str(rel).replace("\\", "\\\\")
        except ValueError:
            return abs_path.replace("\\", "\\\\")

    @staticmethod
    def cleanup(path: str):
        try:
            if path and Path(path).exists():
                os.remove(path)
        except Exception:
            pass


# ============================================================
# 错误特征匹配器
# ============================================================
ERROR_PATTERNS = [
    (r"GGML_CUDA: mm_malloc failed", "CUDA 显存不足，请降低 -ngl 值或选择低精度模型", "error_cuda_oom"),
    (r"GGML: failed to allocate.*with size", "显存分配失败，请尝试使用更小的模型", "error_allocate"),
    (r"model_loader.*failed", "模型文件加载失败，请检查文件完整性", "error_load"),
    (r"port .* already in use", "端口被占用，已自动分配新端口", "error_port"),
    (r"bind.*Address already in use", "端口被占用，已自动分配新端口", "error_port"),
    (r"mlock.*failed", "内存锁定失败，系统将自动降级（不影响使用）", "warn_mlock"),
    (r"context size .* exceeded", "上下文超出限制，请压缩对话历史或增大 -c 参数", "error_context"),
    (r"flash_attn.*not supported", "当前硬件或 CUDA 版本不支持 Flash Attention，将自动禁用", "warn_flash"),
    (r"llama_model_loader.*EOS token not found", "模型文件可能已损坏或不完整", "error_eos"),
    (r"CUDA error", "CUDA 错误，请检查 GPU 驱动和 CUDA 环境", "error_cuda"),
]


def match_error(log_line: str) -> Optional[tuple]:
    for pattern, message, code in ERROR_PATTERNS:
        if re.search(pattern, log_line, re.IGNORECASE):
            return (message, code)
    return None


# ============================================================
# 进程管理器
# ============================================================
class DeploymentManager:
    def __init__(self, log_callback, logger=None):
        self._process: Optional[subprocess.Popen] = None
        self._log_thread: Optional[threading.Thread] = None
        self._log_callback = log_callback
        self._logger = logger or _logger
        self._temp_bat_path = ""
        self._running = False
        self._stop_event = threading.Event()
        self._port_allocator = PortAllocator()
        self._effective_openai_port = OPENAI_DEFAULT_PORT
        self._effective_ollama_port = OLLAMA_DEFAULT_PORT
        self._current_model_config = None
        self._current_mmproj_config = None
        self._current_user_params = None
        self._current_port = OPENAI_DEFAULT_PORT
        self._error_detected = None
        self._lock = threading.Lock()
        self._model_params_cache = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def effective_openai_port(self) -> int:
        return self._effective_openai_port

    @property
    def effective_ollama_port(self) -> int:
        return self._effective_ollama_port

    @property
    def effective_port(self) -> int:
        return self._effective_openai_port

    def _emit(self, msg: str, level: str = "info"):
        try:
            self._log_callback(msg, level)
        except Exception:
            pass
        if level == "error":
            self._logger.error(msg)
        elif level == "warn":
            self._logger.warning(msg)
        elif level == "highlight":
            self._logger.info(msg)

    def start(self, model_config: dict, mmproj_config: Optional[dict],
              user_params: dict, base_port: int = OPENAI_DEFAULT_PORT) -> tuple:
        with self._lock:
            if self._running:
                return (False, "服务已在运行中，请先停止", "")

            self._stop_event.clear()
            self._error_detected = None
            self._current_model_config = model_config
            self._current_mmproj_config = mmproj_config
            self._current_user_params = user_params

            self._emit(f"正在扫描端口 (默认 {base_port})...", "info")

            try:
                port = self._port_allocator.get_effective_port(base_port)
                self._current_port = port
                self._effective_openai_port = port
            except RuntimeError as e:
                return (False, str(e), "")

            self._emit(f"使用端口: {port}", "info")

            try:
                self._temp_bat_path = TempBatGenerator.generate(
                    model_config, mmproj_config, user_params, port
                )
                self._emit(f"已生成临时脚本: {Path(self._temp_bat_path).name}", "info")
            except Exception as e:
                return (False, f"生成临时脚本失败: {e}", "")

            bat_dir = str(TEMP_BAT_DIR)
            cmd = [self._temp_bat_path]

            self._logger.info("启动 llama-server, 端口: %d", self._current_port)
            self._emit(f"正在启动 llama-server...", "info")

            try:
                self._process = subprocess.Popen(
                    cmd,
                    cwd=bat_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    encoding="utf-8",
                    errors="replace",
                )
            except Exception as e:
                self._logger.error("llama-server 启动失败: %s", e)
                return (False, f"启动失败: {e}", self._temp_bat_path)

            self._running = True
            self._log_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._log_thread.start()

            self._logger.info("llama-server 启动成功, 端口: %d", self._current_port)
            self._emit("=" * 70, "divider")
            self._emit("已启动，正在监听输出...", "info")

            return (True, f"服务已启动 (端口: {port})", self._temp_bat_path)

    def _monitor_loop(self):
        if not self._process or not self._process.stdout:
            return
        error_count = 0
        success_detected = False
        while not self._stop_event.is_set():
            line = self._process.stdout.readline()
            if not line:
                time.sleep(POLL_INTERVAL)
                if self._process.poll() is not None:
                    break
                error_count += 1
                if error_count > 50:
                    break
                continue
            error_count = 0
            line = line.strip()
            if not line:
                continue
            if self._stop_event.is_set():
                break
            if "listening on" in line.lower() or "llama server is ready" in line.lower():
                success_detected = True
            matched = match_error(line)
            if matched:
                msg, code = matched
                if code == "error_port":
                    self._error_detected = (msg, code)
                elif code == "warn_mlock" or code == "warn_flash":
                    self._emit(line, "warn")
                else:
                    self._emit(line, "error")
                    self._emit(f"  → {msg}", "highlight")
            else:
                self._emit(line, "normal")
        self._process.wait()
        self._running = False
        if self._error_detected:
            msg, code = self._error_detected
            self._emit(f"⚠ {msg}", "highlight")
            self._error_detected = None
            self._retry_with_new_port()
        elif not success_detected and self._process.returncode != 0:
            self._emit(f"❌ 服务异常退出 (退出码: {self._process.returncode})", "error")
        else:
            self._emit("✅ 服务已停止", "info")
        try:
            self._log_callback("__status_change__", "stop")
        except Exception:
            pass

    def _retry_with_new_port(self):
        if not self._current_model_config:
            return
        self._emit("正在尝试更换端口...", "warn")
        try:
            new_port = self._port_allocator.find_free_port(self._current_port + 1)
        except RuntimeError:
            self._emit("❌ 无法找到新的空闲端口", "error")
            return
        self._current_port = new_port
        self._effective_openai_port = new_port
        self._emit(f"尝试使用新端口: {new_port}", "info")
        try:
            new_bat = TempBatGenerator.generate(
                self._current_model_config,
                self._current_mmproj_config,
                self._current_user_params,
                new_port,
            )
        except Exception as e:
            self._emit(f"生成新脚本失败: {e}", "error")
            return
        if self._temp_bat_path:
            try:
                os.remove(self._temp_bat_path)
            except Exception:
                pass
        self._temp_bat_path = new_bat
        bat_dir = str(TEMP_BAT_DIR)
        try:
            self._process = subprocess.Popen(
                [new_bat],
                cwd=bat_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
            )
            self._emit("已用新端口重新拉起 llama-server", "info")
            self._logger.info("llama-server 启动成功, 端口: %d", self._current_port)
            self._emit("=" * 70, "divider")
        except Exception as e:
            self._emit(f"重启失败: {e}", "error")

    def stop(self) -> bool:
        with self._lock:
            if not self._running:
                return True
            self._logger.info("停止 llama-server")
            self._stop_event.set()
            if self._process:
                try:
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                except Exception:
                    pass
            self._running = False
            self._logger.info("llama-server 进程已终止")
            TempBatGenerator.cleanup(self._temp_bat_path)
            self._temp_bat_path = ""
            self._emit("✅ 服务已停止", "info")
            try:
                self._log_callback("__status_change__", "stop")
            except Exception:
                pass
            return True

    def get_build_cmd_string(self) -> str:
        if not self._current_model_config:
            return ""
        cfg = self._current_model_config
        p = self._current_user_params or {}
        parts = [f"\"{LLAMA_SERVER_EXE}\""]
        model_path_rel = TempBatGenerator._to_relative(cfg["model_path"])
        parts.append(f'  -m "{model_path_rel}"')
        if self._current_mmproj_config:
            mmproj_rel = TempBatGenerator._to_relative(self._current_mmproj_config["path"])
            parts.append(f'  --mmproj "{mmproj_rel}"')
        parts.append(f"  -ngl {p.get('-ngl', '999')}")
        cpu_moe = p.get("--n-cpu-moe", cfg["base_params"].get("--n-cpu-moe", "0"))
        parts.append(f"  --n-cpu-moe {cpu_moe}")
        ctx = p.get("-c", cfg["base_params"].get("-c", "8192"))
        parts.append(f"  -c {ctx}")
        n_pred = p.get("-n", cfg["base_params"].get("-n", "4096"))
        parts.append(f"  -n {n_pred}")
        for k, v in cfg["fixed_params"].items():
            if v == "":
                parts.append(f"  {k}")
            else:
                parts.append(f"  {k} {v}")
        parts.append(f"  --port {self._current_port or self._effective_openai_port}")
        return "\n".join(parts)


# ============================================================
# API 服务器 (Ollama 兼容)
# ============================================================
class ApiServer:
    def __init__(self, port: int, llama_port: int, model_name: str,
                 log_callback, logger=None):
        self.port = port
        self.llama_port = llama_port
        self.model_name = model_name
        self.log_callback = log_callback
        self._logger = logger or _logger
        self._logger.info("Ollama API 服务器初始化, 端口: %d", port)
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._stop_event = threading.Event()
        self._server_sock = None

    @property
    def is_running(self):
        return self._running

    def start(self):
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._stop_event.set()
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass

    def _run_loop(self):
        """服务器主循环"""
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.settimeout(1.0)
        
        try:
            self._server_sock.bind(("127.0.0.1", self.port))
            self._server_sock.listen(MAX_CONNECTIONS)
        except OSError as e:
            self._log(f"Ollama API 端口 {self.port} 绑定失败: {e}")
            return
        
        self._log(f"Ollama API 已启动于 http://localhost:{self.port}")
        
        while not self._stop_event.is_set():
            try:
                client_sock, addr = self._server_sock.accept()
                self._logger.debug("Ollama API 连接: %s:%d", addr[0], addr[1])
                threading.Thread(target=self._handle, args=(client_sock,), daemon=True).start()
            except OSError:
                break
        
        try:
            self._server_sock.close()
        except Exception:
            pass

    def _handle(self, client_sock: socket.socket):
        """处理客户端请求"""
        try:
            raw = client_sock.recv(DEFAULT_BUFFER_SIZE)
            self._logger.debug("收到客户端请求, 长度: %d bytes", len(raw) if raw else 0)
            if not raw:
                client_sock.close()
                return
            
            headers, body = raw.split(b"\r\n\r\n", 1) if b"\r\n\r\n" in raw else (raw, b"")
            header_lines = headers.split(b"\r\n")
            request_line = header_lines[0].decode("utf-8", errors="replace")
            parts = request_line.split(" ")
            
            if len(parts) < 2:
                client_sock.close()
                return
            
            path = parts[1]
            try:
                data = json.loads(body.decode("utf-8", errors="replace")) if body else {}
            except json.JSONDecodeError:
                data = {}
            
            path_lower = path.lower().rstrip("/")
            if path_lower in ("/api/chat", "/api/generate"):
                self._handle_llama(data, client_sock)
            elif path_lower == "/api/tags":
                self._handle_tags(client_sock)
            else:
                self._send(client_sock, 404, json.dumps({"error": "not found"}))
        except Exception as e:
            self._log(f"Ollama 请求处理错误: {e}")
        finally:
            try:
                client_sock.close()
            except Exception:
                pass

    def _handle_llama(self, data: dict, client_sock: socket.socket):
        """处理 /api/chat 和 /api/generate 请求"""
        model_name = data.get("model", self.model_name)
        self._logger.info("Ollama API 请求: model=%s, stream=%s, prompt_len=%d", model_name, data.get("stream", False), len(data.get("prompt", "")))
        
        conv_data = {
            "prompt": data.get("prompt", ""),
            "n_predict": data.get("n_predict", 2048),
            "temperature": data.get("temperature", 0.7),
            "stream": data.get("stream", False),
            "model": model_name
        }
        
        url = f"http://127.0.0.1:{self.llama_port}/generate"
        req = urllib.request.Request(url, data=json.dumps(conv_data).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
        
        try:
            with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
                result = json.loads(resp.read().decode("utf-8", errors="replace"))
            
            resp_data = {
                "model": model_name,
                "created_at": datetime.now().isoformat(),
                "message": result.get("content", ""),
                "done": True,
                "total_duration": result.get("tokens_evaluated", 1) * 1_000_000,
                "prompt_eval_count": result.get("prompt_tokens", 0),
                "eval_count": result.get("tokens_predicted", 0),
            }
            self._send(client_sock, 200, json.dumps(resp_data, ensure_ascii=False).encode("utf-8"))
        except urllib.error.URLError as e:
            self._log(f"llama-server 连接失败: {e}")
            self._send(client_sock, 502, b'{"error":"llama-server not available"}')

    def _handle_tags(self, client_sock):
        tags = {"models": [{"name": self.model_name, "model": self.model_name,
                           "modified_at": datetime.now().isoformat(), "size": 0,
                           "digest": "sha256:0" * 32}]}
        self._send(client_sock, 200, json.dumps(tags, ensure_ascii=False).encode("utf-8"))

    def _log(self, msg: str):
        """记录日志到 UI 和日志系统"""
        try:
            self.log_callback(msg, "info")
        except Exception:
            pass
        self._logger.info(msg)

    @staticmethod
    def _send(client_sock, status_code, body):
        status_text = {200: "OK", 404: "Not Found", 500: "Internal Server Error", 502: "Bad Gateway"}.get(status_code, "Unknown")
        response = f"HTTP/1.1 {status_code} {status_text}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode("utf-8") + body
        try:
            client_sock.sendall(response)
        except Exception:
            pass


# ============================================================
# 跨线程日志信号
# ============================================================
class _LogSignal(QObject):
    append = Signal(str, str)


# ============================================================
# 主应用窗口 - PySide6 重写
# ============================================================
class QtApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Allama")
        self.setFixedSize(1600, 800)
        self._center_window()

        self._text_models = []
        self._mmproj_models = []
        self._enable_mmproj = False
        self._llama_server_port = OPENAI_DEFAULT_PORT
        self._ollama_api = None
        self._current_model_config = None
        self._current_mmproj_config = None
        self._deploy_manager = None

        self._log_signal = _LogSignal()
        self._log_signal.append.connect(self._append_log_ui)

        self._log_buffer = []
        self._MAX_LOG_LINES = 5000
        self._log_flush_timer = QTimer(self)
        self._log_flush_timer.timeout.connect(self._flush_log_buffer)
        self._log_flush_timer.start(80)

        self._settings = AppSettings()
        self._init_ui()
        QTimer.singleShot(0, self._scan_models)

        import atexit
        atexit.register(self._cleanup)

        self._port_timer = QTimer(self)
        self._port_timer.timeout.connect(self._update_port_display)
        self._port_timer.start(5000)

        self._ollama_timer = QTimer(self)
        self._ollama_timer.timeout.connect(self._update_ollama_status)
        self._ollama_timer.start(5000)

    def _center_window(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move((screen.width() - 1600) // 2, (screen.height() - 800) // 2)

    # ---- UI 构建 --------------------------------------------------------

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet("background-color: #ffffff;")
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._sidebar = self._build_sidebar()
        layout.addWidget(self._sidebar)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_deploy_page())
        self._stack.addWidget(self._build_chat_page())
        self._stack.addWidget(self._build_settings_page())
        self._stack.addWidget(self._build_agent_page())
        layout.addWidget(self._stack)

        self._status_bar = QStatusBar()
        self._status_bar.setStyleSheet("background: #ffffff; color: #64748b;")
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("● 未部署")
        self._status_label.setStyleSheet("color: #64748b;")
        self._ollama_status_label = QLabel("Ollama API: 未启动")
        self._ollama_status_label.setStyleSheet("color: #64748b;")
        self._status_bar.addWidget(self._status_label)
        self._status_bar.addPermanentWidget(self._ollama_status_label)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setFixedWidth(200)
        sidebar.setObjectName("sidebar")
        sidebar.setStyleSheet("""
            QFrame#sidebar { background-color: #ffffff; border-right: 1px solid #e2e8f0; }
            QPushButton {
                background-color: transparent; color: #64748b;
                border: none; border-radius: 8px; padding: 12px 16px;
                text-align: left; font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(59,130,246,0.65); color: #ffffff;
            }
            QPushButton:checked { background-color: #eff6ff; color: #3b82f6; font-weight: bold; }
        """)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(20)

        self._btn_deploy = QPushButton("部署模型")
        self._btn_deploy.setCheckable(True)
        self._btn_deploy.setChecked(True)
        self._btn_deploy.clicked.connect(lambda: self._switch_page(0))

        self._btn_chat = QPushButton("聊天")
        self._btn_chat.setCheckable(True)
        self._btn_chat.clicked.connect(lambda: self._switch_page(1))

        self._btn_settings = QPushButton("设置")
        self._btn_settings.setCheckable(True)
        self._btn_settings.clicked.connect(lambda: self._switch_page(2))

        self._btn_agent = QPushButton("Agent 模式")
        self._btn_agent.setCheckable(True)
        self._btn_agent.clicked.connect(lambda: self._switch_page(3))

        layout.addWidget(self._btn_deploy)
        layout.addWidget(self._btn_chat)
        layout.addWidget(self._btn_settings)
        layout.addWidget(self._btn_agent)
        layout.addStretch()
        return sidebar

    def _switch_page(self, index: int):
        self._stack.setCurrentIndex(index)
        self._btn_deploy.setChecked(index == 0)
        self._btn_chat.setChecked(index == 1)
        self._btn_settings.setChecked(index == 2)
        self._btn_agent.setChecked(index == 3)

    # ---- 部署页 ----------------------------------------------------------

    def _build_deploy_page(self) -> QWidget:
        page = QWidget()
        main_layout = QVBoxLayout(page)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(8)

        style = """
            QComboBox { padding: 4px 8px; border: 1px solid #cbd5e1; border-radius: 6px;
                        background: #ffffff; font-size: 12px; }
            QComboBox:disabled { background: #f1f5f9; color: #94a3b8; }
            QLineEdit { padding: 4px 8px; border: 1px solid #cbd5e1; border-radius: 6px;
                        background: #ffffff; font-size: 12px; }
            QPlainTextEdit { border: 1px solid #e2e8f0; border-radius: 8px;
                             background: #1e293b; color: #cbd5e1; font-family: Consolas;
                             font-size: 11px; }
            QPushButton { border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: bold; }
            QCheckBox { font-size: 12px; }
        """
        page.setStyleSheet(style)

        title = QLabel("模型部署")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #1e293b;")
        main_layout.addWidget(title)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("文本模型:"))
        self._model_combo = QComboBox()
        self._model_combo.setMinimumWidth(420)
        self._model_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._model_combo.currentTextChanged.connect(self._on_model_select)
        row1.addWidget(self._model_combo)
        self._add_text_model_btn = QPushButton("添加模型 ▸")
        self._add_text_model_btn.setStyleSheet("""
            QPushButton { background: #ffffff; color: #22c55e; border: 1px solid #22c55e;
                          border-radius: 6px; padding: 4px 10px; font-size: 10px; font-weight: bold; }
            QPushButton:hover { background: #22c55e; color: #ffffff; }
        """)
        self._add_text_model_btn.clicked.connect(self._add_text_model)
        row1.addWidget(self._add_text_model_btn)
        row1.addSpacing(20)
        row1.addWidget(QLabel("视觉模型:"))
        self._mmproj_check = QCheckBox("启用")
        self._mmproj_check.toggled.connect(self._toggle_mmproj)
        row1.addWidget(self._mmproj_check)
        self._mmproj_combo = QComboBox()
        self._mmproj_combo.setMinimumWidth(300)
        self._mmproj_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._mmproj_combo.setEnabled(False)
        self._mmproj_combo.currentTextChanged.connect(self._on_mmproj_select)
        row1.addWidget(self._mmproj_combo)
        self._add_mmproj_model_btn = QPushButton("添加模型 ▸")
        self._add_mmproj_model_btn.setStyleSheet("""
            QPushButton { background: #ffffff; color: #22c55e; border: 1px solid #22c55e;
                          border-radius: 6px; padding: 4px 10px; font-size: 10px; font-weight: bold; }
            QPushButton:hover { background: #22c55e; color: #ffffff; }
        """)
        self._add_mmproj_model_btn.clicked.connect(self._add_mmproj_model)
        row1.addWidget(self._add_mmproj_model_btn)
        row1.addStretch()
        main_layout.addLayout(row1)

        self._model_list_widget = QWidget()
        self._model_list_layout = QVBoxLayout(self._model_list_widget)
        self._model_list_layout.setContentsMargins(0, 4, 0, 4)
        self._model_list_layout.setSpacing(4)
        main_layout.addWidget(self._model_list_widget)

        param_section = QFrame()
        param_section.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; }")
        param_layout = QVBoxLayout(param_section)
        param_header = QLabel("参数覆盖 (默认值来自 bat 档位):")
        param_header.setStyleSheet("color: #94a3b8; font-size: 11px;")
        param_layout.addWidget(param_header)
        param_row = QHBoxLayout()
        param_labels = [("上下文窗口 (-c)", "-c", "8192"),
                        ("最大输出 (-n)", "-n", "4096"),
                        ("GPU 层数 (-ngl)", "-ngl", "999"),
                        ("CPU MoE (--n-cpu-moe)", "--n-cpu-moe", "0")]
        self._param_edits = {}
        for label_text, key, default in param_labels:
            col = QVBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #94a3b8; font-size: 10px;")
            col.addWidget(lbl)
            edit = QLineEdit(default)
            self._param_edits[key] = edit
            col.addWidget(edit)
            param_row.addLayout(col)
        param_layout.addLayout(param_row)
        main_layout.addWidget(param_section)

        btn_row = QHBoxLayout()
        self._port_label = QLabel(f"端口: {OPENAI_DEFAULT_PORT}")
        self._port_label.setStyleSheet("color: #60a5fa; font-family: Consolas; font-size: 11px;")
        btn_row.addWidget(self._port_label)
        btn_row.addStretch()

        self._start_btn = QPushButton("启动部署")
        self._start_btn.setStyleSheet("background: #3b82f6; color: #fff;")
        self._start_btn.clicked.connect(self._start_deployment)
        btn_row.addWidget(self._start_btn)

        self._stop_btn = QPushButton("停止服务")
        self._stop_btn.setStyleSheet("""
            QPushButton { background: #ffffff; color: #ef4444; border: 1px solid #ef4444;
                          border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: bold; }
            QPushButton:hover { background: #ef4444; color: #ffffff; }
            QPushButton:disabled { border-color: #cbd5e1; color: #cbd5e1; }
        """)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_deployment)
        btn_row.addWidget(self._stop_btn)

        self._show_params_btn = QPushButton("查看参数")
        self._show_params_btn.setStyleSheet("""
            QPushButton { background: #ffffff; color: #3b82f6; border: 1px solid #3b82f6;
                          border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: bold; }
            QPushButton:hover { background: #3b82f6; color: #ffffff; }
            QPushButton:disabled { border-color: #cbd5e1; color: #cbd5e1; }
        """)
        self._show_params_btn.clicked.connect(self._show_params_dialog)
        btn_row.addWidget(self._show_params_btn)

        self._clear_log_btn = QPushButton("清空日志")
        self._clear_log_btn.setStyleSheet("""
            QPushButton { background: #ffffff; color: #64748b; border: 1px solid #cbd5e1;
                          border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: bold; }
            QPushButton:hover { background: #f1f5f9; color: #475569; }
            QPushButton:disabled { border-color: #cbd5e1; color: #cbd5e1; }
        """)
        self._clear_log_btn.clicked.connect(self._clear_log)
        btn_row.addWidget(self._clear_log_btn)
        main_layout.addLayout(btn_row)

        log_label = QLabel("部署日志")
        log_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #1e293b;")
        main_layout.addWidget(log_label)

        self._log_text = QPlainTextEdit()
        self._log_text.setReadOnly(True)
        main_layout.addWidget(self._log_text, 1)

        return page

    # ---- 聊天页 ----------------------------------------------------------

    def _build_chat_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        toolbar = QHBoxLayout()
        title = QLabel("聊天对话 (llama-ui)")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #1e293b;")
        toolbar.addWidget(title)
        toolbar.addStretch()

        self._chat_url_label = QLabel("")
        self._chat_url_label.setStyleSheet("color: #64748b; font-size: 11px;")
        toolbar.addWidget(self._chat_url_label)

        self._reload_btn = QPushButton("重新加载")
        self._reload_btn.setStyleSheet("""
            QPushButton { background: #ffffff; color: #3b82f6; border: 1px solid #3b82f6;
                          border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: bold; }
            QPushButton:hover { background: #3b82f6; color: #ffffff; }
        """)
        self._reload_btn.clicked.connect(self._reload_chat)
        toolbar.addWidget(self._reload_btn)

        self._browser_btn = QPushButton("在浏览器打开")
        self._browser_btn.setStyleSheet("""
            QPushButton { background: #ffffff; color: #3b82f6; border: 1px solid #3b82f6;
                          border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: bold; }
            QPushButton:hover { background: #3b82f6; color: #ffffff; }
        """)
        self._browser_btn.clicked.connect(self._open_in_browser)
        toolbar.addWidget(self._browser_btn)
        layout.addLayout(toolbar)

        self._webview = QWebEngineView()
        self._webview.setUrl(QUrl("about:blank"))
        self._webview.loadFinished.connect(self._on_webview_loaded)
        layout.addWidget(self._webview, 1)

        self._chat_status = QLabel("")
        self._chat_status.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(self._chat_status)

        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        style = """
            QLineEdit { padding: 4px 8px; border: 1px solid #cbd5e1; border-radius: 6px;
                        background: #ffffff; font-size: 12px; }
            QPlainTextEdit { border: 1px solid #e2e8f0; border-radius: 8px;
                             background: #1e293b; color: #cbd5e1; font-family: Consolas;
                             font-size: 11px; }
            QPushButton { border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: bold; }
            QCheckBox { font-size: 12px; }
        """
        page.setStyleSheet(style)

        title = QLabel("设置")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e293b;")
        layout.addWidget(title)

        # ---- 模型默认参数 ----
        param_group = QFrame()
        param_group.setObjectName("settingsGroup")
        param_group.setStyleSheet("QFrame#settingsGroup { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; }")
        param_layout = QVBoxLayout(param_group)
        param_layout.setSpacing(8)

        param_title = QLabel("模型默认参数")
        param_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #334155;")
        param_layout.addWidget(param_title)

        grid = QVBoxLayout()
        grid.setSpacing(6)

        ctx_row = QHBoxLayout()
        ctx_label = QLabel("上下文窗口 (-c)")
        ctx_label.setStyleSheet("font-size: 12px; color: #475569;")
        ctx_label.setFixedWidth(140)
        self._settings_ctx = QLineEdit()
        self._settings_ctx.setText(str(self._settings.get("default_context")))
        self._settings_ctx.textChanged.connect(lambda text: self._settings.set("default_context", text))
        ctx_row.addWidget(ctx_label)
        ctx_row.addWidget(self._settings_ctx)
        grid.addLayout(ctx_row)

        ngl_row = QHBoxLayout()
        ngl_label = QLabel("GPU 层数 (-ngl)")
        ngl_label.setStyleSheet("font-size: 12px; color: #475569;")
        ngl_label.setFixedWidth(140)
        self._settings_ngl = QLineEdit()
        self._settings_ngl.setText(str(self._settings.get("default_ngl")))
        self._settings_ngl.textChanged.connect(lambda text: self._settings.set("default_ngl", text))
        ngl_row.addWidget(ngl_label)
        ngl_row.addWidget(self._settings_ngl)
        grid.addLayout(ngl_row)

        n_row = QHBoxLayout()
        n_label = QLabel("最大输出 (-n)")
        n_label.setStyleSheet("font-size: 12px; color: #475569;")
        n_label.setFixedWidth(140)
        self._settings_n = QLineEdit()
        self._settings_n.setText(str(self._settings.get("default_n_predict")))
        self._settings_n.textChanged.connect(lambda text: self._settings.set("default_n_predict", text))
        n_row.addWidget(n_label)
        n_row.addWidget(self._settings_n)
        grid.addLayout(n_row)

        param_layout.addLayout(grid)
        layout.addWidget(param_group)

        # ---- 行为设置 ----
        behavior_group = QFrame()
        behavior_group.setObjectName("settingsGroup")
        behavior_group.setStyleSheet("QFrame#settingsGroup { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; }")
        behavior_layout = QVBoxLayout(behavior_group)
        behavior_layout.setSpacing(8)

        behavior_title = QLabel("行为设置")
        behavior_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #334155;")
        behavior_layout.addWidget(behavior_title)

        self._settings_stop_on_exit = QCheckBox("关闭程序时自动退出模型服务")
        self._settings_stop_on_exit.setChecked(self._settings.get("stop_model_on_exit"))
        self._settings_stop_on_exit.toggled.connect(lambda checked: self._settings.set("stop_model_on_exit", checked))
        behavior_layout.addWidget(self._settings_stop_on_exit)

        self._settings_mmproj = QCheckBox("默认启用视觉模型（部署时自动勾选）")
        self._settings_mmproj.setChecked(self._settings.get("enable_mmproj_default"))
        self._settings_mmproj.toggled.connect(lambda checked: self._settings.set("enable_mmproj_default", checked))
        behavior_layout.addWidget(self._settings_mmproj)
        layout.addWidget(behavior_group)

        layout.addStretch()

        restore_btn = QPushButton("恢复默认值")
        restore_btn.setStyleSheet("""
            QPushButton { background: #ffffff; color: #ef4444; border: 1px solid #ef4444;
                          border-radius: 6px; padding: 6px 14px; font-size: 11px; font-weight: bold; }
            QPushButton:hover { background: #ef4444; color: #ffffff; }
        """)
        restore_btn.clicked.connect(self._restore_defaults)
        layout.addWidget(restore_btn)

        return page

    def _build_agent_page(self) -> QWidget:
        from Agent.agent_wizard import AgentWizard
        from Agent.agent_chat import AgentChatWidget

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        self._agent_stack = QStackedWidget()
        deploy_port = self._deploy_manager.effective_openai_port if self._deploy_manager else 11434
        self._agent_wizard = AgentWizard(
            on_configured=self._on_agent_configured,
            deploy_port=deploy_port,
        )
        self._agent_chat = None
        self._agent_stack.addWidget(self._agent_wizard)
        layout.addWidget(self._agent_stack)
        return page

    def _on_agent_configured(self, config: dict):
        from Agent.agent_chat import AgentChatWidget
        from Agent.api_client import AgentApiClient

        client = AgentApiClient(
            base_url=config["base_url"],
            api_key=config.get("api_key", ""),
            model=config["model"],
            deploy_manager=self._deploy_manager,
        )
        self._agent_chat = AgentChatWidget(client)
        self._agent_stack.addWidget(self._agent_chat)
        self._agent_stack.setCurrentIndex(1)

    def _restore_defaults(self):
        from copy import deepcopy
        self._settings._data.update(deepcopy(AppSettings._DEFAULTS))
        self._settings.save()
        self._settings_ctx.blockSignals(True)
        self._settings_ngl.blockSignals(True)
        self._settings_n.blockSignals(True)
        self._settings_stop_on_exit.blockSignals(True)
        self._settings_mmproj.blockSignals(True)
        self._settings_ctx.setText(str(self._settings.get("default_context")))
        self._settings_ngl.setText(str(self._settings.get("default_ngl")))
        self._settings_n.setText(str(self._settings.get("default_n_predict")))
        self._settings_stop_on_exit.setChecked(self._settings.get("stop_model_on_exit"))
        self._settings_mmproj.setChecked(self._settings.get("enable_mmproj_default"))
        self._settings_ctx.blockSignals(False)
        self._settings_ngl.blockSignals(False)
        self._settings_n.blockSignals(False)
        self._settings_stop_on_exit.blockSignals(False)
        self._settings_mmproj.blockSignals(False)
        self._scan_models()

    def _on_webview_loaded(self, ok: bool):
        if ok:
            self._chat_status.setText("llama-ui 已嵌入")
            self._chat_status.setStyleSheet("color: #22c55e; font-size: 11px;")
        else:
            self._chat_status.setText("页面加载失败")
            self._chat_status.setStyleSheet("color: #ef4444; font-size: 11px;")

    def _launch_embed(self):
        port = self._deploy_manager.effective_openai_port
        url = f"http://127.0.0.1:{port}"
        self._webview.setUrl(QUrl(url))
        self._chat_url_label.setText(f"http://127.0.0.1:{port}")
        self._chat_status.setText("正在加载 llama-ui...")

    def _reload_chat(self):
        self._webview.reload()

    def _open_in_browser(self):
        import webbrowser
        port = self._deploy_manager.effective_openai_port if self._deploy_manager else OPENAI_DEFAULT_PORT
        webbrowser.open(f"http://127.0.0.1:{port}")

    # ---- 模型扫描 --------------------------------------------------------

    def _scan_models(self):
        stored_text = self._settings.get("text_models") or []
        stored_mmproj = self._settings.get("mmproj_models") or []
        self._text_models = []
        for path in stored_text:
            p = Path(path)
            if p.exists():
                self._text_models.append({
                    "path": str(p),
                    "filename": p.name,
                    "size": p.stat().st_size,
                    "is_mmproj": False,
                })
        self._mmproj_models = []
        for path in stored_mmproj:
            p = Path(path)
            if p.exists():
                self._mmproj_models.append({
                    "path": str(p),
                    "filename": p.name,
                    "size": p.stat().st_size,
                    "is_mmproj": True,
                })
        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        if self._text_models:
            names = [self._get_display_name(m) for m in self._text_models]
            self._model_combo.addItems(names)
            self._model_combo.setCurrentIndex(0)
            self._on_model_select_internal(self._text_models[0])
        else:
            self._model_combo.addItem("未找到模型")
        self._model_combo.blockSignals(False)
        self._mmproj_combo.blockSignals(True)
        self._mmproj_combo.clear()
        if self._mmproj_models:
            mmnames = [self._get_display_name(m) for m in self._mmproj_models]
            self._mmproj_combo.addItems(mmnames)
            self._mmproj_combo.setEnabled(True)
        else:
            self._mmproj_combo.addItem("无可用视觉模型")
            self._mmproj_combo.setEnabled(False)
        self._mmproj_combo.blockSignals(False)
        if self._settings.get("enable_mmproj_default") and self._mmproj_models:
            self._mmproj_check.setChecked(True)
        self._refresh_model_list_display()

    def _add_text_model(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择文本模型", "", "GGUF 模型 (*.gguf)"
        )
        if not paths:
            return
        added = []
        for p in paths:
            if "mmproj" in Path(p).name.lower():
                continue
            stored = self._settings.get("text_models") or []
            if p not in stored:
                stored.append(p)
                added.append(p)
        self._settings.set("text_models", stored)
        self._refresh_model_list_display()
        QTimer.singleShot(100, self._scan_models)

    def _add_mmproj_model(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "添加视觉模型", "", "GGUF 模型 (*.gguf)"
        )
        if not paths:
            return
        stored = self._settings.get("mmproj_models") or []
        for p in paths:
            if p not in stored:
                stored.append(p)
        self._settings.set("mmproj_models", stored)
        self._refresh_model_list_display()
        QTimer.singleShot(100, self._scan_models)

    def _remove_text_model(self, path):
        stored = self._settings.get("text_models") or []
        stored = [p for p in stored if p != path]
        self._settings.set("text_models", stored)
        self._refresh_model_list_display()
        QTimer.singleShot(100, self._scan_models)

    def _remove_mmproj_model(self, path):
        stored = self._settings.get("mmproj_models") or []
        stored = [p for p in stored if p != path]
        self._settings.set("mmproj_models", stored)
        self._refresh_model_list_display()
        QTimer.singleShot(100, self._scan_models)

    def _refresh_model_list_display(self):
        while self._model_list_layout.count():
            child = self._model_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        all_models = []
        for m in self._text_models:
            all_models.append(("text", m))
        for m in self._mmproj_models:
            all_models.append(("mmproj", m))
        if not all_models:
            label = QLabel("选择模型")
            label.setStyleSheet("color: #94a3b8; font-size: 11px;")
            self._model_list_layout.addWidget(label)
            return
        for model_type, info in all_models:
            row = QHBoxLayout()
            row.setContentsMargins(0, 2, 0, 2)
            filename = Path(info["path"]).name
            size_gb = info.get("size", 0) / (1024 ** 3)
            type_label = QLabel(f"[{'文本' if model_type == 'text' else '视觉'}] {filename}")
            type_label.setStyleSheet("color: #475569; font-size: 11px;")
            row.addWidget(type_label)
            size_label = QLabel(f"({size_gb:.1f} GB)")
            size_label.setStyleSheet("color: #94a3b8; font-size: 10px;")
            row.addWidget(size_label)
            row.addStretch()
            remove_btn = QPushButton("选择模型")
            remove_btn.setStyleSheet("""
                QPushButton { background: #ffffff; color: #ef4444; border: 1px solid #ef4444;
                              border-radius: 4px; padding: 2px 8px; font-size: 10px; font-weight: bold; }
                QPushButton:hover { background: #ef4444; color: #ffffff; }
            """)
            if model_type == "text":
                remove_btn.clicked.connect(lambda _, p=info["path"]: self._remove_text_model(p))
            else:
                remove_btn.clicked.connect(lambda _, p=info["path"]: self._remove_mmproj_model(p))
            row.addWidget(remove_btn)
            widget = QWidget()
            widget.setLayout(row)
            self._model_list_layout.addWidget(widget)

    def _on_model_select(self, text: str):
        for m in self._text_models:
            if self._get_display_name(m) == text:
                self._on_model_select_internal(m)
                return

    def _on_model_select_internal(self, model_info):
        config = BatParamMapper.get_model_config(model_info["path"])
        self._current_model_config = config
        default_params = config["base_params"]
        self._param_edits["-c"].setText(str(default_params.get("-c", self._settings.get("default_context"))))
        self._param_edits["-n"].setText(str(default_params.get("-n", self._settings.get("default_n_predict"))))
        self._param_edits["-ngl"].setText(self._settings.get("default_ngl"))
        self._param_edits["--n-cpu-moe"].setText(str(default_params.get("--n-cpu-moe", "0")))
        if self._mmproj_models and self._enable_mmproj:
            self._mmproj_combo.setCurrentText(self._get_display_name(self._mmproj_models[0]))

    def _toggle_mmproj(self, checked: bool):
        self._enable_mmproj = checked
        if checked:
            if self._mmproj_models:
                self._mmproj_combo.setEnabled(True)
                self._mmproj_combo.setCurrentIndex(0)
            else:
                self._mmproj_combo.setEnabled(False)
                self._enable_mmproj = False
                self._mmproj_check.setChecked(False)
        else:
            self._mmproj_combo.setEnabled(False)

    def _on_mmproj_select(self, text: str):
        pass

    def _get_display_name(self, model_info) -> str:
        name = model_info.get("display_name", model_info.get("name", model_info.get("filename", "")))
        size_gb = model_info.get("size", 0) / (1024 ** 3)
        return f"{name}  ({size_gb:.1f} GB)"

    def _get_user_params(self) -> dict:
        params = {}
        for key in ("-c", "-n", "--n-cpu-moe", "-ngl"):
            edit = self._param_edits.get(key)
            if edit:
                val = edit.text().strip()
                if val:
                    params[key] = val
        return params

    # ---- 部署控制 --------------------------------------------------------

    def _start_deployment(self):
        if not self._current_model_config:
            QMessageBox.critical(self, "错误", "请先选择文本模型")
            return
        if self._enable_mmproj and not self._mmproj_models:
            QMessageBox.critical(self, "错误", "未找到可用的视觉模型")
            return
        mmproj_info = None
        if self._enable_mmproj:
            selected_name = self._mmproj_combo.currentText().strip()
            mmproj_info = None
            for m in self._mmproj_models:
                if self._get_display_name(m) == selected_name:
                    mmproj_info = m
                    break
            if not mmproj_info:
                QMessageBox.critical(self, "错误", "请选择视觉模型")
                return

        user_params = self._get_user_params()
        self._deploy_manager = DeploymentManager(self._append_log, _logger)
        result = self._deploy_manager.start(
            self._current_model_config, mmproj_info, user_params, OPENAI_DEFAULT_PORT)
        success, msg, bat_path = result
        if success:
            self._llama_server_port = self._deploy_manager.effective_port
            self._start_ollama_api()
            self._update_ui_after_start()
            self._append_log("部署成功!", "highlight")
            self._append_log(
                f"   OpenAI API: http://localhost:{self._deploy_manager.effective_openai_port}",
                "highlight")
            self._append_log(
                f"   Ollama API: http://localhost:{self._deploy_manager.effective_ollama_port}",
                "highlight")
            self._launch_embed()
        else:
            QMessageBox.critical(self, "部署失败", msg)
            self._append_log(f"{msg}", "error")

    def _stop_deployment(self):
        if self._deploy_manager:
            self._deploy_manager.stop()
        if self._ollama_api:
            self._ollama_api.stop()
            self._ollama_api = None
        self._update_ui_after_stop()
        self._append_log("服务已停止", "info")

    def _update_ui_after_start(self):
        self._start_btn.setEnabled(False)
        self._start_btn.setText("部署中...")
        self._stop_btn.setEnabled(True)
        self._model_combo.setEnabled(False)
        self._status_label.setText("● 运行中")
        self._status_label.setStyleSheet("color: #22c55e;")

    def _update_ui_after_stop(self):
        self._start_btn.setEnabled(True)
        self._start_btn.setText("启动部署")
        self._stop_btn.setEnabled(False)
        self._model_combo.setEnabled(True)
        self._status_label.setText("● 未部署")
        self._status_label.setStyleSheet("color: #64748b;")

    def _update_port_display(self):
        port = OPENAI_DEFAULT_PORT
        if self._deploy_manager and self._deploy_manager.is_running:
            port = self._deploy_manager.effective_openai_port
        self._port_label.setText(f"端口: {port}")

    def _update_ollama_status(self):
        status = "未启动"
        color = "#64748b"
        if self._deploy_manager and self._deploy_manager.is_running:
            if self._ollama_api and self._ollama_api.is_running:
                status = f"运行中 (端口: {self._ollama_api.port})"
                color = "#22c55e"
            else:
                status = f"等待启动 (端口: {OLLAMA_DEFAULT_PORT})"
                color = "#f59e0b"
        self._ollama_status_label.setText(f"Ollama API: {status}")
        if not hasattr(self, '_last_ollama_color') or self._last_ollama_color != color:
            self._last_ollama_color = color
            self._ollama_status_label.setStyleSheet(f"color: {color};")

    def _start_ollama_api(self):
        try:
            ollama_port = PortAllocator().get_effective_port(OLLAMA_DEFAULT_PORT)
            model_name = "qwen3.6-a3b"
            if self._current_model_config:
                model_name = self._current_model_config.get("model_name", model_name)
            self._ollama_api = ApiServer(
                port=ollama_port,
                llama_port=self._llama_server_port,
                model_name=model_name,
                log_callback=self._append_log,
                logger=_logger,
            )
            self._ollama_api.start()
        except Exception as e:
            self._append_log(f"Ollama API 启动失败: {e}", "error")

    # ---- 日志 ------------------------------------------------------------

    def _append_log(self, msg: str, level: str = "normal"):
        self._log_signal.append.emit(msg, level)

    def _append_log_ui(self, msg: str, level: str = "normal"):
        if msg == "__status_change__":
            if self._deploy_manager and not self._deploy_manager.is_running:
                self._update_ui_after_stop()
            return
        self._log_buffer.append((msg, level))

    def _flush_log_buffer(self):
        if not self._log_buffer:
            return
        doc = self._log_text.document()
        entries = self._log_buffer
        self._log_buffer = []
        cursor = self._log_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        for msg, level in entries:
            time_str = datetime.now().strftime("%H:%M:%S")
            prefix = f"[{time_str}] "
            if level == "highlight":
                cursor.insertHtml(
                    f'<span style="color:#22c55e;">{prefix}  &gt;&gt;&gt; {msg} &lt;&lt;&lt;</span><br>')
            elif level == "error":
                cursor.insertHtml(
                    f'<span style="color:#ef4444;">{prefix}  ✗ {msg}</span><br>')
            elif level == "warn":
                cursor.insertHtml(
                    f'<span style="color:#f59e0b;">{prefix}  ⚠ {msg}</span><br>')
            elif level == "divider":
                cursor.insertHtml(
                    f'<span style="color:#334155;">{msg}</span><br>')
            else:
                cursor.insertText(f"{prefix}{msg}\n")
        excess = doc.blockCount() - self._MAX_LOG_LINES
        if excess > 0:
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor, excess)
            cursor.removeSelectedText()
        self._log_text.setTextCursor(cursor)

    def _show_params_dialog(self):
        if not self._deploy_manager:
            QMessageBox.information(self, "启动参数", "当前未部署模型")
            return
        cmd = self._deploy_manager.get_build_cmd_string()
        port = self._deploy_manager.effective_openai_port
        text = f"生效端口: {port}\n\n启动命令:\n{cmd}"
        dlg = QDialog(self)
        dlg.setWindowTitle("启动参数详情")
        dlg.resize(600, 400)
        layout = QVBoxLayout(dlg)
        edit = QPlainTextEdit()
        edit.setPlainText(text)
        edit.setReadOnly(True)
        edit.setStyleSheet("font-family: Consolas; font-size: 11px;")
        layout.addWidget(edit)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btns.accepted.connect(dlg.accept)
        layout.addWidget(btns)
        dlg.exec()

    def _clear_log(self):
        self._log_text.clear()

    # ---- 生命周期 --------------------------------------------------------

    def closeEvent(self, event):
        self._settings.save()
        if self._settings.get("stop_model_on_exit"):
            if self._deploy_manager:
                self._deploy_manager.stop()
            if self._ollama_api:
                self._ollama_api.stop()
        event.accept()

    def _cleanup(self):
        self._settings.save()
        if not self._settings.get("stop_model_on_exit"):
            return
        if self._deploy_manager:
            self._deploy_manager.stop()
        if self._ollama_api:
            self._ollama_api.stop()
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if proc.info["name"] and "llama-server" in proc.info["name"].lower():
                    proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        try:
            for f in TEMP_BAT_DIR.glob(f"{TEMP_BAT_PREFIX}*.bat"):
                f.unlink(missing_ok=True)
        except Exception:
            pass


# ============================================================
# 全局实例
# ============================================================
_app_instance = None
_deploy_manager_instance = None


def get_deploy_manager():
    global _deploy_manager_instance
    if _deploy_manager_instance is None:
        _deploy_manager_instance = DeploymentManager(lambda msg, level="normal": None)
    return _deploy_manager_instance


# ============================================================
# 入口
# ============================================================
def main():
    global _app_instance
    qt_app = QApplication(sys.argv)
    qt_app.setStyle("Fusion")
    window = QtApp()
    _app_instance = window
    window.show()
    sys.exit(qt_app.exec())


if __name__ == "__main__":
    main()