# Validation and Troubleshooting

Use this reference when operating `acprctl` from an installed CLI against a live registry service.

## Required Inputs

Collect these before operating:

```text
Registry URL: https://registry.example.com
Admin username: admin
Admin password or bearer token: <secret>
Expected TLS mode: public HTTPS, temporary HTTP, or private/internal TLS
Whether automatic scans should be enabled: yes/no
Whether webhook automation should be enabled: yes/no
```

Do not display secrets in final answers. Refer to them as configured, missing, or redacted.

## Binary and Connection Smoke Test

Check the CLI:

```bash
acprctl --help
```

Check the public health endpoint:

```bash
curl -fsS https://registry.example.com/api/v1/health
```

If the deployment is temporarily HTTP-only:

```bash
curl -fsS http://203.0.113.10:3001/api/v1/health
```

Authenticate and inspect:

```bash
acprctl \
  --server-url https://registry.example.com \
  --username admin \
  --password '<admin-password>' \
  --format json \
  stats
```

Expected `stats` output has at least:

```json
{
  "pending_plugins": 0,
  "total_plugins": 0
}
```

Then run:

```bash
acprctl --format json plugin list --page-size 5
acprctl --format json review list
acprctl --format json worker status
acprctl --format json task list --page-size 20
acprctl --format json config list
```

## Configure for Repeated Use

Write local config only when appropriate for the current machine/user:

```bash
acprctl configure \
  --server-url https://registry.example.com \
  --username admin \
  --password '<admin-password>' \
  --format json
```

For ephemeral agents, prefer environment variables:

```bash
export ACPRCTL_SERVER_URL=https://registry.example.com
export ACPRCTL_USERNAME=admin
export ACPRCTL_PASSWORD='<admin-password>'
export ACPRCTL_FORMAT=json
export ACPRCTL_WAIT_INTERVAL=3s
export ACPRCTL_WAIT_TIMEOUT=300s
```

Use a token instead of password when supplied:

```bash
export ACPRCTL_TOKEN='<bearer-token>'
acprctl stats
```

## Exit Code Handling

`acprctl` writes structured errors to stderr. Branch on exit code first, then inspect JSON details.

```text
0 success
1 general error
2 auth failure
3 destructive action missing --yes
4 not found
5 wait timeout
6 validation or bad input
```

Example not found response:

```json
{
  "error": "Plugin not found",
  "status": 404,
  "code": 4
}
```

## Authentication Failures

Symptoms:

- `acprctl` exits `2`
- API returns `401`
- `auth login` fails

Checks:

```bash
acprctl --format json auth login
```

Actions:

- Confirm the admin username.
- Confirm the admin password or token has not expired.
- If repeated failures occur, wait for login rate-limit block expiry or use a known valid admin token.
- Do not keep retrying rapidly; the service may enforce login rate limits.

## URL, Host, and TLS Failures

Symptoms:

- `curl /api/v1/health` fails
- `acprctl` exits `1` with connection refused, timeout, TLS, or host errors
- Browser works but CLI fails, or CLI works only with HTTP

Checks:

```bash
curl -v https://registry.example.com/api/v1/health
acprctl --server-url https://registry.example.com --verbose stats
```

Common causes:

- Wrong `--server-url`; use the browser-facing origin, not `/admin` or a private container address.
- TLS certificate not valid for the hostname or IP.
- Service is exposed on a nonstandard port and the port is missing from the URL.
- Reverse proxy does not forward `/api/v1/` to the backend.
- Server-side trusted-host settings do not include the requested host/IP.

Recovery:

- Try the exact browser-facing URL.
- If using direct HTTP temporarily, include the port, for example `http://203.0.113.10:3001`.
- If using a private CA or local Caddy internal CA, configure the OS trust store or set `SSL_CERT_FILE` for the command environment.

## Baseline State Inspection

Use this block before changing anything:

```bash
acprctl --format json stats
acprctl --format json plugin list --page-size 20
acprctl --format json review list --page-size 20
acprctl --format json worker status
acprctl --format json task list --page-size 20
acprctl --format json config list
```

In `config list`:

- `deployment_values` shows process-level deployment config.
- `effective_values` shows active runtime values after overrides.
- `values` shows runtime overrides.
- `sensitive_status` shows whether secrets are configured without revealing them.

## Wait Timeouts

Symptoms:

- `acprctl` exits `5`
- `--wait` did not observe build or scan completion

Immediate inspection:

```bash
acprctl --format json plugin show <plugin-key-or-id>
acprctl --format json plugin version list <plugin-key-or-id>
acprctl --format json worker status
acprctl --format json task list --page-size 50
acprctl --format json config list
```

Interpretation:

- `build_status=pending` or `building`: worker may be busy or not processing tasks.
- `build_status=failed`: inspect `build_log` in `plugin show`.
- scan provider `mode=pending`: scan task has not completed; VirusTotal may be waiting on asynchronous remote analysis polling.
- scan provider `mode=error`: inspect the provider message.
- `worker status` with no active workers: the worker process is not heartbeating or cannot reach Redis.
- `task list --status dead`: inspect `last_error`, fix the root cause, then retry the task.
- `task list --status delayed --type virustotal_poll`: VirusTotal polling is scheduled for `next_run_at`.

Recovery:

```bash
acprctl plugin build <plugin-key-or-id> --wait --wait-timeout 600s
acprctl plugin scan <plugin-key-or-id> --version <version> --wait --wait-timeout 600s
```

If a dead task exists and the cause is fixed:

```bash
acprctl task retry <task-id>
```

If the status never changes and there are no active workers, ask the operator with host access to restart or scale the worker process.

## Build Failures

Inspect:

```bash
acprctl --format json plugin show <plugin-key-or-id>
```

Look at:

- `versions[].build_status`
- `versions[].build_log`
- `versions[].commit_sha`
- `versions[].download_url`

Common causes:

- Repository URL is unreachable or not allowed.
- Branch/tag/ref does not exist.
- Plugin metadata is missing or invalid.
- Release zip exceeds configured size limits.
- Object storage credentials or bucket access are broken.

Before retrying a Git build, inspect or resolve the repository through the backend provider:

```bash
acprctl --format json plugin inspect-repo \
  --repo-url <github-repo-url> \
  --ref-type branch \
  --ref main

acprctl --format json plugin resolve-ref \
  --repo-url <github-repo-url> \
  --ref-type branch \
  --ref main
```

If GitHub returns a rate-limit or access-denied error, set a global `GITHUB_TOKEN` in runtime config or pass a temporary `--github-token` to `inspect-repo`, `resolve-ref`, `plugin submit`, or `plugin build`. Do not confuse `--github-token` with global `--token`; `--token` authenticates to the registry itself.

Retry with explicit ref and longer wait:

```bash
acprctl plugin build <plugin-key-or-id> \
  --ref main \
  --changelog "Retry build" \
  --wait \
  --wait-timeout 600s
```

For Git submit/build, omit `--version` to keep the selected commit's `metadata.yaml` version. Add `--version <version>` only when the operator intentionally wants the packaged metadata version rewritten.

## Scan Failures

Inspect:

```bash
acprctl --format json plugin show <plugin-key-or-id>
acprctl --format json config list
```

Check `sensitive_status` and `effective_values` for:

```text
SCAN_ENABLED_PROVIDERS
GITHUB_TOKEN
VIRUSTOTAL_API_KEY
LLM_AGENT_BASE_URL
LLM_AGENT_MODEL
LLM_AGENT_API_KEY
CLAMAV_HOST
CLAMAV_PORT
SCAN_PASS_WHEN_UNCONFIGURED
```

If GitHub repository inspection returns an API rate-limit error, configure a global token:

```bash
acprctl config set --key GITHUB_TOKEN --value '<github-token>'
```

Then re-check `sensitive_status.GITHUB_TOKEN`. Do not print the token value.

Run all providers:

```bash
acprctl plugin scan <plugin-key-or-id> --version <version> --wait --wait-timeout 600s
```

Run one provider:

```bash
acprctl plugin version scan run <plugin-key-or-id> \
  --version <version> \
  --provider clamav \
  --wait \
  --wait-timeout 600s
```

Skip a provider only after explicit manual decision:

```bash
acprctl plugin version scan skip <plugin-key-or-id> \
  --version <version> \
  --provider virustotal
```

## Publish Blocked

Before publishing:

```bash
acprctl --format json plugin show <plugin-key-or-id>
```

Confirm:

- plugin exists
- target version exists
- target version build succeeded
- scan results pass or have been explicitly skipped according to policy
- the human review decision is intentional

Publish:

```bash
acprctl review publish <plugin-key-or-id> --version <version>
```

If publish fails, inspect the blocking state:

```bash
acprctl --format json plugin show <plugin-key-or-id>
```

Publishing is atomic on the backend. It should not leave a plugin half-published; fix the reported blocker, then retry `acprctl review publish` or `acprctl review skip` according to the intended human review result.

## Webhook Verification

Check config:

```bash
acprctl --format json config list
```

Required:

```text
GITHUB_WEBHOOK_SECRET configured
GITHUB_WEBHOOK_REQUIRE_SECRET true at deployment level
WEBHOOK_AUTO_VERSION usually auto
```

Create a signed local test request with a repository URL that is already registered in the registry:

```bash
export REGISTRY_URL=https://registry.example.com
export GITHUB_WEBHOOK_SECRET='<secret>'
body='{"repository":{"html_url":"https://github.com/org/astrbot_plugin_example"},"ref":"refs/heads/main"}'
sig="$(printf '%s' "$body" | openssl dgst -sha256 -hmac "$GITHUB_WEBHOOK_SECRET" -binary | xxd -p -c 256)"
curl -fsS \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: sha256=$sig" \
  --data "$body" \
  "$REGISTRY_URL/api/v1/admin/webhooks/github"
```

Expected:

- `{"status":"queued"}` for a registered repository.
- `{"status":"ignored"}` when the repository URL is not registered or payload fields are missing.
- `401` for invalid signature.
- `503` when signature secret is required but missing.

If it returns `ignored`, compare the registered plugin `repo_url` with GitHub `repository.html_url`; they must match exactly.

## Runtime Config Recovery

Set or repair scan config:

```bash
acprctl config providers enable virustotal
acprctl config providers enable llm_agent
acprctl config set \
  --key SCAN_PASS_WHEN_UNCONFIGURED --value false \
  --key LLM_AGENT_BASE_URL --value https://example.com/v1 \
  --key LLM_AGENT_MODEL --value deepseek-v4-flash \
  --key LLM_AGENT_API_KEY --value '<api-key>'
```

If `config providers` is unavailable in the installed binary, inspect the current `SCAN_ENABLED_PROVIDERS` value and update it with `config set` while preserving providers that should stay enabled.

Set webhook config:

```bash
acprctl config set \
  --key GITHUB_WEBHOOK_SECRET --value '<secret>' \
  --key WEBHOOK_AUTO_VERSION --value auto
```

Refresh public registry cache after status or registry-current-version repairs:

```bash
acprctl cache refresh
```

## Destructive Operations

Never delete without explicit user confirmation.

Delete a plugin:

```bash
acprctl plugin delete <plugin-key-or-id> --yes
```

This removes the plugin, all version records, and all version artifacts.

Delete one version:

```bash
acprctl plugin version delete <plugin-key-or-id> --version <version> --yes
```

This removes only the selected version record and artifact.

Delete from review queue:

```bash
acprctl review delete <plugin-key-or-id> --yes
```

If `--yes` is omitted, exit code `3` is expected.
