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

## CI and releases

GitHub Actions are split into CI and tag-based release:

- `CI` runs on `main`, pull requests, and `v*` tags. It checks the registry
  backend, `acprctl`, dashboard build, and Docker image builds.
- `Release` runs on `v*` tags. It waits for CI to pass on the tagged commit,
  then publishes GHCR images and attaches `acprctl` binaries to the GitHub
  release.

Release image names:

- `ghcr.io/<owner>/<repo>-backend:<tag>`
- `ghcr.io/<owner>/<repo>-worker:<tag>`
- `ghcr.io/<owner>/<repo>-dashboard:<tag>`

Release assets:

- `acprctl_<tag>_linux_amd64.tar.gz`
- `acprctl_<tag>_linux_arm64.tar.gz`
- `acprctl_<tag>_darwin_amd64.tar.gz`
- `acprctl_<tag>_darwin_arm64.tar.gz`
- `acprctl_<tag>_windows_amd64.zip`
- `acprctl_<tag>_windows_arm64.zip`
- `SHA256SUMS`

Recommended flow:

```bash
git push origin main
# wait for CI to pass
git tag v0.1.0
git push origin v0.1.0
```
