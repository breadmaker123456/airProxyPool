# airProxyPool 代理池

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

2. 创建并激活虚拟环境
```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
source venv/bin/activate
```

3. 安装 Python 依赖
```bash
pip install -r requirements.txt
```

4. 安装 glider
```bash
# macOS
wget https://github.com/nadoo/glider/releases/download/v0.16.3/glider_0.16.3_macos_amd64.tar.gz
tar -zxf glider_0.16.3_darwin_amd64.tar.gz
mv glider_0.16.3_darwin_amd64 glider
chmod +x glider/glider

# Linux
wget https://github.com/nadoo/glider/releases/download/v0.16.3/glider_0.16.3_linux_amd64.tar.gz
tar -zxf glider_0.16.3_linux_amd64.tar.gz
mv glider_0.16.3_linux_amd64 glider
chmod +x glider/glider

```

5. 安装aggregator
```bash
# 先回到项目根目录

git clone https://github.com/wzdnzd/aggregator.git

cd aggregator

pip install -r requirements.txt
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

0. 手动更新一次代理池，速度较慢
```bash
python run_collector.py
```

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

## 使用截图

![proxy_config](docs/images/use.png)

## 许可证

MIT License 
