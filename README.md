# AstrBot 社区插件源

这是一个面向 AstrBot 的社区插件源服务，包含插件元数据、版本包、构建/扫描队列、管理后台和独立管理 CLI。

主要目录：

- `registry/`：FastAPI 后端与 worker 代码。
- `dashboard/`：Vue 管理后台。
- `acprctl/`：独立 Go 管理 CLI。
- `skills/acprctl/`：配套 skill，release 包内随 `acprctl` 一起分发。
- `dev/`：本地开发栈。
- `deploy/`：生产部署文件。
- `docs/`：设计文档。

English documentation: [README_en.md](README_en.md)

## 部署模式

生产部署默认使用 GHCR release 镜像：

- `ghcr.io/rc-chn/astrbot-community-plugin-registry-backend:latest`
- `ghcr.io/rc-chn/astrbot-community-plugin-registry-worker:latest`
- `ghcr.io/rc-chn/astrbot-community-plugin-registry-dashboard:latest`

默认部署跟随 `latest`；需要固定版本或回滚时，在 `deploy/.env` 中设置具体 `IMAGE_TAG`。

`deploy/` 提供三种推荐模式。

### 模式一：暴露 HTTP，由外部终止 TLS

这是默认模式。`dashboard` nginx 直接暴露 HTTP 端口，外部的 Caddy、nginx、Traefik、云负载均衡或 CDN 负责 HTTPS/TLS。

```bash
cd deploy
cp .env.example .env
cp s3.json.example s3.json
# 编辑 .env 和 s3.json
docker compose --env-file .env -f compose.yml pull
docker compose --env-file .env -f compose.yml up -d
```

默认会暴露：

```text
0.0.0.0:${DASHBOARD_PORT:-3001} -> dashboard:80
```

如果 TLS 终止层和本栈在同一台机器上，也可以把 `.env` 里的 `DASHBOARD_BIND` 改成 `127.0.0.1`。

### 模式二：随栈启动 Caddy 自动申请证书

如果希望由部署栈自己处理 HTTPS，可以叠加 `compose.caddy.yml`，让 Caddy 监听 `80/443` 并反代到 dashboard。

域名证书：

```bash
cd deploy
cp caddy/Caddyfile.domain.example caddy/Caddyfile
docker compose --env-file .env -f compose.yml -f compose.caddy.yml up -d
```

公网 IP 证书：

```bash
cd deploy
cp caddy/Caddyfile.ip.example caddy/Caddyfile
docker compose --env-file .env -f compose.yml -f compose.caddy.yml up -d
```

Let's Encrypt 当前通过 `shortlived` profile 支持 IP 地址证书，证书有效期约 160 小时；Caddy 需要使用支持 ACME profile 的版本，并在 IP 模式 Caddyfile 中请求 `profile shortlived`。

参考：

- https://letsencrypt.org/docs/profiles/
- https://caddyserver.com/docs/caddyfile/directives/tls

### 模式三：Kubernetes

如果部署到 Kubernetes，使用 `deploy/kubernetes`：

```bash
cd deploy/kubernetes
cp secret.example.yaml secret.yaml
# 编辑 configmap.yaml、secret.yaml、ingress.yaml
kubectl apply -f namespace.yaml
kubectl apply -f secret.yaml
kubectl apply -k .
```

该模板是通用 base，不默认绑定 IngressClass、TLS issuer 或 StorageClass；生产部署前按目标集群调整 `ingress.yaml` 和 PVC 存储配置。

完整部署说明见 [deploy/README.md](deploy/README.md)。

## 使用 acprctl 管理

从 GitHub Release 下载对应平台的 `acprctl` 包。包内包含二进制、README 和 `skills/acprctl/`。

如果你使用支持 skill 的 agent，可以把包内的 `skills/acprctl` 安装到 agent 的 skills 目录。之后让 agent 使用 `acprctl` skill，它会按内置命令参考通过 `acprctl` 连接插件源，完成状态检查、插件审核、扫描触发、发布、配置调整等管理操作。

连接生产服务：

```bash
acprctl configure \
  --server-url https://registry.example.com \
  --username admin \
  --password '<admin-password>'

acprctl stats
acprctl plugin list
```

如果使用默认 HTTP 暴露模式且还没有外部 TLS，`--server-url` 可以暂时使用：

```bash
acprctl --server-url http://<host>:3001 stats
```

## 本地开发

```bash
uv sync
cp .env.example .env
uv run serve
```

使用完整本地中间件栈：

```bash
cd dev
cp .env.example .env
docker compose up -d

cd ..
cp .env.example .env
uv run serve
```

更多本地栈细节见 [dev/README.md](dev/README.md)。
