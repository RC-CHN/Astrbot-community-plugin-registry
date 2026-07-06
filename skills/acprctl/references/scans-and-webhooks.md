# Scans and Webhooks

Use this reference for VirusTotal, LLM scanning, scan waits, and GitHub webhook setup.

## Scan Providers

Supported provider names:

```text
virustotal
llm_agent
all
```

Runtime config keys:

```text
SCAN_PASS_WHEN_UNCONFIGURED
SCAN_UNCONFIGURED_MESSAGE
VIRUSTOTAL_API_KEY
VIRUSTOTAL_TIMEOUT_SECONDS
VIRUSTOTAL_POLL_INTERVAL_SECONDS
VIRUSTOTAL_MAX_POLL_ATTEMPTS
VIRUSTOTAL_MAX_DIRECT_UPLOAD_BYTES
LLM_AGENT_ENABLED
LLM_AGENT_BASE_URL
LLM_AGENT_MODEL
LLM_AGENT_API_KEY
LLM_AGENT_MAX_CONTEXT_CHARS
```

Inspect scan config without revealing secret values:

```bash
acprctl config list
```

Enable LLM scanning:

```bash
acprctl config set \
  --key LLM_AGENT_ENABLED --value true \
  --key LLM_AGENT_BASE_URL --value https://example.com/v1 \
  --key LLM_AGENT_MODEL --value deepseek-v4-flash \
  --key LLM_AGENT_API_KEY --value '<api-key>'
```

Enable VirusTotal:

```bash
acprctl config set --key VIRUSTOTAL_API_KEY --value '<vt-api-key>'
```

Allow publishing when automatic scans are deliberately disabled to save resources:

```bash
acprctl config set --key SCAN_PASS_WHEN_UNCONFIGURED --value true
```

Strict production default:

```bash
acprctl config set --key SCAN_PASS_WHEN_UNCONFIGURED --value false
```

## Scan Execution

Run all scans for a version:

```bash
acprctl plugin scan <plugin-key|id> --version v1.0.0 --wait --wait-timeout 300s
```

Run one provider:

```bash
acprctl plugin version scan run <plugin-key|id> \
  --version v1.0.0 \
  --provider llm_agent \
  --wait
```

Skip a provider:

```bash
acprctl plugin version scan skip <plugin-key|id> \
  --version v1.0.0 \
  --provider virustotal
```

`--wait` polls plugin detail until the selected providers have non-pending scan results, a provider fails, the build fails, or timeout occurs.

## Queue and Parallelism

Build and scan requests enter the backend task queue when Redis is available. Worker concurrency comes from the number of worker containers/processes. Scan provider execution inside one scan task is provider-parallel: VirusTotal and LLM scans are launched together when both providers are requested.

If scans never complete:

```bash
docker compose --env-file .env -f compose.yml logs -f worker
acprctl plugin show <plugin-key|id>
acprctl config list
```

Look for missing provider config, queue failures, S3 artifact download errors, and worker restarts.

## GitHub Webhook Purpose

The GitHub webhook is for already registered plugins. On a repository push, it:

1. Verifies `X-Hub-Signature-256` with `GITHUB_WEBHOOK_SECRET`.
2. Reads `repository.html_url` and `ref` from the GitHub payload.
3. Finds a plugin whose `repo_url` exactly matches `repository.html_url`.
4. Records a `webhook_events` row.
5. Enqueues a `build` task with `version=WEBHOOK_AUTO_VERSION` and `ref=<branch>`.

Endpoint:

```text
POST /api/v1/admin/webhooks/github
```

This endpoint does not use JWT. It must be protected by the GitHub signature secret.

## Webhook Config

Production defaults:

```env
GITHUB_WEBHOOK_REQUIRE_SECRET=true
GITHUB_WEBHOOK_SECRET=
WEBHOOK_AUTO_VERSION=auto
```

Set at runtime:

```bash
acprctl config set \
  --key GITHUB_WEBHOOK_SECRET --value '<random-secret>' \
  --key WEBHOOK_AUTO_VERSION --value auto
```

If `GITHUB_WEBHOOK_REQUIRE_SECRET=true` and no secret is configured, the endpoint returns `503`, which is the safe disabled state.

## GitHub Repository Setup

In the plugin repository, configure a webhook:

```text
Payload URL: https://registry.example.com/api/v1/admin/webhooks/github
Content type: application/json
Secret: same value as GITHUB_WEBHOOK_SECRET
Events: push
```

The plugin must already exist in the registry with `repo_url` equal to GitHub's `repository.html_url`, for example:

```text
https://github.com/org/astrbot_plugin_example
```

Unknown repos are accepted as `{"status":"ignored"}` and recorded as ignored events.

## Local Webhook Verification

Use a registered repository URL in the body:

```bash
body='{"repository":{"html_url":"https://github.com/org/astrbot_plugin_example"},"ref":"refs/heads/main"}'
sig="$(printf '%s' "$body" | openssl dgst -sha256 -hmac "$GITHUB_WEBHOOK_SECRET" -binary | xxd -p -c 256)"
curl -fsS \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: sha256=$sig" \
  --data "$body" \
  "$ACPRCTL_SERVER_URL/api/v1/admin/webhooks/github"
```

Expected responses:

- `{"status":"queued"}` for a registered repository.
- `{"status":"ignored"}` for an unknown repository or missing payload fields.
- `401` for invalid signature.
- `503` when secrets are required but no secret is configured.

