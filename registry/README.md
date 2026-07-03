# astrbot-registry

Backend API server for the AstrBot community plugin registry.

## Quick start

```bash
uv sync
uv run alembic upgrade head
uv run serve
```

Run the worker for queued build/scan jobs:

```bash
uv run python -m astrbot_registry.worker
```

## Development

```bash
uv run pytest
uv run alembic revision --autogenerate -m "init"
uv run alembic upgrade head
uv run ruff check
```
