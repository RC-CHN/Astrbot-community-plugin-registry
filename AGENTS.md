# Agent Guide

This repository contains AstrBot Community Plugin Registry, a production-ready community plugin registry for AstrBot.

## Project Layout

- `registry/`: FastAPI backend, worker code, SQLAlchemy models, Alembic migrations, and Python tests.
- `dashboard/`: Vue admin dashboard served by nginx in production images.
- `acprctl/`: standalone Go administrator CLI.
- `skills/acprctl/`: companion agent skill shipped with `acprctl` release archives.
- `dev/`: local development middleware stack.
- `deploy/`: production deployment files.
- `docker/`: Dockerfiles for backend/worker and dashboard images.
- `docs/`: design documents and interaction notes.
- `.github/workflows/`: CI and release automation.

## Architecture

The production service is composed of:

- PostgreSQL for persistent registry state.
- Redis for cache and task queue.
- SeaweedFS S3 mode for plugin artifacts.
- FastAPI backend for public and admin APIs.
- Worker process for queued submit/build/scan tasks.
- Dashboard nginx for the admin UI and API proxy.
- Optional Caddy TLS layer for in-stack HTTPS.
- `acprctl` for scriptable admin operations.

`acprctl` talks to the browser-facing service origin and uses `/api/v1/admin/...` API routes. Do not require users to connect it to private backend container ports.

## Development Commands

Use `rg` for searches.

Backend:

```bash
uv sync --all-packages --dev --frozen
uv run ruff check registry/src registry/tests
uv run pytest registry/tests -q
```

CLI:

```bash
cd acprctl
gofmt -w main.go main_test.go
go test ./...
go build -o acprctl .
```

Dashboard:

```bash
cd dashboard
npm ci
npm run build
```

Docker image build checks are in `.github/workflows/ci.yml`.

## Local Dev Stack

Use `dev/` for local middleware:

```bash
cd dev
cp .env.example .env
docker compose up -d
```

Then run the app from the repository root with the root `.env` configured for the dev stack.

Dev defaults may use `http://localhost:3001` and `admin/admin123456`; never use those defaults for production.

## Production Deployment

Production files live in `deploy/`.

Docker Compose deployment:

First deployment:

```bash
cd deploy
cp .env.example .env
cp s3.json.example s3.json
```

At minimum, replace:

- `PUBLIC_HOST`
- `PUBLIC_ORIGIN`
- `TRUSTED_HOSTS`
- `HEALTHCHECK_HOST`
- `PG_PASSWORD`
- `S3_ACCESS_KEY`
- `S3_SECRET_KEY`
- `JWT_SECRET`
- `BOOTSTRAP_ADMIN_PASSWORD`

Make `deploy/s3.json` credentials match `S3_ACCESS_KEY` and `S3_SECRET_KEY`.

Default production images:

- `ghcr.io/rc-chn/astrbot-community-plugin-registry-backend:latest`
- `ghcr.io/rc-chn/astrbot-community-plugin-registry-worker:latest`
- `ghcr.io/rc-chn/astrbot-community-plugin-registry-dashboard:latest`

`IMAGE_TAG=latest` is the default. Pin `IMAGE_TAG` to a concrete release tag for reproducible deployments or rollback.

### Mode 1: HTTP Exposed, TLS Terminated Externally

Use:

```bash
docker compose --env-file .env -f compose.yml pull
docker compose --env-file .env -f compose.yml up -d
docker compose --env-file .env -f compose.yml ps
```

Expose:

```text
${DASHBOARD_BIND:-0.0.0.0}:${DASHBOARD_PORT:-3001} -> dashboard:80
```

Set `DASHBOARD_BIND=127.0.0.1` when a same-host reverse proxy terminates TLS. Keep `0.0.0.0` when TLS terminates on another host or load balancer.

### Mode 2: Caddy TLS in the Stack

This mode requires Docker Compose v2.24.4+ because the overlay uses `!override`.

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

IP certificate mode requires a public IP reachable by Let's Encrypt on ports `80/443`, `PUBLIC_HOST=<public-ip>`, and `PUBLIC_ORIGIN=https://<public-ip>`.

Local `localhost` cannot obtain a real Let's Encrypt certificate. Use Caddy internal CA only for local TLS-chain testing.

### Mode 3: Kubernetes

Kubernetes manifests live in `deploy/kubernetes/`.

First deployment:

```bash
cd deploy/kubernetes
cp secret.example.yaml secret.yaml
# edit configmap.yaml, secret.yaml, and ingress.yaml
kubectl apply -f namespace.yaml
kubectl apply -f secret.yaml
kubectl apply -k .
```

The checked-in manifests are a generic base. They do not bind a default IngressClass, TLS issuer, LoadBalancer implementation, or StorageClass. Before applying to a real cluster, adjust `ingress.yaml`, TLS, exposure, and PVC storage settings for that cluster.

## Production Checks

HTTP mode:

```bash
docker compose --env-file .env -f compose.yml ps
docker compose --env-file .env -f compose.yml logs -f backend worker dashboard
curl -fsS -H "Host: ${HEALTHCHECK_HOST}" "http://127.0.0.1:${DASHBOARD_PORT}/api/v1/health"
```

Caddy mode:

```bash
docker compose --env-file .env -f compose.yml -f compose.caddy.yml ps
docker compose --env-file .env -f compose.yml -f compose.caddy.yml logs -f caddy
curl -fsS "${PUBLIC_ORIGIN}/api/v1/health"
```

Admin smoke:

```bash
acprctl --server-url "$PUBLIC_ORIGIN" --username admin --password '<admin-password>' stats
acprctl --server-url "$PUBLIC_ORIGIN" --username admin --password '<admin-password>' plugin list --page-size 5
acprctl --server-url "$PUBLIC_ORIGIN" --username admin --password '<admin-password>' config list
```

## Scanning Policy

Production default:

```env
SCAN_PASS_WHEN_UNCONFIGURED=false
```

This blocks publishing when automatic scans are unavailable. If automatic scanning is intentionally disabled to save resources, set:

```env
SCAN_PASS_WHEN_UNCONFIGURED=true
```

In that mode, rely on manual review and admin controls before publishing.

LLM scanning requires:

- `LLM_AGENT_ENABLED=true`
- `LLM_AGENT_BASE_URL`
- `LLM_AGENT_MODEL`
- `LLM_AGENT_API_KEY`

VirusTotal scanning requires `VIRUSTOTAL_API_KEY`.

## GitHub Webhook

The webhook endpoint is:

```text
POST /api/v1/admin/webhooks/github
```

It is for already registered plugins. GitHub push events are signature-verified, matched by exact `repository.html_url == plugin.repo_url`, recorded in `webhook_events`, and queued as build tasks.

Production should keep:

```env
GITHUB_WEBHOOK_REQUIRE_SECRET=true
GITHUB_WEBHOOK_SECRET=<random-secret>
WEBHOOK_AUTO_VERSION=auto
```

If the secret is required but missing, the endpoint returns `503`, which is the safe disabled state.

## Release Flow

CI runs on `main`, pull requests, and `v*` tags.

Release runs after successful CI for pushed `v*` tags. It publishes:

- backend, worker, and dashboard images with `<tag>`, `latest`, and `sha-<short-sha>` tags
- `acprctl` archives for Linux, macOS, and Windows
- bundled `skills/acprctl`
- `SHA256SUMS`

When replacing an existing release such as `v0.1.0`, update the default branch workflow first, then move the tag to the intended commit and push the tag update. The release workflow checks that the tag points to the CI-tested commit.

## Safety Notes

- Do not commit local deployment secrets. `deploy/s3.json` and `deploy/caddy/Caddyfile` are ignored intentionally.
- Do not revert unrelated user changes in a dirty worktree.
- Do not use dev credentials or wildcard trusted hosts in production.
- Do not expose FastAPI docs or bootstrap APIs in production unless deliberately debugging a private instance.
- Keep `GITHUB_WEBHOOK_REQUIRE_SECRET=true` in production.
- Be explicit with destructive `acprctl` commands and require `--yes`.
- If `latest` image pulls fail before a refreshed release is available, pin `IMAGE_TAG` to a known existing release tag.
