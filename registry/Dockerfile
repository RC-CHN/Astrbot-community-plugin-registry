FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project metadata and lockfile
COPY pyproject.toml uv.lock ./

# Copy source code
COPY src/ ./src/

# Install dependencies and the project
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uv", "run", "serve"]
