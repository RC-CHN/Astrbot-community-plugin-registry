# Deployment and Connection

Use this reference when an operations agent has only the `acprctl` binary, this skill, the registry URL, and admin credentials or a token.

Do not assume the agent has the project source tree, deployment manifests, `.env` files, Docker Compose files, Kubernetes manifests, or direct access to backend containers. Operate through `acprctl` and the browser-facing service origin.

## Release Bundle

Release archives are named like:

```text
acprctl_<tag>_linux_amd64.tar.gz
acprctl_<tag>_linux_arm64.tar.gz
acprctl_<tag>_darwin_amd64.tar.gz
acprctl_<tag>_darwin_arm64.tar.gz
acprctl_<tag>_windows_amd64.zip
acprctl_<tag>_windows_arm64.zip
SHA256SUMS
```

Each archive contains:

- `acprctl`
- `README.md`
- `skills/acprctl/`

Use the bundled skill folder with the bundled binary. Do not require the registry source repository.

## Binary Check

```bash
acprctl --help
```

Expected help includes at least:

```text
config list|set|providers
plugin list|show|inspect-repo|resolve-ref|submit|upload|update|delete|set-status|build|scan|version
review list|approve|publish|skip|disable|delete
```

If `config providers` is missing, the binary is older than the provider-management workflow. Use `acprctl config set --key SCAN_ENABLED_PROVIDERS --value ...` as a fallback, but preserve existing providers manually.

## Server URL Rules

Pass the browser-facing service origin:

```bash
--server-url https://registry.example.com
--server-url http://203.0.113.10:3001
--server-url http://localhost:3001
```

These are accepted and normalized:

```bash
--server-url https://registry.example.com
--server-url https://registry.example.com/api
--server-url https://registry.example.com/api/v1
```

Do not point `acprctl` at a private backend container port unless the operator explicitly says that private endpoint is the supported administrative entrypoint. Production should normally expose dashboard/Caddy/nginx, which proxies `/api/v1/...`.

## One-Off Agent Connection

Prefer environment variables for ephemeral agent runs:

```bash
export ACPRCTL_SERVER_URL=https://registry.example.com
export ACPRCTL_USERNAME=admin
export ACPRCTL_PASSWORD='<admin-password>'
export ACPRCTL_FORMAT=json
export ACPRCTL_WAIT_INTERVAL=3s
export ACPRCTL_WAIT_TIMEOUT=300s

acprctl stats
acprctl review list
```

If a bearer token is supplied:

```bash
export ACPRCTL_SERVER_URL=https://registry.example.com
export ACPRCTL_TOKEN='<bearer-token>'
acprctl stats
```

Do not print secrets in final answers.

## Local Config

Use local config only when it is appropriate to persist credentials on the current machine and user account:

```bash
acprctl configure \
  --server-url https://registry.example.com \
  --username admin \
  --password '<admin-password>' \
  --format json
```

`configure` validates login and stores a token. The config file is created with mode `0600`.

## Connection Smoke Test

```bash
curl -fsS https://registry.example.com/api/v1/health
acprctl --format json stats
acprctl --format json plugin list --page-size 5
acprctl --format json review list --page-size 5
acprctl --format json config list
```

If HTTPS is not ready and the operator provided temporary HTTP:

```bash
curl -fsS http://203.0.113.10:3001/api/v1/health
acprctl --server-url http://203.0.113.10:3001 --format json stats
```

## Runtime Configuration Surface

Use `acprctl config list` to inspect:

- `effective_values`: active runtime values after overrides
- `values`: DB-backed runtime overrides
- `sensitive_status`: whether secrets are configured without revealing them
- `deployment_values`: read-only process/deployment values

Use `acprctl config set` for writable runtime overrides:

```bash
acprctl config set --key PUBLIC_CACHE_MAX_AGE --value 60
acprctl config set --key WEBHOOK_AUTO_VERSION --value auto
acprctl config set --key GITHUB_TOKEN --value '<github-token>'
```

Clear a runtime override:

```bash
acprctl config set --key PUBLIC_CACHE_MAX_AGE --value ''
```

`GITHUB_TOKEN` is optional but recommended for production instances that import many GitHub repositories. It avoids anonymous GitHub API rate limits for repository inspection and Git preflight. It is redacted in `config list`; check `sensitive_status.GITHUB_TOKEN` instead of printing the value.

## Scan Provider Management

Use provider commands instead of hand-editing the whole CSV:

```bash
acprctl config providers list
acprctl config providers enable virustotal
acprctl config providers enable llm_agent
acprctl config providers enable clamav
acprctl config providers disable clamav
```

Provider commands preserve other enabled providers. Supported providers are `virustotal`, `llm_agent`, and `clamav`.

If the binary lacks `config providers`, fallback:

```bash
acprctl config list
acprctl config set --key SCAN_ENABLED_PROVIDERS --value virustotal,llm_agent
```

Before using fallback, inspect the current value and preserve providers that should remain enabled.

## Platform-Level Changes

Some changes cannot be completed by an agent that only has `acprctl`:

- starting or scaling worker processes
- starting ClamAV/clamd
- changing container images or release tags
- changing load balancer, DNS, TLS certificates, or storage
- reading service logs when the platform does not expose them through another tool

When these are required, report the exact runtime evidence from `acprctl` and ask the operator with host/cluster access to perform the platform action. Do not invent source-tree paths or deployment commands.

## ClamAV Operational Boundary

`acprctl` can configure the registry to use a reachable clamd endpoint:

```bash
acprctl config providers enable clamav
acprctl config set \
  --key CLAMAV_HOST --value clamav \
  --key CLAMAV_PORT --value 3310
```

Starting clamd itself is a platform operation. If scans fail with connection errors, collect:

```bash
acprctl --format json config list
acprctl --format json plugin show <plugin-key-or-id>
```

Then ask the platform operator to verify clamd reachability from backend and worker.

## Release and Upgrade Notes

The `acprctl` binary and `skills/acprctl` should come from the same release archive. After replacing the binary:

```bash
acprctl --help
acprctl --format json stats
```

If a new skill describes a command that the binary does not support, treat the binary as stale and use the documented fallback command when available.
