# Plan: Add Runtime Logging to runtime/Debug

## Goal
Add centralized application logging that saves to runtime/Debug folder, with real-time console output.

## Analysis
- Project: PySide6 desktop app (llama.py) + Agent modules (Agent/)
- Entry: main.py → llama.py
- Existing logs: in-memory Qt buffer only (_append_log), no file persistence
- Components needing log integration: DeploymentManager, ApiServer, AgentLoop, AgentApiClient

## Implementation Steps

### 1. Create untime/logger.py
- Centralized Python logging module
- Creates runtime/Debug/ directory (relative to project root)
- Handlers:
  - RotatingFileHandler → runtime/Debug/app.log (10MB max, 5 backups)
  - StreamHandler → stdout (console)
- Format: [YYYY-MM-DD HH:MM:SS] [LEVEL] message
- get_logger(name) factory function
- Thread-safe

### 2. Create untime/__init__.py
- Package init

### 3. Update main.py
- Import logging init at startup

### 4. Update llama.py
- Replace ad-hoc log callbacks with logger in DeploymentManager and ApiServer

### 5. Update Agent modules
- Agent/core/agent_loop.py - agent turn lifecycle logging
- Agent/api_client.py - API request logging
