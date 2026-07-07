# Dev stack

One-shot dev stack: PostgreSQL, Redis, SeaweedFS, the registry API, a background
worker, and the dashboard behind an nginx reverse proxy. Only the dashboard port
is exposed; `/api` and `/s3` are proxied internally.

```bash
cd dev
cp .env.example .env   # then edit PUBLIC_HOST / DASHBOARD_PORT if needed
docker compose up -d --build
```

Open the dashboard at `http://${PUBLIC_HOST:-localhost}:${DASHBOARD_PORT:-3001}`.

Default admin login: `admin` / `admin123456` (override with
`BOOTSTRAP_ADMIN_USERNAME` / `BOOTSTRAP_ADMIN_PASSWORD`).

`PUBLIC_HOST` should be the host you open in the browser (e.g. `192.168.44.155`)
because it is used to build public S3 download URLs that are proxied through nginx
at `/s3/`.

## Services

| Service    | Image / build            | Memory | CPUs | Port |
|------------|--------------------------|--------|------|------|
| postgres   | `postgres:16-alpine`     | `PG_MEM_LIMIT` | `PG_CPUS` | internal |
| redis      | `redis:7-alpine`         | `REDIS_MEM_LIMIT` | `REDIS_CPUS` | internal |
| seaweedfs  | `chrislusf/seaweedfs`    | `S3_MEM_LIMIT` | `S3_CPUS` | internal |
| backend    | `dev/Dockerfile.backend` | `BACKEND_MEM_LIMIT` | `BACKEND_CPUS` | internal |
| worker     | `dev/Dockerfile.backend` | `WORKER_MEM_LIMIT` | `WORKER_CPUS` | internal |
| dashboard  | `dev/Dockerfile.dashboard` (nginx) | `DASHBOARD_MEM_LIMIT` | `DASHBOARD_CPUS` | `DASHBOARD_PORT` |

The backend runs database migrations and bootstraps the admin user on startup.
The worker consumes build/scan queues from Redis. The dashboard serves the built
SPA and proxies `/api/`, `/docs`, `/redoc` to the backend and `/s3/` to SeaweedFS.

## Public deployment checklist

Do not expose the stack with the development defaults. For public access, set
`DEPLOYMENT_MODE=production`; the backend will refuse to start until unsafe
defaults are replaced.

Required production changes:

- Set a random `JWT_SECRET` of at least 32 characters.
- Change `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `PG_PASSWORD`, and
  `BOOTSTRAP_ADMIN_PASSWORD`.
- Set `TRUSTED_HOSTS` to the public domain/IP, for example
  `registry.example.com`, and set `HEALTHCHECK_HOST` to one trusted host.
- Set `DOCS_ENABLED=false` and keep `BOOTSTRAP_API_ENABLED=false`.
- Choose the scan policy deliberately. There is no fixed required-provider list:
  existing pending/error/failed scan results block publishing, while skipped
  providers do not. `SCAN_PASS_WHEN_UNCONFIGURED` controls the displayed `pass`
  value for unconfigured skipped providers.
- Optional ClamAV scanning is available through the `clamav` Compose profile:
  add `clamav` to `SCAN_ENABLED_PROVIDERS`, keep `CLAMAV_HOST=clamav`, then run
  `docker compose --profile clamav up -d clamav backend worker`.
- Keep `GITHUB_WEBHOOK_REQUIRE_SECRET=true` and configure
  `GITHUB_WEBHOOK_SECRET` before enabling GitHub webhooks.
- Terminate TLS at the public reverse proxy. If this nginx container is the TLS
  endpoint, set `HSTS_ENABLED=true`; otherwise add HSTS at the outer proxy.

The bundled nginx only exposes plugin objects under `/s3/<bucket>/plugins/` with
`GET`/`HEAD`. It intentionally does not expose SeaweedFS as a public S3 API.

## Host-based development

If you still want to run the API/worker on the host for faster edit/test cycles,
start only the middleware:

```bash
docker compose up -d postgres redis seaweedfs
```

Then copy the matching `DATABASE_URL`, `REDIS_URL`, `S3_ENDPOINT`, and
`S3_PUBLIC_URL` values into the root `.env` (use `localhost` ports) and run:

```bash
cd registry
uv run alembic upgrade head
uv run serve          # API
uv run python -m astrbot_registry.worker   # worker in another terminal
```

## Useful checks

```bash
docker compose ps
docker compose logs -f backend worker dashboard
```

The S3 credentials used by SeaweedFS are defined in `s3.json`. Keep them in sync
with `S3_ACCESS_KEY` and `S3_SECRET_KEY`.
