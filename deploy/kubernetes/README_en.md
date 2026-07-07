# Kubernetes Deployment

This directory contains generic Kubernetes deployment templates and avoids binding the base manifests to a specific cluster implementation. The templates only assume that the cluster has:

- a default StorageClass, or that you will add `storageClassName` to the StatefulSets yourself.
- a usable Ingress controller, or that you will replace Ingress with your own exposure method.

TLS, IngressClass, cert-manager annotations, LoadBalancer settings, node affinity, and quotas are intentionally not specified by default. Add them for your target cluster.

Chinese version: [README.md](README.md)

## Files

- `kustomization.yaml`: Kustomize entrypoint, default image tag `latest`.
- `namespace.yaml`: `astrbot-registry` namespace.
- `configmap.yaml`: non-secret runtime configuration.
- `secret.example.yaml`: secret template; it is not included by `kustomization.yaml`.
- `postgres.yaml`, `redis.yaml`, `seaweedfs.yaml`: bundled dependencies.
- `clamav.yaml`: optional self-hosted ClamAV scanner, default `replicas: 0`.
- `backend.yaml`, `worker.yaml`, `dashboard.yaml`: application components.
- `ingress.yaml`: generic Ingress, with no default IngressClass or TLS.

## First Deploy

```bash
cd deploy/kubernetes
cp secret.example.yaml secret.yaml
```

Edit `configmap.yaml` and replace at least:

- `TRUSTED_HOSTS`
- `HEALTHCHECK_HOST`
- `S3_PUBLIC_URL`

Edit `ingress.yaml` and replace at least:

- `spec.rules[0].host`

If your cluster has no default IngressClass, add this to `ingress.yaml`:

```yaml
spec:
  ingressClassName: <your-ingress-class>
```

If you use cert-manager for TLS, add your issuer annotation and `spec.tls`. Example:

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

If you need a fixed StorageClass, add this under `volumeClaimTemplates[].spec` in `postgres.yaml`, `redis.yaml`, and `seaweedfs.yaml`:

```yaml
storageClassName: <your-storage-class>
```

If you enable ClamAV, also add the same `storageClassName` to `PersistentVolumeClaim.spec` in `clamav.yaml`.

Edit `secret.yaml` and replace at least:

- `PG_PASSWORD`
- the PostgreSQL password inside `DATABASE_URL`
- `S3_ACCESS_KEY`
- `S3_SECRET_KEY`
- S3 credentials inside `seaweedfs-s3.json`
- `JWT_SECRET`
- `BOOTSTRAP_ADMIN_PASSWORD`

Generate random secrets with:

```bash
openssl rand -hex 32
openssl rand -base64 32
```

Create the namespace and secret first:

```bash
kubectl apply -f namespace.yaml
kubectl apply -f secret.yaml
```

Apply the stack:

```bash
kubectl apply -k .
```

## Checks

```bash
kubectl -n astrbot-registry get pods,svc,ingress,pvc
kubectl -n astrbot-registry rollout status statefulset/postgres
kubectl -n astrbot-registry rollout status statefulset/redis
kubectl -n astrbot-registry rollout status statefulset/seaweedfs
kubectl -n astrbot-registry rollout status deployment/backend
kubectl -n astrbot-registry rollout status deployment/worker
kubectl -n astrbot-registry rollout status deployment/dashboard
```

If ClamAV is enabled:

```bash
kubectl -n astrbot-registry rollout status deployment/clamav
```

Health check:

```bash
curl -fsS https://registry.example.com/api/v1/health
```

Admin smoke test:

```bash
acprctl --server-url https://registry.example.com --username admin --password '<admin-password>' stats
acprctl --server-url https://registry.example.com --username admin --password '<admin-password>' plugin list --page-size 5
acprctl --server-url https://registry.example.com --username admin --password '<admin-password>' config list
```

## Upgrade And Rollback

The default image tag is `latest`:

```bash
kubectl -n astrbot-registry rollout restart deployment/backend deployment/worker deployment/dashboard
```

Pin a release tag:

```bash
kubectl -n astrbot-registry set image deployment/backend backend=ghcr.io/rc-chn/astrbot-community-plugin-registry-backend:v0.1.0
kubectl -n astrbot-registry set image deployment/worker worker=ghcr.io/rc-chn/astrbot-community-plugin-registry-worker:v0.1.0
kubectl -n astrbot-registry set image deployment/dashboard dashboard=ghcr.io/rc-chn/astrbot-community-plugin-registry-dashboard:v0.1.0
```

Or update `images[].newTag` in `kustomization.yaml` and re-apply:

```bash
kubectl apply -k .
```

## Scanning Policy

Default production recording policy:

```yaml
SCAN_PASS_WHEN_UNCONFIGURED: "false"
```

There is no fixed required-provider list. Publishing is blocked only by existing scan results that are `pending`, `error`, or real failed results; skipped unconfigured providers do not block publishing. `SCAN_PASS_WHEN_UNCONFIGURED` only controls the recorded `pass` value when an unconfigured provider is triggered. To show skipped results as passing, change it in `configmap.yaml`:

```yaml
SCAN_PASS_WHEN_UNCONFIGURED: "true"
```

To enable ClamAV, update `configmap.yaml`:

```yaml
SCAN_ENABLED_PROVIDERS: "virustotal,llm_agent,clamav"
CLAMAV_HOST: "clamav"
CLAMAV_PORT: "3310"
```

Then change `Deployment.spec.replicas` in `clamav.yaml` to `1` and apply:

```bash
kubectl apply -k .
kubectl -n astrbot-registry rollout status deployment/clamav
kubectl -n astrbot-registry rollout restart deployment/backend deployment/worker
```

When enabling LLM or VirusTotal scanning, update provider settings in `configmap.yaml`, API keys in `secret.yaml`, then restart backend and worker:

```bash
kubectl apply -f secret.yaml
kubectl apply -k .
kubectl -n astrbot-registry rollout restart deployment/backend deployment/worker
```

## Notes

- Do not commit `secret.yaml`.
- `DATABASE_URL` is a full connection string; keep it in sync with `PG_PASSWORD`.
- `S3_PUBLIC_URL` must be the final browser origin plus `/s3/<bucket>`.
- `TRUSTED_HOSTS` and `HEALTHCHECK_HOST` must include the real public host.
- The base manifests do not enable TLS by default. Terminate TLS at Ingress, a gateway, a load balancer, or an external reverse proxy in production.
- These manifests use bundled PostgreSQL, Redis, and SeaweedFS. If you use managed services, remove the matching StatefulSets and update `configmap.yaml`/`secret.yaml`.
- SeaweedFS S3 is not exposed directly. Public downloads go through dashboard nginx at `/s3/<bucket>/plugins/...`.
