# AstrBot Community Plugin Registry

A community plugin registry system for AstrBot, consisting of:

- `registry/` — FastAPI backend (uv project)
- `dev/` — lightweight local middleware (PostgreSQL, Redis, SeaweedFS)
- `dashboard/` — Vue admin dashboard (TBD)
- `docs/` — design documents

## Quick start

```bash
uv sync
cp .env.example .env
uv run serve
```

## Development with local middleware

```bash
cd dev
cp .env.example .env
docker compose up -d

cd ..
cp .env.example .env
uv run serve
```

See `dev/README.md` for resource limits and details.

