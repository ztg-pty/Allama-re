# Allama 维护手册

## 📚 手册索引

### 📖 核心文档

- **[模型部署维护手册](./MODEL_DEPLOYMENT.md)** - 模型加载、参数配置、故障排查
- **[Agent 插件维护手册](./AGENT_MANUAL.md)** - Agent 系统、工具调用、扩展开发

### 🔧 技能文档（Skills）

- **[日志解析 Skill](./skills/log-parser.md)** - 日志分析、错误识别、性能监控

## 📋 快速导航

### 新手入门

1. **模型部署** → [MODEL_DEPLOYMENT.md](./MODEL_DEPLOYMENT.md)
   - 如何下载和配置模型
   - 基础参数说明
   - 常见问题解决

2. **启动应用** → [MODEL_DEPLOYMENT.md#启动部署](./MODEL_DEPLOYMENT.md#启动部署)
   - UI 操作指南
   - 命令行启动方式

### 进阶使用

1. **Agent 模式** → [AGENT_MANUAL.md](./AGENT_MANUAL.md)
   - Agent 系统架构
   - 工具调用机制
   - 自定义工具开发

2. **性能优化** → [MODEL_DEPLOYMENT.md#性能优化](./MODEL_DEPLOYMENT.md#性能优化)
   - GPU 优化策略
   - CPU 优化策略
   - 网络性能调优

### 故障排查

1. **模型问题** → [MODEL_DEPLOYMENT.md#故障排查](./MODEL_DEPLOYMENT.md#故障排查)
   - 模型加载失败
   - CUDA OOM 错误
   - 端口冲突

2. **Agent 问题** → [AGENT_MANUAL.md#故障排查](./AGENT_MANUAL.md#故障排查)
   - 工具调用失败
   - 上下文溢出
   - API 连接问题

3. **日志分析** → [skills/log-parser.md](./skills/log-parser.md)
   - 错误模式识别
   - 性能指标监控
   - 日志清理策略

## 📂 文档结构

```
docs/
├── GUIDE.md                          # 本文件 - 手册索引
├── MODEL_DEPLOYMENT.md                # 模型部署维护手册
├── AGENT_MANUAL.md                   # Agent 插件维护手册
├── AGENT_PLUGIN.md                   # Agent 模型部署手册
└── skills/
    └── log-parser.md                  # 日志解析 Skill
```

## 🔍 按主题查找

### 部署相关
- [模型配置](./MODEL_DEPLOYMENT.md#2-配置模型路径)
- [参数配置](./MODEL_DEPLOYMENT.md#参数配置)
- [端口管理](./MODEL_DEPLOYMENT.md#端口管理)
- [多模型部署](./MODEL_DEPLOYMENT.md#多模型部署)

### Agent 相关
- [Agent Loop](./AGENT_MANUAL.md#1-agent-loop-agent_looppy)
- [工具执行](./AGENT_MANUAL.md#3-tool-executor-tool_executorpy)
- [API 客户端](./AGENT_MANUAL.md#4-api-client-api_clientpy)
- [系统提示词](./AGENT_MANUAL.md#系统提示词)

### 日志相关
- [错误模式](./skills/log-parser.md#错误模式识别)
- [性能指标](./skills/log-parser.md#性能指标)
- [日志清理](./skills/log-parser.md#日志清理脚本)

## 🛠️ 常用命令

### 查看日志
```bash
# 查看最新日志
Get-Content "RunTime/Debug/app.log" -Tail 50

# 搜索错误
Select-String -Path "RunTime/Debug/app.log" -Pattern "ERROR"

# 导出错误列表
Select-String -Path "RunTime/Debug/app.log" -Pattern "ERROR" | Out-File errors.txt
```

### 检查端口
```bash
# 查看端口占用
netstat -ano | findstr "8080"

# 查找 llama-server 进程
tasklist | findstr "llama-server"
```

### 监控 GPU
```bash
# 实时监控
nvidia-smi -l 1

# 导出监控数据
nvidia-smi --query-gpu=timestamp,name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv -l 1 > gpu_stats.csv
```

### 清理日志
```bash
# 清理旧日志（7天前）
$age = (Get-Date) - (New-TimeSpan -Days 7)
Get-ChildItem "RunTime/Debug" | Where-Object {$_.LastWriteTime -lt $age} | Remove-Item
```

## 📞 获取帮助

### 在线资源
- [llama.cpp GitHub](https://github.com/ggerganov/llama.cpp)
- [Allama 项目仓库](https://github.com/your-repo/allama)
- [PySide6 文档](https://www.qt.io/pyside6)

### 获取支持
1. 查阅对应主题的手册
2. 搜索日志文件查找错误
3. 查看常见问题（FAQ）
4. 提交 Issue 到项目仓库

## 🔄 文档更新

### 维护计划
- **定期更新**：每季度
- **重大版本**：同步更新
- **Bug 修复**：即时更新

### 贡献文档
欢迎提交文档改进建议！

1. Fork 项目仓库
2. 创建文档改进分支
3. 提交 Pull Request

## 📝 版本历史

- **v1.0** (2026-06-20)
  - 初始版本
  - 添加模型部署手册
  - 添加 Agent 插件手册
  - 添加日志解析 Skill

## 📄 许可证

本文档遵循 Allama 项目的主许可证（MIT License）

---

**最后更新**：2026-06-20
**文档版本**：v1.0
**维护者**：Allama 开发团队
