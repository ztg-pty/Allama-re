# Allama Agent Infrastructure Maintenance Manual

---

## Document Info

| Item | Value |
|------|-------|
| Project | Allama — Local LLM Desktop Application |
| Framework | PySide6 + llama.cpp |
| Core Python Files | `llama.py`, `main.py`, `Agent/` |
| Runtime Binaries | `RunTime/` (llama.cpp binaries/DLLs, excluded from modifications) |
| Config File | `settings.json` |
| Log Files | `RunTime/Debug/app.log` |
| Python Module | `_runtime/` (contains `logger.py` for log initialization) |

---

## 1. Runtime Node Inventory

Based on code analysis of `llama.py`, the following independent runtime nodes exist:

| # | Node | Process Type | Default Port | Host File | Thread Model |
|---|------|-------------|-------------|-----------|--------------|
| N1 | `QtApp` UI Main Thread | PySide6 GUI | — | `llama.py` | Qt Event Loop |
| N2 | `DeploymentManager` / `llama-server` | subprocess | 8080 (auto-increment) | `llama.py` | C++ llama.cpp |
| N3 | `ApiServer` (Ollama Proxy) | socket TCP | 7890 (auto-increment) | `llama.py` | Per-connection Thread |
| N4 | `_log_thread` | threading | — | `llama.py` | Daemon Thread |
| N5 | `AgentLoop` (Background) | threading | — | `Agent/core/agent_loop.py` | Daemon Thread |
| N6 | `PortAllocator` | in-memory | — | `llama.py` | Thread-safe (Lock) |
| N7 | `Timer` Components | QTimer | — | `llama.py` | Qt Timers |

---

## 2. Node N1: QtApp UI Main Thread

### 2.1 Health Check

```powershell
# Check if Allama process is running
Get-Process python* -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -match "Allama" } | Select-Object Id, MainWindowTitle

# Check Python process memory
Get-Process python* -ErrorAction SilentlyContinue | Select-Object Id, WorkingSet64, CPU

# Check Qt event loop responsiveness (non-blocking)
# Open Allama UI; if mouse clicks respond within 2s, event loop is healthy
```

### 2.2 Log Location

| Source | Path |
|--------|------|
| File logger | `RunTime/Debug/app.log` (via `_runtime/logger.py` module) |
| UI log buffer | In-memory, max 5000 lines (`_MAX_LOG_LINES`), flushed every 80ms |

### 2.3 Common Issues

#### UI freezes or unresponsive

```powershell
# 1. Check for stuck Qt timer (port_timer / ollama_timer at 5s intervals)
# If UI is frozen, force close and restart:
Stop-Process -Name "python*" -Where { $_.MainWindowTitle -match "Allama" } -Force

# 2. Check if RunTime/Debug/app.log shows any Python errors
Get-Content "RunTime/Debug/app.log" -Tail 50

# 3. If QWebEngineView is stuck, check WebView2 process:
Get-Process "WebView2*" -ErrorAction SilentlyContinue
```

**Recovery Steps:**
1. Close Allama via status bar "Stop Service" button first (triggers `_stop_deployment()`)
2. If unresponsive, `Stop-Process` the Python process
3. Delete stale BAT files: `Remove-Item "RunTime\TempDeploy_*.bat" -ErrorAction SilentlyContinue`
4. Restart: `python main.py` or execute `dist\Allama\Allama.exe`

---

## 3. Node N2: llama-server (DeploymentManager)

### 3.1 Health Check

```powershell
# Check if llama-server is listening on the configured port (default 8080)
netstat -ano | Select-String ":8080"
netstat -ano | Select-String ":808[0-9]"

# Check llama-server process
Get-Process llama-server -ErrorAction SilentlyContinue | Select-Object Id, CPU, WorkingSet64

# Check if the HTTP endpoint responds
curl -s http://127.0.0.1:8080/generate -Method POST -ContentType "application/json" -Body '{"prompt":"test","n_predict":10}'

# Verify via Ollama proxy
curl -s http://127.0.0.1:7890/api/tags
```

### 3.2 Log Location

| Source | Path | Key Markers |
|--------|------|-------------|
| UI Deployment Log | In-memory (QPlainTextEdit) | `[HH:MM:SS]` prefix, `>>> ... <<<` for highlights |
| File Log | `RunTime/Debug/app.log` | Module `llama`, function `DeploymentManager` |
| llama-server stdout | Captured by subprocess PIPE | Contains "listening on", "GGML", "CUDA" |

### 3.3 Common Issues

#### 3.3.1 CUDA Out of Memory

**Symptom:** Log shows `GGML_CUDA: mm_malloc failed` or `GGML: failed to allocate`

**Recovery:**
1. Open Allama Settings page
2. Reduce `-ngl` (GPU layers) value, e.g., from 999 to 50 or 30
3. Click "Stop Service", then "Start Deployment" again
4. Alternatively, select a smaller quantized model

```powershell
# Check GPU memory usage
nvidia-smi

# If GPU memory is full, kill stale llama-server:
Get-Process llama-server | Stop-Process -Force
```

#### 3.3.2 Port Conflict

**Symptom:** Log shows `port XXXX already in use` or `bind: Address already in use`

**Recovery:**
1. DeploymentManager auto-detects and tries next port (searches up to 50 ports forward)
2. Manual check:
```powershell
netstat -ano | Select-String ":808[0-9]"
# Find PID, then:
Get-Process -Id <PID> | Stop-Process -Force
```
3. Delete stale temp BAT scripts:
```powershell
Remove-Item "RunTime\TempDeploy_*.bat" -ErrorAction SilentlyContinue
```

#### 3.3.3 Model Loading Failure

**Symptom:** Log shows `model_loader.*failed` or `EOS token not found`

**Recovery:**
1. Verify model file integrity:
```powershell
Test-Path "models\*.gguf"
# Check file size matches expected
Get-ChildItem "models\*.gguf" | Select-Object Name, Length
```
2. Re-download model if corrupted
3. In settings, remove the bad model path and re-add

#### 3.3.4 Context Size Exceeded

**Symptom:** Log shows `context size XXXX exceeded`

**Recovery:**
1. In Deployment page, increase `-c` (context window) value
2. Or compress conversation history (Agent mode)
3. Default is 8192; increase based on available RAM/GPU memory

---

## 4. Node N3: ApiServer (Ollama Proxy)

### 4.1 Health Check

```powershell
# Check Ollama proxy port (default 7890)
netstat -ano | Select-String ":789[0-9]"

# Check Ollama API endpoint
curl -s http://127.0.0.1:7890/api/tags | ConvertFrom-Json

# Check chat endpoint
curl -s http://127.0.0.1:7890/api/chat -Method POST -ContentType "application/json" -Body '{"model":"test","messages":[{"role":"user","content":"hi"}],"stream":false}'

# Verify proxy forwards to llama-server
curl -s http://127.0.0.1:7890/api/generate -Method POST -ContentType "application/json" -Body '{"model":"test","prompt":"hello","stream":false}'
```

### 4.2 Log Location

| Source | Path | Key Markers |
|--------|------|-------------|
| UI Deployment Log | In-memory (QPlainTextEdit) | `Ollama API 已启动于 http://localhost:7890` |
| File Log | `RunTime/Debug/app.log` | Module `llama`, log level INFO |

### 4.3 Common Issues

#### 4.3.1 Ollama Port Unavailable

**Symptom:** UI status bar shows `Ollama API: 等待启动 (端口: 7890)` in amber

**Recovery:**
1. Check if port 7890 is occupied:
```powershell
netstat -ano | Select-String ":7890"
```
2. ApiServer auto-allocates next available port (searches up to 50 ports)
3. Check status bar for actual allocated port number
4. If all ports exhausted:
```powershell
# Find and kill processes on ports 7890-7939
for ($i = 0; $i -lt 50; $i++) {
    $port = 7890 + $i
    $conn = netstat -ano | Select-String ":$port "
    if ($conn) {
        $pid = ($conn -split '\s+')[-1]
        if ($pid -match '^\d+$') { Get-Process -Id $pid -ErrorAction SilentlyContinue }
    }
}
```

#### 4.3.2 502 Bad Gateway

**Symptom:** Client receives `{"error":"llama-server not available"}` from Ollama proxy

**Recovery:**
1. Verify llama-server (Node N2) is running: `netstat -ano | Select-String ":808[0-9]"`
2. If llama-server is down, restart from Deployment page
3. If llama-server is running but proxy fails, check proxy log for `llama-server 连接失败`

#### 4.3.3 Proxy Thread Exhaustion

**Symptom:** New Ollama API connections are slow or timing out

**Details:** ApiServer spawns a new daemon thread per connection (`threading.Thread(target=self._handle, ...)`)

**Recovery:**
1. Restart Allama to clean up stale threads:
```powershell
Stop-Process -Name "python*" -Where { $_.MainWindowTitle -match "Allama" } -Force
python main.py
```

---

## 5. Node N5: AgentLoop (Agent Mode)

### 5.1 Health Check

```powershell
# AgentLoop runs inside the Python process; check via UI:
# 1. Open Agent page (Agent 模式 button in sidebar)
# 2. Configure service address, model name via wizard
# 3. Send a test message
# 4. Observe if tool bubbles (ToolCallBubble / ToolResultBubble) appear
# 5. If response appears, AgentLoop is healthy

# Check AgentApiClient endpoint connectivity
curl -s http://127.0.0.1:7890/v1/chat/completions -Method POST -ContentType "application/json" -Body '{"model":"test","messages":[{"role":"user","content":"test"}],"stream":false}'
```

### 5.2 Log Location

| Source | Path | Key Markers |
|--------|------|-------------|
| Agent Chat UI | In-scroll-area bubbles | ToolCallBubble (blue), ToolResultBubble (green) |
| File Log | `RunTime/Debug/app.log` | Module `agent_loop`, `api_client`, `tool_executor` |
| Agent EventBus | In-memory | Events: `agent.turn.start`, `agent.tool.call`, `agent.tool.result`, `agent.error` |

### 5.3 Common Issues

#### 5.3.1 Agent Loop Stuck (Infinite Tool Execution)

**Symptom:** Agent keeps calling the same tool repeatedly

**Recovery:**
1. Check `MAX_TOOL_ROUNDS` limit (default: 10) in `Agent/agent_chat.py`
2. If loop exceeds 10 rounds, it auto-stops
3. For debugging, open file log and search for `agent_loop`:
```powershell
Select-String "agent_loop" "RunTime/Debug/app.log" | Select-Object -Last 30
```
4. Kill the stuck AgentApiClient request (120s timeout) by sending a new message

#### 5.3.2 Tool Execution Timeout

**Symptom:** `execute_command` returns "Command execution timed out (60s)"

**Recovery:**
1. In Agent UI, uncheck "Allow command execution" to prevent execution
2. Check command output in `RunTime/Debug/app.log`
3. Identify stuck process:
```powershell
Get-Process | Where-Object { $_.CPU -gt 100 } | Select-Object Name, Id, CPU
```

#### 5.3.3 Tool Call Parse Failure

**Symptom:** Agent responds with text but tools are not recognized

**Debug:**
1. Check the raw model response in file log
2. Verify tool call format matches: `<name>tool_name</name><params>{"key": "value"}</params>`
3. Regex: `r'<name>(.*?)</name><params>(\{.*?\})</params>'`
4. If JSON params are malformed, fallback to case-insensitive match

#### 5.3.4 AgentApiClient Connection Failed

**Symptom:** Error message "Connection failed: ..." in Agent UI

**Recovery:**
1. Verify the configured base_url is reachable:
```powershell
curl -s http://127.0.0.1:7890/api/tags
```
2. If using localhost Ollama API, verify Ollama proxy is running: `netstat -ano | Select-String ":789[0-9]"`
3. If using remote API, check network connectivity:
```powershell
Test-NetConnection <remote-host> -Port 443
```
4. Verify API key in Agent wizard configuration

---

## 6. Node N6: PortAllocator

### 6.1 Health Check

```powershell
# Check all relevant ports in use
netstat -ano | Select-String ":808[0-9]|:789[0-9]"

# List all Python processes and their listening ports
Get-Process python* | ForEach-Object {
    $id = $_.Id
    netstat -ano | Select-String " $id$"
}
```

### 6.2 Port Allocation Logic

| Component | Default Port | Search Range | Allocation Method |
|-----------|-------------|-------------|-------------------|
| OpenAI API / llama-server | 8080 | 8080-8129 (50 ports) | Sequential first-free |
| Ollama API proxy | 7890 | 7890-7939 (50 ports) | Sequential first-free |

### 6.3 Recovery: Force Free Port

```powershell
# Find process on port 8080
$port = 8080
$conn = netstat -ano | Select-String ":$port "
if ($conn) {
    $pid = ($conn -split '\s+')[-1]
    Get-Process -Id $pid
    Stop-Process -Id $pid -Force
}

# Verify port is free
netstat -ano | Select-String ":$port "
```

---

## 7. Node N7: QTimer Components

### 7.1 Timer Inventory

| Timer | Interval | Purpose | File |
|-------|----------|---------|------|
| `_log_flush_timer` | 80ms | Flush in-memory log buffer to UI | `llama.py` QtApp |
| `_port_timer` | 5s | Update port display in status bar | `llama.py` QtApp |
| `_ollama_timer` | 5s | Update Ollama API status | `llama.py` QtApp |

### 7.2 Health Check

No direct command; check UI status bar:
- Port display updates every 5s
- Ollama status updates every 5s (green/amber/grey)

### 7.3 Recovery

If timers are not firing (UI static):
1. Check if Qt event loop is blocked (see Node N1)
2. Restart Allama

---

## 8. Configuration Maintenance

### 8.1 settings.json

Location: `settings.json` (same directory as `main.py`)

```json
{
  "default_context": "8192",
  "default_ngl": "999",
  "default_n_predict": "4096",
  "stop_model_on_exit": true,
  "enable_mmproj_default": false,
  "text_models": ["D:/path/to/model.gguf"],
  "mmproj_models": ["D:/path/to/mmproj.gguf"]
}
```

**Recovery Steps:**
1. To reset all settings: delete `settings.json`, restart Allama (defaults re-applied)
2. To update model paths: edit `settings.json` directly or use Settings page in UI
3. To change default parameters: use Settings page -> Model Default Parameters

### 8.2 Temp BAT Scripts

Location: `RunTime/TempDeploy_*.bat`

**Cleanup:**
```powershell
# List temp scripts
Get-ChildItem "RunTime\TempDeploy_*.bat"

# Delete all stale temp scripts
Remove-Item "RunTime\TempDeploy_*.bat" -Force

# Note: DeploymentManager.cleanup() removes the active temp BAT on stop
```

---

## 9. Troubleshooting Decision Tree

```
Allama Not Starting
├── Python missing? → pip install PySide6 psutil
├── RunTime/llama-server.exe missing? → Re-extract runtime binaries
└── settings.json corrupt? → Delete settings.json

llama-server Won't Start
├── Port 8080 in use? → Check netstat, kill process, or restart (auto-allocates new port)
├── CUDA OOM? → Reduce -ngl in Deployment page
├── Model file missing? → Add model via "Add Text Model" button
├── Context size exceeded? → Increase -c or compress history
└── GGUF parse error? → Re-download model

Ollama Proxy Won't Start
├── Port 7890 in use? → Auto-allocates next available port
└── llama-server not running? → Start deployment first

Agent Mode Not Working
├── Ollama proxy down? → Check status bar, start deployment
├── Model not specified? → Complete AgentWizard Step 3
├── Tool calls not parsed? → Check log for raw model response format
└── Tool execution timeout? → Check command output in log

Agent Loop Stuck
├── > 10 tool rounds? → Auto-stops; reduce model's tool usage tendency
├── Tool execution hanging? → Kill stuck subprocess: Get-Process -Id <PID>
└── API returning empty? → Verify endpoint with curl -s http://127.0.0.1:7890/api/tags
```

---

## 10. Emergency Procedures

### 10.1 Full System Reset

```powershell
# 1. Stop all Python processes
Stop-Process -Name "python*" -Force -ErrorAction SilentlyContinue

# 2. Kill any lingering llama-server processes
Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force

# 3. Clean temp files
Remove-Item "RunTime\TempDeploy_*.bat" -Force -ErrorAction SilentlyContinue

# 4. Clean log
Clear-Content "RunTime/Debug/app.log" -ErrorAction SilentlyContinue

# 5. Restart
python main.py
```

### 10.2 GPU Memory Leak Recovery

```powershell
# Check current GPU memory
nvidia-smi

# If GPU memory is not released by llama.cpp, kill all CUDA processes:
Get-Process llama-server | Stop-Process -Force
# Then restart Allama
python main.py
```

### 10.3 Log File Rotation

- Log rotation is configured with `maxBytes=10MB`, `backupCount=5`
- Log files are written to `RunTime/Debug/app.log`
- Old logs: `app.log.1` through `app.log.5`

```powershell
# Check log size
Get-ChildItem "RunTime/Debug/" | Select-Object Name, Length

# Manually rotate if needed
Copy-Item "RunTime/Debug/app.log" "RunTime/Debug/app.log.$(Get-Date -Format 'yyyyMMdd')"
Clear-Content "RunTime/Debug/app.log"
```

---

## 11. Quick Reference: Default Values

| Parameter | Default | Override Location |
|-----------|---------|-------------------|
| OpenAI API Port | 8080 | `OPENAI_DEFAULT_PORT` in `llama.py` |
| Ollama API Port | 7890 | `OLLAMA_DEFAULT_PORT` in `llama.py` |
| Max Port Search | 50 | `MAX_PORT_SEARCH` in `llama.py` |
| Log Flush Interval | 80ms | `_log_flush_timer.start(80)` in `llama.py` |
| Port Check Interval | 5s | `_port_timer.start(5000)` in `llama.py` |
| Max Log Lines | 5000 | `_MAX_LOG_LINES` in `llama.py` |
| Agent Max Tool Rounds | 10 | `MAX_TOOL_ROUNDS` in `Agent/agent_chat.py` |
| Tool Cmd Timeout | 60s | `subprocess.run(..., timeout=60)` in `tool_executor.py` |
| API Request Timeout | 120s | `urlopen(req, timeout=120)` in `api_client.py` |
| Ollama Proxy Timeout | 600s | `urlopen(req, timeout=600)` in `llama.py` |

---

> **已生成文档：`agents.md` 与 `OPS_ALLAMA_AGENT_INFRA.md`**
> **已阅读项目代码，本次文档撰写严格规避 _runtime/llama.cpp 底层文件。**
