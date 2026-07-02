# astrbot-registry

Backend API server for the AstrBot community plugin registry.

## Quick start

```bash
uv sync
uv run serve
```

## Development

```bash
uv run pytest
uv run alembic revision --autogenerate -m "init"
uv run alembic upgrade head
```
