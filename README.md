# ProxyPool 代理池

这是一个简单的代理池项目，通过自动收集和验证代理，并提供统一的SOCKS5访问接口。项目包含两个主要功能：

1. 通过 aggregator 自动扫描和收集可用的代理服务器
2. 使用 glider 将收集到的代理转换为统一的 SOCKS5 代理，供外部访问

## 功能特点

- 自动收集和更新代理
- 定期检测代理可用性
- 支持 SS 和 VMess 代理
- 统一的 SOCKS5 访问接口
- 自动故障转移

## 依赖要求

- Python 3.7+
- glider

## 安装步骤

1. 克隆项目
```bash
git clone <repository_url>
cd proxyPool
```

2. 安装 Python 依赖
```bash
pip install -r requirements.txt
```

3. 安装 glider
```bash
# Linux/macOS
wget https://github.com/nadoo/glider/releases/download/v0.16.3/glider_0.16.3_linux_amd64.tar.gz
tar -zxf glider_0.16.3_linux_amd64.tar.gz
mv glider glider/
chmod +x glider/glider
```

## 项目结构

```
proxyPool/
├── aggregator/          # 代理收集模块
├── glider/             # glider配置和可执行文件
├── scheduler.py        # 主调度器
├── run_collector.py    # 代理收集执行脚本
└── parse.py           # 配置解析脚本
```

## 配置说明

1. 在 `aggregator/data/` 目录下会生成 `clash.yaml`，存储收集到的代理信息
2. 在 `glider/` 目录下创建 `glider.conf` 配置文件，内容如下：

```conf
# Verbose mode, print logs
verbose=True

# 监听地址和端口
listen=:10707

# Round Robin mode: rr
# High Availability mode: ha
strategy=rr

# forwarder health check
check=http://www.msftconnecttest.com/connecttest.txt#expect=200
```

配置说明：
- `verbose`: 是否打印详细日志
- `listen`: 监听地址和端口，格式为 `[ip]:port`
- `strategy`: 负载均衡策略
  - `rr`: 轮询模式
  - `ha`: 高可用模式
- `check`: 健康检查配置
  - 检查URL: `http://www.msftconnecttest.com/connecttest.txt`
  - 期望响应码: `200`

## 使用方法

1. 启动代理池服务
```bash
python scheduler.py
```

这个脚本会：
- 启动 glider 代理服务器
- 每30分钟自动更新一次代理池
- 自动进行代理可用性检测

2. 手动更新代理池（可选）
```bash
python run_collector.py
```

3. 使用代理
- 默认监听端口：10707
- 协议：SOCKS5
- 连接地址：127.0.0.1:10707

## 工作流程

1. `scheduler.py`
   - 作为主进程启动和管理整个服务
   - 定期触发代理更新
   - 管理 glider 进程

2. `run_collector.py`
   - 调用 aggregator 收集代理
   - 生成 clash.yaml 配置文件
   - 调用 parse.py 转换配置格式

3. `parse.py`
   - 将 clash 格式的配置转换为 glider 可用的格式
   - 生成 glider.conf 配置文件

## 注意事项

1. 确保 glider 可执行文件位于正确位置
2. 需要定期清理和更新代理池
3. 建议配置自动启动脚本
4. 如遇到问题，检查日志输出

## 常见问题

1. 如果代理无法连接，请检查：
   - glider 进程是否正常运行
   - 代理池是否有可用代理
   - 端口是否被占用

2. 如何修改监听端口？
   - 修改 glider.conf 中的 listen 配置

3. 如何添加自定义代理源？
   - 在 aggregator 模块中添加新的代理源

## 贡献指南

欢迎提交 Issue 和 Pull Request 来改进项目。

## 许可证

MIT License 