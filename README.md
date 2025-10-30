# airProxyPool 代理池
![proxy_config](docs/images/use.png)


用于“代理池”场景：把不同来源、不同格式的节点统一成一个稳定的 SOCKS5 出口。适合爬虫、批量注册（注册机）、自动化任务等需要大量/稳定出站代理的场景。

1) 通过 aggregator 自动扫描与聚合可用节点
2) 使用 glider 将节点统一转换为 SOCKS5 代理供外部访问
3) 自定义“机场”订阅一键转换为 glider 可用的 forward= 节点

- 普通用户：使用“白嫖机场”订阅作为代理池，开箱即用。
- 有追求用户：使用自建订阅或付费机场作为代理池，更干净、更可控。

## 功能特点

- 自动收集与定时更新
- 可用性检测与故障转移
- 支持 SS / VMess
- 统一的 SOCKS5 访问接口
- 支持自定义订阅（机场）→ glider 节点转换（单次或定时轮询）

## 目录
- [通用准备](#通用准备)
- [使用“白嫖机场”订阅作为代理池](#建议小白使用白嫖机场订阅作为代理池)
- [使用自建/付费订阅作为代理池](#有追求使用自建付费订阅作为代理池)

## 通用准备

- 依赖要求
  - Python 3.7+
  - glider 可执行文件

- 创建虚拟环境并安装依赖
```bash
python -m venv venv
pip install -r requirements.txt
```

- 安装 glider（下载与放置）

  > 使用 Docker 部署时镜像会自动下载 glider，可跳过此步骤。

  - 将可执行文件放到项目 glider/ 目录：
    - Windows: glider/glider.exe（示例下载链接：v0.16.4 32-bit）
      https://github.com/nadoo/glider/releases/download/v0.16.4/glider_0.16.4_windows_386.zip
      解压后重命名为 glider.exe 放到 glider/ 目录
      验证： `./glider/glider.exe -h`

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
- glider 基础配置（glider/glider.conf）（此为示例，脚本会自行创建）
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

---

## 使用“白嫖机场”订阅作为代理池

此方式依赖 aggregator（作为 Git 子模块），自动聚合免费节点。

- 初始化 submodule（首次必做）
```bash
git submodule update --init --recursive
```
- 安装 aggregator 依赖（在项目根）
```bash
pip install -r aggregator/requirements.txt
```
- 手动跑一轮采集并写入 glider/glider.conf 的 forward= 段
```bash
python run_collector.py
```
- 守护运行（每 30 分钟刷新并重启 glider 生效）
```bash
python scheduler.py
```
- 默认 SOCKS5：127.0.0.1:10707
- 产物：aggregator/data/clash.yaml（聚合结果），glider/glider.conf（含 forward= 行）


---

## 使用自建/付费订阅作为代理池

此方式不需要 submodule（可忽略 aggregator）。
- 定时轮询（长期自动刷新）：在项目根创建 subscriptions.txt（每行一个订阅 URL），然后运行
```bash
python subscription_scheduler.py
```
- 行为：定时拉取 → 解析为 forward= → 写入 glider/glider.subscription.conf → 启动/重启 glider 使用该配置
- 默认 SOCKS5/http：127.0.0.1:10710

## 中转 API 服务

项目新增了一个 `FastAPI` 驱动的中转服务，支持 HTTP/SOCKS5 代理统一出口，并可通过 API 按需返回代理信息。

### 功能摘要
- 支持协议过滤：`protocols=socks5/http`
- 支持国家过滤：自动从订阅/节点名称中推断国家信息
- 支持数量控制：`count` 指定返回的代理数量
- 支持随机轮换：`random=true` 时每次返回不同端口；默认 5 分钟缓存相同请求
- 提供健康检查与手动刷新接口

### 启动（本地）
```bash
pip install -r requirements.txt
uvicorn proxychain.main:app --host 0.0.0.0 --port 8000
```

服务启动后可访问：
- 健康检查：`GET /healthz`
- 获取代理：`GET /api/v1/proxies?protocols=socks5&country=US&count=3&random=1`
- 手动刷新：`POST /api/v1/proxies/refresh`

返回示例：
```json
{
  "data": [
    {
      "id": "<endpoint-id>",
      "protocol": "socks5",
      "endpoint": "socks5://example.com:25001",
      "country": {"name": "United States", "code": "US"},
      "available": true
    }
  ],
  "meta": {
    "requested_count": 3,
    "returned_count": 3,
    "cached": false,
    "random": true
  }
}
```

> **提示**：未开启 `random` 参数时，服务会对相同的查询结果做 5 分钟缓存。

### Docker Compose 部署

项目根目录提供 `docker-compose.yml`，单容器即可完成部署并持久化数据。

```bash
# 构建并启动
docker compose up -d

# 查看日志
docker compose logs -f
```

默认映射：
- API：`8000` (宿主) → `8000` (容器)
- SOCKS5 端口池：`25000-25100`
- HTTP 端口池：`26000-26100`
- 数据目录：`./data`

镜像会在构建时自动下载 Linux 版 glider 并放置到 `/app/glider/glider`，无需额外准备二进制。若需指定自定义版本，可在构建时通过 `--build-arg GLIDER_VERSION=...`（以及 `GLIDER_ARCH`）覆盖，或直接在运行 `docker compose build` 前设置同名环境变量（`docker-compose.yml` 已预置 build args）。也可在运行时挂载自定义可执行文件并设置 `GLIDER_BINARY` 环境变量指向其路径。部署前请在宿主机的 `subscriptions.txt` 中填入订阅地址（容器内以只读方式挂载）。

常用环境变量：
- `PUBLIC_HOST`：对外暴露的域名/IP，默认 `127.0.0.1`
- `BASE_SOCKS_PORT`、`BASE_HTTP_PORT`：本地端口起始值
- `ENABLE_GLIDER`：是否自动拉起 glider 进程（默认开启）
- `GLIDER_STRATEGY`：glider 端的调度策略，默认 `rr`，可设为 `ha` 等 glider 支持的模式
- `GLIDER_CHECK_INTERVAL`：健康检查间隔（秒），默认 `60`
- `GLIDER_DIAL_TIMEOUT`：glider 连接后端代理的超时时间（秒），默认 `10`
- `GLIDER_RELAY_TIMEOUT`：glider 转发超时时间（秒），默认 `30`，设为 `0` 禁用
- `GLIDER_CHECK_TIMEOUT`：健康检查超时时间（秒），默认 `8`
- `GLIDER_MAX_FAILURES`：节点失败多少次后标记为不可用，默认 `2`
- `PROXY_HEALTH_CHECK`：健康检查 URL，留空可禁用 glider 内置检查
- `LOG_LEVEL`：日志级别，可设为 `DEBUG` 查看详细的 glider 配置和输出

### 故障排查

如果代理无法连接或返回空响应，请按以下步骤排查：

1. **查看 glider 进程日志**：
   ```bash
   # Docker 环境
   docker compose logs -f
   
   # 本地环境，设置日志级别为 DEBUG
   LOG_LEVEL=DEBUG uvicorn proxychain.main:app --host 0.0.0.0 --port 8000
   ```
   
   日志中会显示：
   - glider 配置文件内容（DEBUG 级别）
   - glider 进程的实时输出（INFO 级别，格式：`glider[端点ID前8位]: 消息内容`）
   - 端点启动/停止状态

2. **检查生成的配置文件**：
   配置文件位于 `data/glider_configs/` 目录（Docker 中为 `/data/glider_configs/`），可手动查看配置是否正确。

3. **测试单个端点**：
   ```bash
   # SOCKS5 代理测试
   curl -x socks5://127.0.0.1:25000 http://ip.sb
   
   # HTTP 代理测试
   curl -x http://127.0.0.1:26000 http://ip.sb
   ```

4. **常见问题**：
   - **空响应或超时**：
     * 后端代理节点失效或无法连接，查看 glider 日志确认转发错误
     * 如果日志中出现 `i/o timeout` 或 `dial timeout` 错误，可尝试增加超时时间：
       ```bash
       # Docker Compose 环境，在 docker-compose.yml 中添加或修改环境变量
       environment:
         - GLIDER_DIAL_TIMEOUT=15  # 增加拨号超时到15秒
         - GLIDER_RELAY_TIMEOUT=60  # 增加转发超时到60秒
       
       # 然后重启服务
       docker compose down && docker compose up -d
       ```
     * 免费节点经常失效，建议使用付费机场或自建节点以获得更稳定的服务
   - **端口无法访问**：检查防火墙规则和 Docker 端口映射
   - **订阅解析失败**：确认 `subscriptions.txt` 中的 URL 可访问且格式正确

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=dreammis/airProxyPool&type=Date)](https://star-history.com/#dreammis/airProxyPool&Date)
