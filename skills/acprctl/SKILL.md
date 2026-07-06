---
name: acprctl
description: Use this skill whenever the user asks to use, build, deploy, test, document, or modify acprctl, the standalone Go CLI for administering AstrBot Community Plugin Registry. Also use it for ACPR admin workflows such as plugin review, publish, scan, build, upload, runtime config changes, cache refresh, or dev-stack verification through acprctl, even if the user only mentions registry administration.
---

# acprctl

Use this skill to work with `acprctl`, the standalone Go admin CLI for AstrBot Community Plugin Registry.

## Progressive References

- Read `references/command-reference.md` when you need exact syntax for any command, flags, examples, or error-code handling.
- Read `references/implementation-coverage.md` when you need to answer whether the Go CLI implements the interaction design, identify gaps, or modify behavior safely.
- Read `docs/acprctl-cli-interaction-design.md` only when you need the full product design. That file may be ignored by git in this workspace.

## Core Rules

- Treat `acprctl/` as the CLI implementation. Do not add the tool under `registry/src/astrbot_registry`.
- Build a single deployable binary from the Go module:
  ```bash
  cd acprctl
  go build -o acprctl .
  ```
- The CLI talks to the backend Admin API through `/api/v1/admin/...`; pass the service origin as `--server-url`, for example `http://localhost:3001`.
- Prefer JSON output for automation. Use `--format table` only for human inspection.
- Do not bypass backend state checks. Publishing a version still requires successful build and passing scans.

## Quick Workflow

1. Confirm the tool builds and tests:
   ```bash
   cd acprctl
   go test ./...
   go build -o acprctl .
   ```

2. For the dev stack, check service health first:
   ```bash
   docker compose -f dev/compose.yml ps
   curl -fsS http://localhost:3001/api/v1/health
   ```

3. Use default dev credentials only for the local dev stack:
   ```bash
   ./acprctl --server-url http://localhost:3001 --username admin --password admin123456 stats
   ```

4. For repeated local use, write a config file:
   ```bash
   ./acprctl configure \
     --server-url http://localhost:3001 \
     --username admin \
     --password admin123456
   ```

## Configuration

Config priority is command flags, then `ACPRCTL_*` environment variables, then `~/.config/acprctl/config.yaml`.

Useful environment variables:

```bash
ACPRCTL_SERVER_URL=http://localhost:3001
ACPRCTL_USERNAME=admin
ACPRCTL_PASSWORD=admin123456
ACPRCTL_TOKEN=...
ACPRCTL_FORMAT=json
ACPRCTL_TIMEOUT=30s
ACPRCTL_WAIT_INTERVAL=3s
ACPRCTL_WAIT_TIMEOUT=120s
```

For CI or agent runs, prefer flags or environment variables over writing a shared config file.

## Common Commands

Use `acprctl stats`, `acprctl plugin list`, `acprctl plugin show`, `acprctl review list`, `acprctl config list`, and `acprctl cache refresh` for quick inspection. For the full command set, including all plugin, version, review, upload, scan, config, and destructive commands, read `references/command-reference.md`.

## Error Handling

Errors are JSON on stderr and include `code`; scripts should branch on the process exit code.

- `2`: auth failure
- `3`: destructive action missing `--yes`
- `4`: not found
- `5`: wait timeout
- `6`: validation or bad input

When a command fails, inspect both the exit code and JSON `detail`. For publish failures, expect backend validation messages about build or scan state.

## Editing Guidance

- Keep the Go CLI dependency-free unless there is a strong reason to add a module dependency.
- If a CLI behavior disagrees with the backend, verify the real API in `registry/src/astrbot_registry/api/admin.py` and dashboard API calls before changing command semantics.
- If changing config responses, preserve the full response shape: `values`, `effective_values`, `sensitive_status`, `sensitive_keys`, and `deployment_values`.
- After CLI edits, run:
  ```bash
  cd acprctl
  gofmt -w main.go main_test.go
  go test ./...
  go build -o /tmp/acprctl-test .
  ```
- After backend API edits, run:
  ```bash
  uv run pytest -q
  uv run ruff check registry/src registry/tests
  ```

## Full Reference

For feature coverage against the interaction design, read `references/implementation-coverage.md`.
