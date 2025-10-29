# 修复说明：Glider 代理空回复问题

## 问题描述
用户报告使用 `curl -x http://IP:26026 http://ip.sb` 时收到空响应，代理无法正常工作。

## 根本原因
之前的代码将 glider 进程的 stdout 和 stderr 都重定向到 `/dev/null`（DEVNULL），导致：
1. 无法看到 glider 的错误信息和日志输出
2. 无法诊断 glider 为什么无法正常转发请求
3. 如果 glider 启动失败或遇到配置错误，用户完全无法知晓

## 修复内容

### 1. 启用 glider 日志输出 (`proxychain/glider_manager.py`)
- 将 glider 进程的 stdout/stderr 从 DEVNULL 改为 PIPE
- 添加 `_log_glider_output()` 方法，在独立线程中读取 glider 输出
- 所有 glider 日志会实时显示，格式为：`glider[端点ID前8位]: 消息内容`

### 2. 增强配置日志
- 在 DEBUG 日志级别下，会完整打印生成的 glider 配置文件内容
- 方便验证配置是否正确

### 3. 更新 README 文档
添加了"故障排查"章节，包含：
- 如何查看 glider 日志
- 如何设置 DEBUG 日志级别
- 常见问题和解决方法
- 测试单个代理端点的命令示例

## 使用方法

### Docker 环境
```bash
# 查看完整日志（包括 glider 输出）
docker compose logs -f

# 重启容器应用新版本
docker compose down
docker compose up -d
```

### 本地环境
```bash
# 以 DEBUG 级别启动，查看详细配置
LOG_LEVEL=DEBUG uvicorn proxychain.main:app --host 0.0.0.0 --port 8000
```

## 预期效果
启动后，日志中会显示：
```
INFO:proxychain.glider_manager:Started glider endpoint 729d76c4:http (http:26026)
INFO:proxychain.glider_manager:glider[729d76c4]: 2024/01/15 10:00:00 listen.go:123 HTTP proxy listening on http://0.0.0.0:26026
INFO:proxychain.glider_manager:glider[729d76c4]: 2024/01/15 10:00:05 proxy.go:456 dial ss://example.com:443 via forwarder...
```

如果有错误（如后端节点连接失败），也会在日志中显示，帮助快速定位问题。

## 下一步诊断建议
1. 重新部署后查看日志，找到 `glider[...]` 开头的日志行
2. 如果看到连接错误，可能是订阅中的节点失效
3. 如果看到 "listen failed" 或 "bind: address already in use"，检查端口占用
4. 使用文档中的测试命令验证单个端口是否工作

## 技术细节
- 使用 `subprocess.PIPE` 捕获输出
- 通过 daemon 线程异步读取日志，不阻塞主流程
- glider 进程终止时，日志线程会自动退出
