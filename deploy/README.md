# 生产部署

本目录提供生产部署文件。默认使用 GHCR release 镜像，不在生产机器上构建应用镜像。

默认镜像：

- `ghcr.io/rc-chn/astrbot-community-plugin-registry-backend:latest`
- `ghcr.io/rc-chn/astrbot-community-plugin-registry-worker:latest`
- `ghcr.io/rc-chn/astrbot-community-plugin-registry-dashboard:latest`

默认 `IMAGE_TAG=latest`，会跟随最新发布版本；如果需要可复现部署或回滚，可以在 `.env` 中把 `IMAGE_TAG` 固定为具体版本。

English version: [README_en.md](README_en.md)

## 文件

- `compose.yml`：应用栈，包含 PostgreSQL、Redis、SeaweedFS、backend、worker、dashboard。
- `compose.caddy.yml`：可选 Caddy TLS 终止层。
- `.env.example`：生产环境变量模板。
- `s3.json.example`：SeaweedFS S3 权限配置模板。
- `caddy/Caddyfile.domain.example`：域名证书模式。
- `caddy/Caddyfile.ip.example`：公网 IP 证书模式。
- `kubernetes/`：通用 Kubernetes manifests。

## 第一次部署

```bash
cd deploy
cp .env.example .env
cp s3.json.example s3.json
```

编辑 `.env`，至少替换这些值：

- `PUBLIC_HOST`
- `PUBLIC_ORIGIN`
- `TRUSTED_HOSTS`
- `HEALTHCHECK_HOST`
- `PG_PASSWORD`
- `S3_ACCESS_KEY`
- `S3_SECRET_KEY`
- `JWT_SECRET`
- `BOOTSTRAP_ADMIN_PASSWORD`

编辑 `s3.json`，让其中的 `accessKey` 和 `secretKey` 与 `.env` 中的 `S3_ACCESS_KEY`、`S3_SECRET_KEY` 保持一致。

生成随机密钥可以用：

```bash
openssl rand -hex 32
openssl rand -base64 32
```

## 模式一：暴露 HTTP，由外部终止 TLS

这是 `compose.yml` 的默认模式。dashboard nginx 会直接暴露 HTTP 端口：

```text
${DASHBOARD_BIND:-0.0.0.0}:${DASHBOARD_PORT:-3001} -> dashboard:80
```

启动：

```bash
docker compose --env-file .env -f compose.yml pull
docker compose --env-file .env -f compose.yml up -d
docker compose --env-file .env -f compose.yml ps
```

外部 TLS 终止层把请求转发到：

```text
http://<deploy-host>:${DASHBOARD_PORT:-3001}
```

如果外部 TLS 终止层和本栈在同一台机器上，建议设置：

```env
DASHBOARD_BIND=127.0.0.1
```

如果 TLS 终止层在另一台机器上，保持：

```env
DASHBOARD_BIND=0.0.0.0
```

`PUBLIC_ORIGIN` 必须填写浏览器最终访问的源，例如：

```env
PUBLIC_ORIGIN=https://registry.example.com
```

如果只是内网或临时 HTTP 测试，可以写：

```env
PUBLIC_ORIGIN=http://203.0.113.10:3001
```

## 模式二：随栈启动 Caddy 自动 TLS

这个模式会额外启动 Caddy，监听宿主机 `80/443`，并反代到 dashboard。

叠加 `compose.caddy.yml` 后，dashboard 不再映射宿主机端口，只由 Caddy 对外提供 `80/443`。
该覆盖写法需要 Docker Compose v2.24.4 或更新版本。

先确认 `.env`：

```env
PUBLIC_HOST=registry.example.com
PUBLIC_ORIGIN=https://registry.example.com
TRUSTED_HOSTS=registry.example.com
HEALTHCHECK_HOST=registry.example.com
ACME_EMAIL=admin@example.com
```

域名证书：

```bash
cp caddy/Caddyfile.domain.example caddy/Caddyfile
docker compose --env-file .env -f compose.yml -f compose.caddy.yml up -d
```

公网 IP 证书：

```bash
cp caddy/Caddyfile.ip.example caddy/Caddyfile
docker compose --env-file .env -f compose.yml -f compose.caddy.yml up -d
```

IP 模式示例：

```env
PUBLIC_HOST=203.0.113.10
PUBLIC_ORIGIN=https://203.0.113.10
TRUSTED_HOSTS=203.0.113.10
HEALTHCHECK_HOST=203.0.113.10
ACME_EMAIL=admin@example.com
```

Let's Encrypt 当前通过 `shortlived` profile 支持 IP 地址证书；该 profile 的证书有效期约 160 小时，Caddyfile 中会显式请求 `profile shortlived`。需要使用支持 ACME profile 的 Caddy 版本。

参考：

- https://letsencrypt.org/docs/profiles/
- https://caddyserver.com/docs/caddyfile/directives/tls

## 扫描策略

默认生产策略：

```env
SCAN_PASS_WHEN_UNCONFIGURED=false
```

这表示自动扫描未配置或不可用时，不允许直接发布。若你明确希望关闭自动扫描以节省资源，可以改成：

```env
SCAN_PASS_WHEN_UNCONFIGURED=true
```

这种模式下，发布前需要依赖人工审核和管理流程兜底。

## Kubernetes

Kubernetes 部署文件在 [kubernetes/](kubernetes/)。

快速流程：

```bash
cd deploy/kubernetes
cp secret.example.yaml secret.yaml
# 编辑 configmap.yaml、secret.yaml、ingress.yaml
kubectl apply -f namespace.yaml
kubectl apply -f secret.yaml
kubectl apply -k .
```

默认模板是通用 base，不默认绑定 IngressClass、TLS issuer 或 StorageClass。生产部署前，按目标集群调整 `ingress.yaml`、TLS、暴露方式和 PVC 存储配置。

## 使用 acprctl 管理

从 GitHub Release 下载对应平台的 `acprctl` 包，包内包含 `skills/acprctl/`。

如果你的运维环境使用支持 skill 的 agent，可以把 `skills/acprctl` 安装到 agent 的 skills 目录。之后直接让 agent 使用 `acprctl` skill 来管理本插件源；agent 会按 skill 内的命令参考调用 `acprctl`，完成检查、审核、扫描、发布和配置管理。

首次配置：

```bash
acprctl configure \
  --server-url https://registry.example.com \
  --username admin \
  --password '<admin-password>'
```

常用检查：

```bash
acprctl stats
acprctl plugin list
acprctl review list
acprctl config list
```

如果当前只暴露 HTTP：

```bash
acprctl --server-url http://203.0.113.10:3001 stats
```

## 升级

默认使用 `IMAGE_TAG=latest` 时，直接 pull 并重建即可：

```bash
docker compose --env-file .env -f compose.yml pull
docker compose --env-file .env -f compose.yml up -d
```

如果启用了 Caddy：

```bash
docker compose --env-file .env -f compose.yml -f compose.caddy.yml pull
docker compose --env-file .env -f compose.yml -f compose.caddy.yml up -d
```

需要锁定或回滚到某个版本时，先把 `.env` 中的 `IMAGE_TAG` 改为对应 tag。

## 检查

```bash
docker compose --env-file .env -f compose.yml ps
docker compose --env-file .env -f compose.yml logs -f backend worker dashboard
curl -fsS -H "Host: ${HEALTHCHECK_HOST}" http://127.0.0.1:${DASHBOARD_PORT}/api/v1/health
```

Caddy 模式：

```bash
docker compose --env-file .env -f compose.yml -f compose.caddy.yml logs -f caddy
curl -fsS ${PUBLIC_ORIGIN}/api/v1/health
```
