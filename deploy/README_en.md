# Production Deployment

This directory contains production deployment files. It uses GHCR release images by default and does not build application images on the production host.

Default images:

- `ghcr.io/rc-chn/astrbot-community-plugin-registry-backend:latest`
- `ghcr.io/rc-chn/astrbot-community-plugin-registry-worker:latest`
- `ghcr.io/rc-chn/astrbot-community-plugin-registry-dashboard:latest`

The default `IMAGE_TAG=latest` follows the newest published release. Pin `IMAGE_TAG` to a concrete version in `.env` when you need reproducible deploys or rollback.

Chinese version: [README.md](README.md)

## Files

- `compose.yml`: application stack with PostgreSQL, Redis, SeaweedFS, backend, worker, and dashboard.
- `compose.caddy.yml`: optional Caddy TLS terminator.
- `.env.example`: production environment template.
- `s3.json.example`: SeaweedFS S3 permission template.
- `caddy/Caddyfile.domain.example`: domain certificate mode.
- `caddy/Caddyfile.ip.example`: public IP certificate mode.
- `kubernetes/`: generic Kubernetes manifests.

## First Deploy

```bash
cd deploy
cp .env.example .env
cp s3.json.example s3.json
```

Edit `.env` and replace at least:

- `PUBLIC_HOST`
- `PUBLIC_ORIGIN`
- `TRUSTED_HOSTS`
- `HEALTHCHECK_HOST`
- `PG_PASSWORD`
- `S3_ACCESS_KEY`
- `S3_SECRET_KEY`
- `JWT_SECRET`
- `BOOTSTRAP_ADMIN_PASSWORD`

Edit `s3.json` so its `accessKey` and `secretKey` match `S3_ACCESS_KEY` and `S3_SECRET_KEY`.

Generate random secrets with:

```bash
openssl rand -hex 32
openssl rand -base64 32
```

## Mode 1: Expose HTTP and Terminate TLS Externally

This is the default `compose.yml` mode. The dashboard nginx exposes an HTTP port:

```text
${DASHBOARD_BIND:-0.0.0.0}:${DASHBOARD_PORT:-3001} -> dashboard:80
```

Start:

```bash
docker compose --env-file .env -f compose.yml pull
docker compose --env-file .env -f compose.yml up -d
docker compose --env-file .env -f compose.yml ps
```

The external TLS terminator proxies to:

```text
http://<deploy-host>:${DASHBOARD_PORT:-3001}
```

If the TLS terminator runs on the same host, use:

```env
DASHBOARD_BIND=127.0.0.1
```

If the TLS terminator runs elsewhere, keep:

```env
DASHBOARD_BIND=0.0.0.0
```

`PUBLIC_ORIGIN` must be the final browser-facing origin, for example:

```env
PUBLIC_ORIGIN=https://registry.example.com
```

For an internal or temporary HTTP deployment:

```env
PUBLIC_ORIGIN=http://203.0.113.10:3001
```

## Mode 2: Run Caddy With the Stack

This mode starts Caddy, exposes host ports `80/443`, and reverse proxies to the dashboard.

When `compose.caddy.yml` is layered in, the dashboard host port is removed; only Caddy exposes `80/443`.
This override requires Docker Compose v2.24.4 or newer.

Set `.env`:

```env
PUBLIC_HOST=registry.example.com
PUBLIC_ORIGIN=https://registry.example.com
TRUSTED_HOSTS=registry.example.com
HEALTHCHECK_HOST=registry.example.com
ACME_EMAIL=admin@example.com
```

Domain certificate:

```bash
cp caddy/Caddyfile.domain.example caddy/Caddyfile
docker compose --env-file .env -f compose.yml -f compose.caddy.yml up -d
```

Public IP certificate:

```bash
cp caddy/Caddyfile.ip.example caddy/Caddyfile
docker compose --env-file .env -f compose.yml -f compose.caddy.yml up -d
```

IP mode example:

```env
PUBLIC_HOST=203.0.113.10
PUBLIC_ORIGIN=https://203.0.113.10
TRUSTED_HOSTS=203.0.113.10
HEALTHCHECK_HOST=203.0.113.10
ACME_EMAIL=admin@example.com
```

Let's Encrypt currently supports IP address certificates through the `shortlived` profile. These certificates are valid for about 160 hours, and the IP-mode Caddyfile explicitly requests `profile shortlived`. Use a Caddy version that supports ACME profiles.

References:

- https://letsencrypt.org/docs/profiles/
- https://caddyserver.com/docs/caddyfile/directives/tls

## Scan Policy

Default production recording policy:

```env
SCAN_PASS_WHEN_UNCONFIGURED=false
```

There is no fixed required-provider list. Publishing is blocked only by existing scan results that are `pending`, `error`, or real failed results; skipped unconfigured providers do not block publishing. `SCAN_PASS_WHEN_UNCONFIGURED` only controls the recorded `pass` value when an unconfigured provider is triggered. To show skipped results as passing, set:

```env
SCAN_PASS_WHEN_UNCONFIGURED=true
```

When automatic scanning is disabled, publishing should rely on manual review and admin workflow controls regardless of this value.

Optional self-hosted ClamAV scanning uses a Compose profile and is not started by default:

```bash
docker compose --env-file .env -f compose.yml --profile clamav up -d clamav
docker compose --env-file .env -f compose.yml up -d backend worker
```

Also set these values in `.env`:

```env
CLAMAV_ENABLED=true
CLAMAV_HOST=clamav
CLAMAV_PORT=3310
```

## Kubernetes

Kubernetes deployment files live in [kubernetes/](kubernetes/).

Quick flow:

```bash
cd deploy/kubernetes
cp secret.example.yaml secret.yaml
# edit configmap.yaml, secret.yaml, and ingress.yaml
kubectl apply -f namespace.yaml
kubectl apply -f secret.yaml
kubectl apply -k .
```

The manifests are a generic base. They do not bind a default IngressClass, TLS issuer, or StorageClass. Adjust `ingress.yaml`, TLS, exposure, and PVC storage settings for the target cluster before production deployment.

## Manage With acprctl

Download the matching `acprctl` archive from GitHub Releases. It includes `skills/acprctl/`.

If your operations environment uses an agent with skill support, install `skills/acprctl` into the agent's skills directory. Then ask the agent to use the `acprctl` skill to manage this registry; the agent will follow the bundled command reference and call `acprctl` for checks, reviews, scans, publishing, and configuration management.

First configure:

```bash
acprctl configure \
  --server-url https://registry.example.com \
  --username admin \
  --password '<admin-password>'
```

Common checks:

```bash
acprctl stats
acprctl plugin list
acprctl review list
acprctl config list
```

If the stack is currently exposed over HTTP only:

```bash
acprctl --server-url http://203.0.113.10:3001 stats
```

## Upgrade

With the default `IMAGE_TAG=latest`, pull and recreate the stack:

```bash
docker compose --env-file .env -f compose.yml pull
docker compose --env-file .env -f compose.yml up -d
```

With Caddy enabled:

```bash
docker compose --env-file .env -f compose.yml -f compose.caddy.yml pull
docker compose --env-file .env -f compose.yml -f compose.caddy.yml up -d
```

To pin or roll back to a specific version, first change `IMAGE_TAG` in `.env` to that tag.

## Checks

```bash
docker compose --env-file .env -f compose.yml ps
docker compose --env-file .env -f compose.yml logs -f backend worker dashboard
curl -fsS -H "Host: ${HEALTHCHECK_HOST}" http://127.0.0.1:${DASHBOARD_PORT}/api/v1/health
```

Caddy mode:

```bash
docker compose --env-file .env -f compose.yml -f compose.caddy.yml logs -f caddy
curl -fsS ${PUBLIC_ORIGIN}/api/v1/health
```
