# Allama 日志解析 Skill

## 概述

本 Skill 用于解析和分析 Allama 应用的日志文件，识别关键错误、警告和性能指标。

## 功能

- 📊 解析日志文件
- 🔍 识别错误模式
- ⚠️ 检测警告信息
- 📈 统计关键指标
- 📝 生成分析报告

## 使用方法

### 基础用法

```bash
# 解析日志文件
python scripts/log_parser.py <log_file_path>

# 输出示例
=== Allama 日志分析报告 ===
总行数: 12345
错误数: 3
警告数: 12

错误详情:
1. CUDA OOM - 显存不足，请降低 -ngl 值
2. 模型加载失败 - 文件完整性检查
3. 端口被占用 - 已自动分配新端口

警告详情:
1. mlock 失败 - 系统将自动降级
2. Flash Attention 不支持 - 将自动禁用
```

### 高级用法

```bash
# 按级别过滤
python scripts/log_parser.py <log_file_path> --level ERROR

# 生成 JSON 格式报告
python scripts/log_parser.py <log_file_path> --format json

# 指定时间范围
python scripts/log_parser.py <log_file_path> --since "2024-06-01 00:00:00"

# 导出错误列表
python scripts/log_parser.py <log_file_path> --export errors.txt
```

## 错误模式识别

### 1. CUDA 错误

**模式**：
```
GGML_CUDA: mm_malloc failed
GGML: failed to allocate.*with size
CUDA error
```

**含义**：GPU 显存不足

**解决方案**：
- 降低 `-ngl` 参数值
- 使用更低精度的模型
- 减小上下文窗口大小

### 2. 模型加载错误

**模式**：
```
model_loader.*failed
llama_model_loader.*EOS token not found
```

**含义**：模型文件损坏或不完整

**解决方案**：
- 重新下载模型文件
- 检查文件完整性
- 使用校验和验证

### 3. 端口冲突

**模式**：
```
port .* already in use
bind.*Address already in use
```

**含义**：端口被占用

**解决方案**：
- 应用会自动分配新端口
- 检查是否有其他进程占用端口
- 手动关闭占用端口的进程

### 4. 上下文溢出

**模式**：
```
context size .* exceeded
```

**含义**：对话历史超出模型上下文限制

**解决方案**：
- 压缩对话历史
- 增大 `-c` 参数
- 减少 `keep_last` 参数

### 5. Flash Attention 错误

**模式**：
```
flash_attn.*not supported
```

**含义**：当前硬件不支持 Flash Attention

**解决方案**：
- 应用会自动禁用（不影响使用）
- 升级 CUDA 驱动
- 更换支持 Flash Attention 的 GPU

## 警告模式

### mlock 失败

**模式**：`mlock.*failed`

**含义**：内存锁定失败，系统将自动降级

**影响**：无，不影响使用

### Flash Attention 不支持

**模式**：`flash_attn.*not supported`

**含义**：当前硬件或 CUDA 版本不支持

**影响**：轻微性能下降

## 性能指标

### 推理性能

**指标**：
- 请求延迟
- Token 生成速度
- GPU 利用率

**查看方法**：
```bash
# 查找推理性能日志
grep "推理" RunTime/Debug/app.log

# 查找 token 生成速度
grep "tokens/s" RunTime/Debug/app.log
```

### 内存使用

**指标**：
- 显存占用
- 内存占用

**查看方法**：
```bash
# 查找内存相关日志
grep "内存" RunTime/Debug/app.log
```

### API 性能

**指标**：
- 请求响应时间
- 并发连接数

**查看方法**：
```bash
# 查找 API 请求日志
grep "Ollama API" RunTime/Debug/app.log
```

## 日志文件位置

### 开发模式

```
项目根目录/RunTime/Debug/app.log
```

### 打包模式

```
dist/Allama/RunTime/Debug/app.log
```

### Windows 事件日志

```bash
# 查看应用事件日志
eventvwr.msc
```

## 常见问题排查

### Q1: 日志文件过大

**问题**：日志文件超过 100MB

**解决方案**：
```bash
# 清理旧日志
Remove-Item "RunTime/Debug/app.log" -Force

# 或者限制日志大小
# 在 llama.py 中修改 MAX_LOG_LINES
```

### Q2: 日志内容乱码

**问题**：日志显示为乱码

**解决方案**：
```bash
# 使用 UTF-8 编码查看
Get-Content "RunTime/Debug/app.log" -Encoding UTF8 -Tail 50
```

### Q3: 日志丢失

**问题**：日志文件突然消失

**解决方案**：
1. 检查文件权限
2. 确认文件路径
3. 检查磁盘空间

## 集成到 Allama

### 自动日志解析

在 `llama.py` 中集成日志解析：

```python
import re
from datetime import datetime

ERROR_PATTERNS = [
    (r"GGML_CUDA: mm_malloc failed", "CUDA OOM", "error"),
    (r"model_loader.*failed", "模型加载失败", "error"),
    (r"port .* already in use", "端口冲突", "warn"),
    # ... 更多模式
]

def parse_log_line(line: str) -> Optional[tuple]:
    """解析单行日志"""
    for pattern, message, level in ERROR_PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            return (message, level)
    return None
```

### 日志分析报告

生成定期分析报告：

```python
def generate_log_report(log_path: str) -> dict:
    """生成日志分析报告"""
    errors = []
    warnings = []
    info_count = 0

    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            if 'ERROR' in line:
                errors.append(line.strip())
            elif 'WARN' in line:
                warnings.append(line.strip())
            elif 'INFO' in line:
                info_count += 1

    return {
        'total_lines': info_count + len(errors) + len(warnings),
        'errors': errors,
        'warnings': warnings,
        'info_count': info_count
    }
```

## 工具脚本

### 日志清理脚本

`scripts/clean_logs.py`:
```python
import os
from datetime import datetime, timedelta

LOG_DIR = "RunTime/Debug"
MAX_AGE_DAYS = 7

def clean_old_logs():
    """清理超过 N 天的日志文件"""
    cutoff = datetime.now() - timedelta(days=MAX_AGE_DAYS)

    for filename in os.listdir(LOG_DIR):
        filepath = os.path.join(LOG_DIR, filename)
        mtime = datetime.fromtimestamp(os.path.getmtime(filepath))

        if mtime < cutoff:
            os.remove(filepath)
            print(f"已删除: {filename}")
```

### 日志搜索脚本

`scripts/search_logs.py`:
```python
import sys
from datetime import datetime

def search_logs(log_path: str, keyword: str, since: str = None):
    """搜索日志文件"""
    cutoff = datetime.fromisoformat(since) if since else None

    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            if keyword.lower() in line.lower():
                if cutoff and datetime.fromisoformat(line.split()[0]) < cutoff:
                    continue
                print(line.strip())

if __name__ == "__main__":
    log_path = sys.argv[1]
    keyword = sys.argv[2]
    since = sys.argv[3] if len(sys.argv) > 3 else None

    search_logs(log_path, keyword, since)
```

## 扩展开发

### 自定义日志格式

```python
class CustomLogParser:
    """自定义日志解析器"""

    def __init__(self, log_path: str):
        self.log_path = log_path
        self._patterns = {}

    def register_pattern(self, pattern: str, level: str):
        """注册自定义模式"""
        self._patterns[pattern] = level

    def parse(self) -> dict:
        """解析日志"""
        results = {
            'errors': [],
            'warnings': [],
            'info': []
        }

        with open(self.log_path, 'r', encoding='utf-8') as f:
            for line in f:
                for pattern, level in self._patterns.items():
                    if re.search(pattern, line):
                        results[level].append(line.strip())
                        break

        return results
```

### 实时日志监控

```python
import time
import threading

class LogMonitor:
    """实时日志监控"""

    def __init__(self, log_path: str, callback):
        self.log_path = log_path
        self.callback = callback
        self._running = False
        self._thread = None
        self._last_position = 0

    def start(self):
        """开始监控"""
        self._running = True
        self._thread = threading.Thread(target=self._monitor, daemon=True)
        self._thread.start()

    def stop(self):
        """停止监控"""
        self._running = False

    def _monitor(self):
        """监控循环"""
        with open(self.log_path, 'r', encoding='utf-8') as f:
            f.seek(self._last_position)

            while self._running:
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    continue

                self._last_position = f.tell()
                self.callback(line.strip())
```

## 参考资源

- [Python logging 文档](https://docs.python.org/3/library/logging.html)
- [正则表达式教程](https://docs.python.org/3/library/re.html)
- [日志分析最佳实践](https://www.loggly.com/blog/beginners-guide-to-log-analysis/)
