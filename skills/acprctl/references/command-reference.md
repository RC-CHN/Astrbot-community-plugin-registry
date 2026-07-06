# acprctl Command Reference

Use this reference for exact command syntax. The CLI is the Go module in `acprctl/`.

## Contents

- Build and connect
- Global flags and config
- Auth
- Plugin commands
- Version commands
- Review commands
- Runtime config, cache, and stats
- Error handling

## Build and Connect

Build a deployable binary:

```bash
cd acprctl
go test ./...
go build -o acprctl .
```

Use against the dev stack:

```bash
./acprctl --server-url http://localhost:3001 --username admin --password admin123456 stats
```

The CLI accepts a service origin and normalizes it to `/api/v1`. These are equivalent inputs:

```bash
--server-url http://localhost:3001
--server-url http://localhost:3001/api
--server-url http://localhost:3001/api/v1
```

## Global Flags and Config

Config priority:

1. Command flags
2. `ACPRCTL_*` environment variables
3. Config file

Global flags:

```text
-U, --server-url
-u, --username
-p, --password
-t, --token
-c, --config
-f, --format json|table
-y, --yes
-v, --verbose
-T, --timeout
-W, --wait
-I, --wait-interval
    --wait-timeout
-h, --help
```

Environment variables:

```bash
ACPRCTL_SERVER_URL=http://localhost:3001
ACPRCTL_USERNAME=admin
ACPRCTL_PASSWORD=admin123456
ACPRCTL_TOKEN=...
ACPRCTL_CONFIG=~/.config/acprctl/config.yaml
ACPRCTL_FORMAT=json
ACPRCTL_TIMEOUT=30s
ACPRCTL_WAIT_INTERVAL=3s
ACPRCTL_WAIT_TIMEOUT=120s
```

Write a config:

```bash
acprctl configure \
  --server-url http://localhost:3001 \
  --username admin \
  --password admin123456 \
  --format json
```

## Auth

Print a token:

```bash
acprctl auth login
```

If a token is absent, authenticated commands log in with username/password. On 401, the CLI retries login once when credentials are available.

## Plugin Commands

List plugins:

```bash
acprctl plugin list \
  [--status pending|active|disabled|deleted] \
  [--q keywords] \
  [--page 1] \
  [--page-size 20]
```

Show a plugin by key or UUID:

```bash
acprctl plugin show astrbot-plugin-example
acprctl plugin show --id 11111111-1111-1111-1111-111111111111
```

Submit a Git repository:

```bash
acprctl plugin submit \
  --repo-url https://github.com/org/repo \
  [--version v1.0] \
  [--ref main] \
  [--plugin-key astrbot-plugin-example] \
  [--wait] \
  [--wait-timeout 120s]
```

Pass `--plugin-key` when using `plugin submit --wait`; the backend submit response may not include the new plugin UUID.

Upload a new plugin zip:

```bash
acprctl plugin upload --file ./plugin.zip [--wait]
```

Update plugin metadata:

```bash
acprctl plugin update astrbot-plugin-example \
  [--display-name "..."] \
  [--description "..."] \
  [--category "..."] \
  [--tags tag1,tag2] \
  [--support-platforms windows,linux] \
  [--astrbot-version "3.0+"]
```

Delete a plugin:

```bash
acprctl plugin delete astrbot-plugin-example --yes
```

Set plugin status and optional review status:

```bash
acprctl plugin set-status astrbot-plugin-example \
  --status active|disabled|deleted|pending \
  [--review-status pending|approved|skipped|rejected]
```

Trigger a build:

```bash
acprctl plugin build astrbot-plugin-example \
  --version v1.0 \
  [--ref main] \
  [--wait]
```

Trigger all security scans for a version:

```bash
acprctl plugin scan astrbot-plugin-example --version v1.0 [--wait]
```

## Version Commands

List versions:

```bash
acprctl plugin version list astrbot-plugin-example
```

Upload a version zip:

```bash
acprctl plugin version upload astrbot-plugin-example \
  --file ./v1.0.zip \
  --version v1.0 \
  [--changelog "..."] \
  [--wait]
```

Set latest:

```bash
acprctl plugin version set-latest astrbot-plugin-example --version v1.0
```

Set version status:

```bash
acprctl plugin version set-status astrbot-plugin-example \
  --version v1.0 \
  --status active|deprecated|deleted|draft
```

Run or skip provider scans:

```bash
acprctl plugin version scan run astrbot-plugin-example \
  --version v1.0 \
  --provider virustotal|llm_agent|all \
  [--wait]

acprctl plugin version scan skip astrbot-plugin-example \
  --version v1.0 \
  --provider virustotal|llm_agent|all
```

## Review Commands

List pending reviews:

```bash
acprctl review list [--page 1] [--page-size 20]
```

Approve plugin only:

```bash
acprctl review approve astrbot-plugin-example
```

Approve and publish a version:

```bash
acprctl review publish astrbot-plugin-example [--version v1.0]
```

Skip review and publish a version:

```bash
acprctl review skip astrbot-plugin-example [--version v1.0]
```

Disable or delete:

```bash
acprctl review disable astrbot-plugin-example
acprctl review delete astrbot-plugin-example --yes
```

Publishing does not bypass backend constraints. The target version must have successful build and passing scans before it can become active/latest.

## Runtime Config, Cache, and Stats

Read config:

```bash
acprctl config list
```

Set one or more runtime config values:

```bash
acprctl config set --key S3_PUBLIC_URL --value http://localhost:3001/s3/astrbot-plugins
acprctl config set --key S3_PUBLIC_URL --value http://... --key PUBLIC_CACHE_MAX_AGE --value 60
```

Clear a runtime override by setting an empty value:

```bash
acprctl config set --key PUBLIC_CACHE_MAX_AGE --value ''
```

Refresh cache and view stats:

```bash
acprctl cache refresh
acprctl stats
```

## Error Handling

Errors are JSON on stderr. Branch on exit code:

```text
0 success
1 general error
2 auth failure
3 destructive action missing --yes
4 not found
5 wait timeout
6 validation or bad input
```

Example:

```json
{
  "error": "Plugin not found",
  "status": 404,
  "code": 4
}
```
