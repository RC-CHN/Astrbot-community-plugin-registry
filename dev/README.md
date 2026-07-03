# Dev middleware

Local middleware for development: PostgreSQL, Redis, SeaweedFS.
This compose file intentionally does not run the registry API or worker; run those
from the host with `uv` for faster edit/test cycles.

```bash
cd dev
cp .env.example .env
docker compose up -d
```

This compose stack uses the explicit project name `astrbot-registry-dev`, with
container names like `astrbot-registry-dev-postgres`. This avoids collisions with
other repositories that also live in a directory named `dev`.

If you previously started this file before the project name was added, stop the
old default-namespace containers first to free ports:

```bash
docker compose -p dev -f compose.yml --env-file .env stop postgres redis seaweedfs
```

Then start the backend from the repo root. If you changed ports or credentials in
`dev/.env`, copy the matching `DATABASE_URL`, `REDIS_URL`, `S3_ENDPOINT`, and
`S3_PUBLIC_URL` values into the root `.env`.

```bash
cd ..
cp .env.example .env
cd registry
uv run alembic upgrade head
uv run serve
```

Run the background worker in a second terminal when testing build/scan queues:

```bash
cd registry
uv run python -m astrbot_registry.worker
```

Services and resource limits:

| Service | Memory | CPUs | Port |
|---------|--------|------|------|
| postgres | `PG_MEM_LIMIT` | `PG_CPUS` | `PG_PORT` |
| redis | `REDIS_MEM_LIMIT` | `REDIS_CPUS` | `REDIS_PORT` |
| seaweedfs | `S3_MEM_LIMIT` | `S3_CPUS` | `S3_PORT` / `S3_FILER_PORT` / `S3_MASTER_PORT` |

The registry app will create the S3 bucket automatically on startup if `S3_AUTO_CREATE_BUCKET=true`.

Useful checks:

```bash
docker compose ps
docker compose logs -f postgres redis seaweedfs
```

The S3 credentials used by SeaweedFS are defined in `s3.json`. Keep them in sync
with `S3_ACCESS_KEY` and `S3_SECRET_KEY`.
