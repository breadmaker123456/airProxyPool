# airProxyPool 代理池

一个简单实用的代理池：自动收集/验证节点，统一暴露为 SOCKS5 接口。同时支持：

1) 通过 aggregator 自动扫描与聚合可用节点
2) 使用 glider 将节点统一转换为 SOCKS5 代理供外部访问
3) 自定义“机场”订阅一键转换为 glider 可用的 forward= 节点

## 功能特点

- 自动收集与定时更新
- 可用性检测与故障转移
- 支持 SS / VMess
- 统一的 SOCKS5 访问接口
- 支持自定义订阅（机场）→ glider 节点转换（单次或定时轮询）

## 依赖要求

- Python 3.7+
- glider 可执行文件

## 快速开始

1. 克隆仓库并初始化子模块（aggregator 已改为 submodule）
   - 初次克隆后执行：
```bash
git submodule update --init --recursive
```
   - 后续拉取最新 aggregator：
```bash
git submodule update --remote --merge aggregator
# 或在 aggregator 目录内执行
git pull
```

2. 创建虚拟环境并安装依赖
```bash
python -m venv venv
pip install -r requirements.txt
pip install -r aggregator\requirements.txt
```

3. 安装 glider（下载与放置）
   - 下载位置：将可执行文件放到项目的 glider/ 目录下
     - Windows 放置为 glider/glider.exe
     - macOS/Linux 放置为 glider/glider（注意赋予可执行权限）
   - macOS（示例，版本号以官方为准）
     ```bash
     # 示例：下载压缩包
     wget https://github.com/nadoo/glider/releases/download/v0.16.3/glider_0.16.3_macos_amd64.tar.gz
     # 解压（文件名以实际下载为准）
     tar -zxf glider_0.16.3_darwin_amd64.tar.gz
     # 移动到项目目录的 glider/
     mv glider_0.16.3_darwin_amd64 glider
     chmod +x glider/glider
     ```
   - Linux（示例，版本号以官方为准）
     ```bash
     wget https://github.com/nadoo/glider/releases/download/v0.16.3/glider_0.16.3_linux_amd64.tar.gz
     tar -zxf glider_0.16.3_linux_amd64.tar.gz
     mv glider_0.16.3_linux_amd64 glider
     chmod +x glider/glider
     ```
   - Windows（你提供的链接，架构按需替换）
     - 直接下载（32-bit 示例）：
       https://github.com/nadoo/glider/releases/download/v0.16.4/glider_0.16.4_windows_386.zip
     - 解压后重命名可执行文件为 glider.exe，并放到项目 glider/ 目录：glider/glider.exe
     - PowerShell 验证：在项目根执行：
```bash
./glider/glider.exe -h
```
   - 脚本适配说明：
     - Windows 下脚本使用 glider/glider.exe
     - Linux/macOS 下脚本使用 glider/glider
     - 无需手动修改，scheduler.py 与 subscription_scheduler.py 已按平台进行路径/权限处理。
   - 更多信息参考 glider/README.md 或官方 Releases 页面。

## 配置说明

1) aggregator 输出
- 初次运行后会生成 aggregator/data/clash.yaml（聚合到的 Clash 节点）

2) glider 基础配置（glider/glider.conf）
- 建议基础内容如下（forward= 行会由脚本自动写入/替换）：

```conf
# Verbose mode, print logs
verbose=true

# 监听地址
listen=:10707

# 负载策略：rr（轮询）/ ha（高可用）
strategy=rr

# 健康检查
check=http://www.msftconnecttest.com/connecttest.txt#expect=200

# 健康检查间隔（秒）
checkinterval=30
```

## 如何使用

方式一：内置采集器（aggregator）驱动的代理池
- 更新一次（生成/刷新节点，并写入 glider/glider.conf 的 forward= 行）：
```bash
python run_collector.py
```
- 持续运行（每 30 分钟更新并重启 glider 生效）：
```bash
python scheduler.py
```
- 默认监听：127.0.0.1:10707（SOCKS5）

方式二：自定义机场订阅 → SOCKS5（新）
- 定时轮询（长期使用）：
  - 在项目根创建 subscriptions.txt，一行一个订阅 URL（可混合 YAML/TXT）。
  - 如需修改监听端口/间隔等，可编辑 subscription_scheduler.py 顶部的变量（LISTEN、INTERVAL_SECONDS 等）。
  - 运行：
```bash
python subscription_scheduler.py
```
  - 行为：定时拉取 → 解析为 forward= → 写入 glider/glider.subscription.conf → 启动/重启 glider 使用该配置

- 默认监听：127.0.0.1:10710（SOCKS5）

## 使用截图

![proxy_config](docs/images/use.png)

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=langchou/airProxyPool&type=Date)](https://star-history.com/#langchou/airProxyPool&Date)
