# Dev middleware

Local middleware for development: PostgreSQL, Redis, SeaweedFS.
Lightweight defaults for 2C2G ~ 4C4G machines.

```bash
cd dev
cp .env.example .env
docker compose up -d
```

Then start the backend from the repo root:

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
| postgres | 512m | 1.0 | 5432 |
| redis | 128m | 0.25 | 6379 |
| seaweedfs | 256m | 0.5 | 8333 (S3) / 8888 (UI) / 9333 (master) |

The registry app will create the S3 bucket automatically on startup if `S3_AUTO_CREATE_BUCKET=true`.
