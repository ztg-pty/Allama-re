# Allama 模型部署维护手册

## 概述

模型部署是 Allama 的核心功能，负责启动和管理 llama-server 进程，提供本地大模型推理服务。

## 部署流程

### 1. 准备模型文件

**格式要求**：
- 必须是 GGUF 格式
- 推荐量化版本：Q4_K_M, Q5_K_M, Q6_K

**模型下载**：
```bash
# 使用 Hugging Face
git clone https://huggingface.co/<model-repo>

# 或使用 llama.cpp 仓库
wget https://huggingface.co/ggerganov/llama.cpp/resolve/main/models/ggml-model-q4_k_m.gguf
```

**模型目录结构**：
```
models/
├── qwen2.5-coder-32b-instruct-q4_k_m.gguf
├── qwen2.5-coder-32b-instruct-q5_k_m.gguf
└── llama3.2-3b-instruct-q4_k_m.gguf
```

### 2. 配置模型路径

**方法一：通过 UI 配置**

1. 打开"模型部署"页面
2. 点击"添加模型"按钮
3. 选择 GGUF 文件
4. 选择视觉模型（可选）
5. 配置参数（上下文、GPU 层数等）
6. 点击"启动部署"

**方法二：直接编辑 settings.json**

```json
{
  "text_models": [
    "D:/models/qwen2.5-coder-32b-instruct-q4_k_m.gguf"
  ],
  "mmproj_models": [
    "D:/models/qwen2.5-coder-32b-instruct-mmproj-q4_k_m.gguf"
  ],
  "default_context": "8192",
  "default_ngl": "999",
  "default_n_predict": "4096"
}
```

### 3. 启动部署

**启动流程**：
1. 验证模型配置
2. 扫描可用端口
3. 生成临时启动脚本
4. 启动 llama-server 进程
5. 监控启动状态
6. 初始化 API 服务器

**启动命令示例**：
```batch
@echo off
chcp 65001 >nul
title Allama - qwen2.5-coder-32b-instruct
cd /d "%~dp0"

"C:\Users\admin\.openclaw\workspace\RunTime\llama-server.exe" ^
  -m "models\qwen2.5-coder-32b-instruct-q4_k_m.gguf" ^
  -ngl 999 ^
  --n-cpu-moe 0 ^
  -c 8192 ^
  -n 4096 ^
  --flash-attn on ^
  --parallel 1 ^
  --mlock ^
  --host 127.0.0.1 ^
  --port 8080
```

## 参数配置

### 基础参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-m` | 必填 | 模型文件路径 |
| `-ngl` | 999 | GPU 加载层数 |
| `-c` | 8192 | 上下文窗口大小 |
| `-n` | 4096 | 最大输出 token 数 |

### 高级参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--flash-attn` | on | Flash Attention 加速 |
| `--parallel` | 1 | 并行批处理数 |
| `--mlock` | 空 | 内存锁定（防交换） |
| `--host` | 127.0.0.1 | 监听地址 |
| `--port` | 8080 | 监听端口 |

### CPU MoE 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--n-cpu-moe` | 0 | CPU MoE 层数 |

**适用场景**：
- CPU MoE = 0：纯 GPU 推理
- CPU MoE = 25：CPU 和 GPU 混合推理

## 量化版本选择

### 推荐配置

| 模型大小 | 量化版本 | 推荐参数 |
|----------|----------|----------|
| < 7B | Q4_K_M | `-ngl 999 -c 8192` |
| 7B-13B | Q5_K_M | `-ngl 999 -c 16384` |
| 13B-30B | Q4_K_M | `-ngl 999 -c 8192` |
| > 30B | Q4_K_M | `-ngl 500 -c 4096` |

### 量化对比

| 量化 | 大小 | 质量 | 速度 | 推荐场景 |
|------|------|------|------|----------|
| Q4_K_M | ~70% | 高 | 快 | 通用场景 |
| Q5_K_M | ~80% | 很高 | 中 | 高质量需求 |
| Q6_K | ~85% | 极高 | 慢 | 精细任务 |
| Q8_0 | ~100% | 原始 | 最慢 | 离线评估 |

## 端口管理

### 默认端口

- **OpenAI 模式**：8080
- **Ollama 模式**：7890

### 端口冲突处理

**自动处理**：
- 检测端口占用
- 自动分配新端口
- 更新 UI 显示

**手动处理**：
```bash
# 查看端口占用
netstat -ano | findstr "8080"

# 查找占用进程
tasklist | findstr <PID>

# 终止进程
taskkill /PID <PID> /F
```

### 端口配置

在 `settings.json` 中修改默认端口：

```json
{
  "default_port": "8080"
}
```

## 多模型部署

### 同时部署多个模型

**限制**：
- 每次只能部署一个模型
- 部署新模型会自动停止当前模型

**切换模型**：
1. 停止当前模型
2. 选择新模型
3. 启动新模型

### 模型切换流程

```
用户选择新模型
    ↓
停止当前 llama-server
    ↓
清理临时脚本
    ↓
加载新模型配置
    ↓
生成新启动脚本
    ↓
启动新 llama-server
    ↓
更新 API 端点
```

## 视觉模型（多模态）

### 配置 mmproj

**文件要求**：
- 必须与文本模型配套
- 文件名包含 `mmproj` 关键字
- 格式为 GGUF

**配置步骤**：
1. 启用"视觉模型"复选框
2. 添加 mmproj 文件
3. 配置视觉参数

**参数说明**：
- `-ctk`：文本编码器（默认 q4_0）
- `-ctv`：视觉编码器（默认 q4_0）

### 视觉模型使用

**支持功能**：
- 图片理解
- 多模态对话
- 图像分析

**限制**：
- 需要配套的 mmproj 文件
- 首次加载较慢
- 显存占用增加

## 故障排查

### 问题 1：模型加载失败

**错误信息**：
```
model_loader.*failed
llama_model_loader.*EOS token not found
```

**原因**：
- 模型文件损坏
- 文件路径错误
- 文件权限不足

**解决方案**：
```bash
# 验证文件完整性
Get-FileHash models/qwen2.5-coder-32b-instruct-q4_k_m.gguf -Algorithm SHA256

# 检查文件大小
Get-Item models/qwen2.5-coder-32b-instruct-q4_k_m.gguf | Select-Object Length

# 重新下载模型
```

### 问题 2：CUDA OOM

**错误信息**：
```
GGML_CUDA: mm_malloc failed
```

**原因**：
- GPU 显存不足
- `-ngl` 参数过高
- 模型量化精度过高

**解决方案**：
```bash
# 降低 -ngl 参数
-ngl 500  # 从 999 降低

# 使用更低量化版本
qwen2.5-coder-32b-instruct-q5_k_m.gguf

# 减小上下文窗口
-c 4096
```

### 问题 3：端口冲突

**错误信息**：
```
port 8080 already in use
bind.*Address already in use
```

**原因**：
- 端口被其他进程占用
- 之前的 llama-server 未正常关闭

**解决方案**：
```bash
# 查找占用端口的进程
netstat -ano | findstr "8080"

# 终止进程
taskkill /PID <PID> /F

# 或在 Allama UI 中停止服务
```

### 问题 4：Flash Attention 不支持

**错误信息**：
```
flash_attn.*not supported
```

**原因**：
- GPU 不支持 Flash Attention
- CUDA 驱动版本过低

**影响**：
- 性能轻微下降
- 功能正常

**解决方案**：
```bash
# 检查 CUDA 版本
nvidia-smi

# 升级 CUDA 驱动
# 或禁用 Flash Attention
#（llama-server 会自动禁用）
```

## 性能优化

### GPU 性能优化

1. **调整 `-ngl` 参数**
   - GPU 显存充足：`-ngl 999`
   - 显存不足：`-ngl 500` 或更低

2. **启用 Flash Attention**
   - `--flash-attn on`
   - 加速推理速度 10-20%

3. **使用并行批处理**
   - `--parallel 2` 或更高
   - 提高吞吐量

### CPU 性能优化

1. **CPU MoE 配置**
   - 混合推理：`--n-cpu-moe 25`
   - 减轻 GPU 负担

2. **内存锁定**
   - `--mlock`
   - 防止内存交换

3. **线程优化**
   - 多线程推理
   - CPU 多核利用

### 网络性能优化

1. **API 响应优化**
   - 增大 `-n` 参数
   - 减少请求频率

2. **连接池**
   - 复用连接
   - 减少握手开销

## 监控和维护

### 进程监控

```bash
# 查看进程状态
Get-Process | Where-Object {$_.ProcessName -like "*llama-server*"}

# 查看 GPU 利用率
nvidia-smi

# 查看端口状态
netstat -ano | findstr "8080"
```

### 日志监控

**日志位置**：`RunTime/Debug/app.log`

**关键日志**：
- `llama-server 启动成功`
- `CUDA OOM`
- `模型加载失败`
- `端口冲突`

### 资源监控

**GPU 监控**：
```bash
# 实时监控
nvidia-smi -l 1

# 导出监控数据
nvidia-smi --query-gpu=timestamp,name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv -l 1 > gpu_stats.csv
```

**内存监控**：
```bash
# 查看进程内存
Get-Process | Where-Object {$_.ProcessName -like "*llama-server*"} | Select-Object Name,WorkingSet64
```

## 部署检查清单

### 部署前检查

- [ ] 模型文件存在且完整
- [ ] 模型格式为 GGUF
- [ ] 模型路径正确
- [ ] GPU 驱动已安装
- [ ] CUDA 版本兼容
- [ ] 端口未被占用

### 部署后验证

- [ ] llama-server 进程已启动
- [ ] 端口监听正常
- [ ] API 可访问
- [ ] 模型加载成功
- [ ] 推理正常工作

### 定期维护

- [ ] 检查日志文件大小
- [ ] 清理临时脚本
- [ ] 更新模型文件
- [ ] 优化参数配置
- [ ] 监控资源使用

## 扩展指南

### 自定义启动脚本

编辑 `RunTime/越狱版模型启动器.bat`：

```batch
@echo off
chcp 65001 >nul
title Allama - Custom Model

cd /d "%~dp0"

"C:\path\to\llama-server.exe" ^
  -m "models\my_custom_model.gguf" ^
  -ngl 999 ^
  -c 16384 ^
  -n 8192 ^
  --custom-flag value ^
  --another-flag ^
  --port 8080
```

### 多实例部署

**限制**：Allama 当前不支持多实例同时运行

**解决方案**：
- 使用不同端口部署多个实例
- 手动管理多个 llama-server 进程
- 考虑使用 Docker 容器化部署

### 远程部署

**SSH 部署**：
```bash
# 在远程服务器部署
ssh user@remote-server
cd /path/to/allama
python main.py
```

**端口转发**：
```bash
# 本地访问远程服务
ssh -L 8080:localhost:8080 user@remote-server
```

## 参考资源

- [llama.cpp 官方文档](https://github.com/ggerganov/llama.cpp)
- [GGUF 格式说明](https://github.com/ggerganov/ggml/blob/master/docs/GGUF.md)
- [llama-server 参数说明](https://github.com/ggerganov/llama.cpp/blob/master/examples/llama-server/README.md)
- [CUDA 性能优化](https://docs.nvidia.com/deploy/cuda-opt-guide/)
