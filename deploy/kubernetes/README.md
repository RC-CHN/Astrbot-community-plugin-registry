# Kubernetes 部署

本目录提供通用 Kubernetes 部署模板，尽量不绑定具体集群实现。模板只假设集群已经有：

- 默认 StorageClass，或你会自行给 StatefulSet 增加 `storageClassName`。
- 可用的 Ingress controller，或你会改成自己的暴露方式。

TLS、IngressClass、cert-manager 注解、LoadBalancer、节点亲和、资源配额等集群相关配置不在 base 模板里默认指定，请按目标集群自行添加。

English version: [README_en.md](README_en.md)

## 文件

- `kustomization.yaml`：Kustomize 入口，默认镜像 tag 为 `latest`。
- `namespace.yaml`：`astrbot-registry` namespace。
- `configmap.yaml`：非敏感运行配置。
- `secret.example.yaml`：敏感配置示例，不会被 `kustomization.yaml` 自动引用。
- `postgres.yaml`、`redis.yaml`、`seaweedfs.yaml`：内置依赖。
- `clamav.yaml`：可选自托管 ClamAV 扫描服务，默认 `replicas: 0`。
- `backend.yaml`、`worker.yaml`、`dashboard.yaml`：应用组件。
- `ingress.yaml`：通用 Ingress 入口，默认不指定 IngressClass 或 TLS。

## 第一次部署

```bash
cd deploy/kubernetes
cp secret.example.yaml secret.yaml
```

编辑 `configmap.yaml`，至少替换：

- `TRUSTED_HOSTS`
- `HEALTHCHECK_HOST`
- `S3_PUBLIC_URL`

编辑 `ingress.yaml`，至少替换：

- `spec.rules[0].host`

如果集群没有默认 IngressClass，给 `ingress.yaml` 添加：

```yaml
spec:
  ingressClassName: <your-ingress-class>
```

如果使用 cert-manager 自动签发 TLS，按你的 issuer 增加注解和 `spec.tls`。示例：

```yaml
metadata:
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
    - hosts:
        - registry.example.com
      secretName: astrbot-registry-tls
```

如果需要固定 StorageClass，在 `postgres.yaml`、`redis.yaml`、`seaweedfs.yaml` 的 `volumeClaimTemplates[].spec` 下添加：

```yaml
storageClassName: <your-storage-class>
```

如果启用 ClamAV，也给 `clamav.yaml` 的 `PersistentVolumeClaim.spec` 添加同样的 `storageClassName`。

编辑 `secret.yaml`，至少替换：

- `PG_PASSWORD`
- `DATABASE_URL` 中的 PostgreSQL 密码
- `S3_ACCESS_KEY`
- `S3_SECRET_KEY`
- `seaweedfs-s3.json` 中的 S3 凭据
- `JWT_SECRET`
- `BOOTSTRAP_ADMIN_PASSWORD`

生成随机密钥：

```bash
openssl rand -hex 32
openssl rand -base64 32
```

先创建 namespace 和 secret：

```bash
kubectl apply -f namespace.yaml
kubectl apply -f secret.yaml
```

再应用完整栈：

```bash
kubectl apply -k .
```

## 检查

```bash
kubectl -n astrbot-registry get pods,svc,ingress,pvc
kubectl -n astrbot-registry rollout status statefulset/postgres
kubectl -n astrbot-registry rollout status statefulset/redis
kubectl -n astrbot-registry rollout status statefulset/seaweedfs
kubectl -n astrbot-registry rollout status deployment/backend
kubectl -n astrbot-registry rollout status deployment/worker
kubectl -n astrbot-registry rollout status deployment/dashboard
```

如果启用了 ClamAV：

```bash
kubectl -n astrbot-registry rollout status deployment/clamav
```

健康检查：

```bash
curl -fsS https://registry.example.com/api/v1/health
```

管理员 smoke test：

```bash
acprctl --server-url https://registry.example.com --username admin --password '<admin-password>' stats
acprctl --server-url https://registry.example.com --username admin --password '<admin-password>' plugin list --page-size 5
acprctl --server-url https://registry.example.com --username admin --password '<admin-password>' config list
```

## 升级和回滚

默认使用 `latest`：

```bash
kubectl -n astrbot-registry rollout restart deployment/backend deployment/worker deployment/dashboard
```

固定到某个 release tag：

```bash
kubectl -n astrbot-registry set image deployment/backend backend=ghcr.io/rc-chn/astrbot-community-plugin-registry-backend:v0.1.0
kubectl -n astrbot-registry set image deployment/worker worker=ghcr.io/rc-chn/astrbot-community-plugin-registry-worker:v0.1.0
kubectl -n astrbot-registry set image deployment/dashboard dashboard=ghcr.io/rc-chn/astrbot-community-plugin-registry-dashboard:v0.1.0
```

或者修改 `kustomization.yaml` 的 `images[].newTag` 后重新：

```bash
kubectl apply -k .
```

## 扫描策略

生产默认记录策略：

```yaml
SCAN_PASS_WHEN_UNCONFIGURED: "false"
```

当前没有固定“必需 provider”。发布只会被已有扫描结果中的 `pending`、`error` 或真实失败阻塞；未配置 provider 被跳过时不会阻塞发布。`SCAN_PASS_WHEN_UNCONFIGURED` 只控制未配置 provider 被触发时记录的 `pass` 值。如果希望 skipped 结果在展示上显示为通过，可以在 `configmap.yaml` 中改为：

```yaml
SCAN_PASS_WHEN_UNCONFIGURED: "true"
```

启用 ClamAV 时，修改 `configmap.yaml`：

```yaml
SCAN_ENABLED_PROVIDERS: "virustotal,llm_agent,clamav"
CLAMAV_HOST: "clamav"
CLAMAV_PORT: "3310"
```

然后把 `clamav.yaml` 中 `Deployment.spec.replicas` 改为 `1`，再应用：

```bash
kubectl apply -k .
kubectl -n astrbot-registry rollout status deployment/clamav
kubectl -n astrbot-registry rollout restart deployment/backend deployment/worker
```

启用 LLM 或 VirusTotal 扫描时，分别更新 `configmap.yaml` 中的 provider 设置和 `secret.yaml` 中的 API key，然后重启 backend/worker：

```bash
kubectl apply -f secret.yaml
kubectl apply -k .
kubectl -n astrbot-registry rollout restart deployment/backend deployment/worker
```

## 注意事项

- `secret.yaml` 不要提交到 Git。
- `DATABASE_URL` 是完整连接串，修改 `PG_PASSWORD` 后必须同步修改它。
- `S3_PUBLIC_URL` 必须等于浏览器最终访问源加 `/s3/<bucket>`。
- `TRUSTED_HOSTS` 和 `HEALTHCHECK_HOST` 必须包含真实访问域名。
- base 模板不默认启用 TLS；生产环境应在 Ingress、网关、负载均衡或外部反代层终止 TLS。
- 本模板使用内置 PostgreSQL、Redis、SeaweedFS；如果接入外部托管服务，可以删除对应 StatefulSet，并把连接地址改到 `configmap.yaml`/`secret.yaml`。
- 当前模板没有直接暴露 SeaweedFS S3 API；公开下载通过 dashboard nginx 的 `/s3/<bucket>/plugins/...` 反代路径完成。
