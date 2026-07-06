# AstrBot Community Plugin Registry

Community plugin registry service for AstrBot. It includes plugin metadata, version artifacts, build and scan queues, an admin dashboard, and a standalone admin CLI.

Main directories:

- `registry/`: FastAPI backend and worker.
- `dashboard/`: Vue admin dashboard.
- `acprctl/`: standalone Go admin CLI.
- `skills/acprctl/`: companion skill bundled with `acprctl` release archives.
- `dev/`: local development stack.
- `deploy/`: production deployment files.
- `docs/`: design documents.

Chinese documentation: [README.md](README.md)

## Deployment Modes

Production deployment uses GHCR release images by default:

- `ghcr.io/rc-chn/astrbot-community-plugin-registry-backend:latest`
- `ghcr.io/rc-chn/astrbot-community-plugin-registry-worker:latest`
- `ghcr.io/rc-chn/astrbot-community-plugin-registry-dashboard:latest`

Deployments follow `latest` by default. Set a concrete `IMAGE_TAG` in `deploy/.env` when you need to pin or roll back.

`deploy/` provides two recommended modes.

### Mode 1: Expose HTTP and terminate TLS externally

This is the default mode. The dashboard nginx exposes an HTTP port, and an external Caddy, nginx, Traefik, load balancer, or CDN terminates HTTPS/TLS.

```bash
cd deploy
cp .env.example .env
cp s3.json.example s3.json
# edit .env and s3.json
docker compose --env-file .env -f compose.yml pull
docker compose --env-file .env -f compose.yml up -d
```

Default exposure:

```text
0.0.0.0:${DASHBOARD_PORT:-3001} -> dashboard:80
```

If the TLS terminator runs on the same host, set `DASHBOARD_BIND=127.0.0.1` in `.env`.

### Mode 2: Run Caddy with the stack

If the stack should handle HTTPS itself, add `compose.caddy.yml`. Caddy listens on `80/443` and reverse proxies to the dashboard.

Domain certificate:

```bash
cd deploy
cp caddy/Caddyfile.domain.example caddy/Caddyfile
docker compose --env-file .env -f compose.yml -f compose.caddy.yml up -d
```

Public IP certificate:

```bash
cd deploy
cp caddy/Caddyfile.ip.example caddy/Caddyfile
docker compose --env-file .env -f compose.yml -f compose.caddy.yml up -d
```

Let's Encrypt currently supports IP address certificates through the `shortlived` profile. These certificates are valid for about 160 hours. Caddy must use a version that supports ACME profile selection, and the IP-mode Caddyfile requests `profile shortlived`.

References:

- https://letsencrypt.org/docs/profiles/
- https://caddyserver.com/docs/caddyfile/directives/tls

See [deploy/README_en.md](deploy/README_en.md) for full deployment details.

## Manage With acprctl

Download the matching `acprctl` archive from GitHub Releases. The archive includes the binary, README, and `skills/acprctl/`.

If you use an agent with skill support, install the bundled `skills/acprctl` directory into the agent's skills directory. Then ask the agent to use the `acprctl` skill; it will follow the bundled command reference to connect with `acprctl` and handle status checks, plugin review, scan triggers, publishing, and runtime configuration.

Connect to production:

```bash
acprctl configure \
  --server-url https://registry.example.com \
  --username admin \
  --password '<admin-password>'

acprctl stats
acprctl plugin list
```

If the stack is temporarily exposed over HTTP before TLS is configured:

```bash
acprctl --server-url http://<host>:3001 stats
```

## Local Development

```bash
uv sync
cp .env.example .env
uv run serve
```

With the full local middleware stack:

```bash
cd dev
cp .env.example .env
docker compose up -d

cd ..
cp .env.example .env
uv run serve
```

See [dev/README.md](dev/README.md) for local stack details.
