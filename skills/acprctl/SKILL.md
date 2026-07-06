---
name: acprctl
description: Use this skill when the user wants Codex to administer, validate, troubleshoot, or document AstrBot Community Plugin Registry using a prebuilt acprctl binary. Trigger for connecting to a registry, plugin submission/upload/build/scan/review/publish, runtime config, cache refresh, wait behavior, GitHub webhook setup, production health checks, or agent-operated registry maintenance from an installed CLI.
---

# acprctl

Use this skill to operate AstrBot Community Plugin Registry through the standalone `acprctl` admin CLI.

Assume the agent may only have:

- the `acprctl` binary
- this skill folder
- the registry service URL
- admin credentials or an admin token
- optional shell tools such as `curl`, `openssl`, and `jq`

Use the installed CLI and the live registry service as the operating surface.

## Reference Map

Load only the reference needed for the task:

- `references/command-reference.md`: exact command syntax, flags, config precedence, output, and exit codes.
- `references/operations-workflows.md`: step-by-step workflows for submit, upload, build, scan, review, publish, config, and cache work.
- `references/deployment-and-connection.md`: dev/prod connection, HTTP vs Caddy TLS deployment, release assets, GHCR image tags, and agent skill installation.
- `references/scans-and-webhooks.md`: VirusTotal/LLM scan configuration, scan waits, GitHub webhook setup, and webhook verification.
- `references/validation-troubleshooting.md`: service validation, production health checks, common failures, and recovery steps.
- `references/implementation-coverage.md`: released CLI capability coverage and known operational boundaries.

## Core Rules

- Connect to the service origin, not to a private backend container. The CLI normalizes the origin to `/api/v1`.
- Prefer `--format json` for automation and agent use; use table output only for human inspection.
- Use command flags or `ACPRCTL_*` environment variables for agent runs. Avoid writing shared config files on multi-user hosts.
- Do not bypass backend publishing rules. A publish path must still satisfy build, scan, status, and latest-version constraints.
- Treat destructive operations as explicit: use `--yes` only when the user clearly asked for deletion.
- Never print or persist admin passwords, API keys, tokens, webhook secrets, VT keys, or LLM keys in conversation output.

## Fast Path

Check that the binary is available:

```bash
acprctl --help
```

Connect to production:

```bash
acprctl configure \
  --server-url https://registry.example.com \
  --username admin \
  --password '<admin-password>' \
  --format json

acprctl stats
acprctl review list
```

Use environment variables for one-off agent runs:

```bash
ACPRCTL_SERVER_URL=https://registry.example.com \
ACPRCTL_USERNAME=admin \
ACPRCTL_PASSWORD='<admin-password>' \
acprctl --format json stats
```

If a task involves more than inspection, read `references/operations-workflows.md` before acting.
