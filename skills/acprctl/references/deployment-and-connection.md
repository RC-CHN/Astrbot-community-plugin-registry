# Deployment and Connection

Use this reference when connecting `acprctl` to dev, local production, or public production deployments.

## Release Artifacts

GitHub Releases attach platform archives named like:

```text
acprctl_<tag>_linux_amd64.tar.gz
acprctl_<tag>_linux_arm64.tar.gz
acprctl_<tag>_darwin_amd64.tar.gz
acprctl_<tag>_darwin_arm64.tar.gz
acprctl_<tag>_windows_amd64.zip
acprctl_<tag>_windows_arm64.zip
SHA256SUMS
```

Each archive includes:

- `acprctl` binary
- `README.md`
- `skills/acprctl/`

Install the bundled `skills/acprctl` folder into the target agent's skills directory when the user wants agent-assisted registry operations.

## Server URL Rules

Pass the browser-facing service origin:

```bash
--server-url https://registry.example.com
--server-url http://localhost:3001
```

These are accepted and normalized:

```bash
--server-url https://registry.example.com
--server-url https://registry.example.com/api
--server-url https://registry.example.com/api/v1
```

Do not point `acprctl` at the backend container's private `:8000` port in production. The dashboard/Caddy/nginx entrypoint must proxy `/api/v1/...` to the backend.

## Dev Stack

Check local services:

```bash
docker compose -f dev/compose.yml ps
curl -fsS http://localhost:3001/api/v1/health
```

Use default dev credentials only for the dev stack:

```bash
./acprctl --server-url http://localhost:3001 --username admin --password admin123456 stats
```

Write a local config when repeatedly testing:

```bash
./acprctl configure \
  --server-url http://localhost:3001 \
  --username admin \
  --password admin123456 \
  --format json
```

## Production HTTP Mode

`deploy/compose.yml` exposes dashboard nginx over HTTP:

```text
${DASHBOARD_BIND:-0.0.0.0}:${DASHBOARD_PORT:-3001} -> dashboard:80
```

Use this mode when another reverse proxy, load balancer, or CDN terminates TLS.

Important `.env` values:

```env
PUBLIC_HOST=registry.example.com
PUBLIC_ORIGIN=https://registry.example.com
TRUSTED_HOSTS=registry.example.com
HEALTHCHECK_HOST=registry.example.com
DASHBOARD_BIND=0.0.0.0
DASHBOARD_PORT=3001
```

If the TLS terminator is on the same host:

```env
DASHBOARD_BIND=127.0.0.1
```

Then connect:

```bash
acprctl --server-url https://registry.example.com --username admin --password '<admin-password>' stats
```

For temporary HTTP-only testing:

```bash
acprctl --server-url http://203.0.113.10:3001 --username admin --password '<admin-password>' stats
```

## Production Caddy Mode

Layer `deploy/compose.caddy.yml` on top of `deploy/compose.yml` when the stack should terminate TLS itself.

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

IP certificate mode requires `PUBLIC_HOST` to be the public IP and ports `80/443` to be reachable by Let's Encrypt:

```env
PUBLIC_HOST=203.0.113.10
PUBLIC_ORIGIN=https://203.0.113.10
TRUSTED_HOSTS=203.0.113.10
HEALTHCHECK_HOST=203.0.113.10
ACME_EMAIL=admin@example.com
```

Local `localhost` cannot receive a real Let's Encrypt certificate. Use Caddy `tls internal` only for local reverse-proxy testing.

## Image Tags

Deployment defaults to:

```env
IMAGE_TAG=latest
```

Use `latest` for straightforward updates. Pin a version for reproducible deployment or rollback:

```env
IMAGE_TAG=v0.1.0
```

If `latest` is not available in the image registry yet, pin `IMAGE_TAG` to a known existing tag.

## Required Production Secrets

At minimum set:

```env
PG_PASSWORD=
S3_ACCESS_KEY=
S3_SECRET_KEY=
JWT_SECRET=
BOOTSTRAP_ADMIN_PASSWORD=
```

`deploy/s3.json` must contain the same S3 access key and secret as `.env`.
