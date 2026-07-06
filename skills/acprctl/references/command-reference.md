# acprctl Command Reference

Use this reference for exact syntax. For task procedures, read `operations-workflows.md`.

## Availability

Check that `acprctl` is installed and callable:

```bash
acprctl --help
```

`acprctl` talks to the registry over HTTP(S).

## Global Flags

```text
-U, --server-url <url>       Service origin; origin, /api, and /api/v1 all work.
-u, --username <name>        Admin username.
-p, --password <password>    Admin password.
-t, --token <token>          Existing bearer token.
-c, --config <path>          Config file path.
-f, --format json|table      Output format; default json.
-y, --yes                    Confirm destructive commands.
-v, --verbose                Log HTTP method and URL to stderr.
-T, --timeout <duration>     HTTP request timeout.
-W, --wait                   Wait for async submit/build/scan completion.
-I, --wait-interval <dur>    Poll interval; default 3s.
    --wait-timeout <dur>     Poll timeout; default 120s.
-h, --help                   Print help.
```

Durations accept Go-style values such as `500ms`, `3s`, `2m`, `1h`, or bare seconds.

## Config Resolution

Priority:

1. Command flags
2. `ACPRCTL_*` environment variables
3. Config file

Environment variables:

```bash
ACPRCTL_SERVER_URL=https://registry.example.com
ACPRCTL_USERNAME=admin
ACPRCTL_PASSWORD='...'
ACPRCTL_TOKEN='...'
ACPRCTL_CONFIG=~/.config/acprctl/config.yaml
ACPRCTL_FORMAT=json
ACPRCTL_TIMEOUT=30s
ACPRCTL_WAIT_INTERVAL=3s
ACPRCTL_WAIT_TIMEOUT=120s
```

Default config path is `~/.config/acprctl/config.yaml`, or `$XDG_CONFIG_HOME/acprctl/config.yaml` when `XDG_CONFIG_HOME` is set.

Write config:

```bash
acprctl configure \
  --server-url https://registry.example.com \
  --username admin \
  --password '<admin-password>' \
  --format json
```

`configure` validates username/password by logging in, stores the token when login succeeds, and writes the config file with mode `0600`.

## Auth

```bash
acprctl auth login
```

Authenticated commands auto-login when no token is available. On `401`, the CLI retries login once when credentials exist.

## Command Tree

```text
acprctl
├── configure
├── auth login
├── config list
├── config set
├── cache refresh
├── stats
├── plugin list
├── plugin show
├── plugin submit
├── plugin upload
├── plugin update
├── plugin delete
├── plugin set-status
├── plugin build
├── plugin scan
├── plugin version list
├── plugin version upload
├── plugin version set-latest
├── plugin version set-status
├── plugin version scan run
├── plugin version scan skip
├── review list
├── review approve
├── review publish
├── review skip
├── review disable
└── review delete
```

## Plugin Commands

List:

```bash
acprctl plugin list \
  [--status pending|active|disabled|deleted] \
  [--q keywords] \
  [--page 1] \
  [--page-size 20]
```

Show by plugin key or UUID:

```bash
acprctl plugin show astrbot-plugin-example
acprctl plugin show --id 11111111-1111-1111-1111-111111111111
```

Submit a Git repository:

```bash
acprctl plugin submit \
  --repo-url https://github.com/org/repo \
  [--version v1.0.0] \
  [--ref main] \
  [--changelog "..."] \
  [--plugin-key astrbot-plugin-example] \
  [--wait] \
  [--wait-timeout 300s]
```

Upload a plugin zip:

```bash
acprctl plugin upload --file ./plugin.zip [--wait]
```

Update metadata:

```bash
acprctl plugin update <plugin-key|id> \
  [--display-name "..."] \
  [--description "..."] \
  [--category "..."] \
  [--tags tag1,tag2] \
  [--support-platforms linux,windows] \
  [--astrbot-version "3.0+"]
```

Delete:

```bash
acprctl plugin delete <plugin-key|id> --yes
```

Set status:

```bash
acprctl plugin set-status <plugin-key|id> \
  --status active|disabled|deleted|pending \
  [--review-status pending|approved|skipped|rejected]
```

Build:

```bash
acprctl plugin build <plugin-key|id> \
  --version v1.0.0 \
  [--ref main] \
  [--changelog "..."] \
  [--wait]
```

Scan:

```bash
acprctl plugin scan <plugin-key|id> --version v1.0.0 [--wait]
```

## Version Commands

List:

```bash
acprctl plugin version list <plugin-key|id>
```

Upload:

```bash
acprctl plugin version upload <plugin-key|id> \
  --file ./v1.0.0.zip \
  --version v1.0.0 \
  [--changelog "..."] \
  [--wait]
```

Set latest:

```bash
acprctl plugin version set-latest <plugin-key|id> --version v1.0.0
```

Set status:

```bash
acprctl plugin version set-status <plugin-key|id> \
  --version v1.0.0 \
  --status active|draft|deprecated|deleted
```

Run or skip provider scans:

```bash
acprctl plugin version scan run <plugin-key|id> \
  --version v1.0.0 \
  --provider virustotal|llm_agent|all \
  [--wait]

acprctl plugin version scan skip <plugin-key|id> \
  --version v1.0.0 \
  --provider virustotal|llm_agent|all
```

## Review Commands

```bash
acprctl review list [--page 1] [--page-size 20]
acprctl review approve <plugin-key|id>
acprctl review publish <plugin-key|id> [--version v1.0.0]
acprctl review skip <plugin-key|id> [--version v1.0.0]
acprctl review disable <plugin-key|id>
acprctl review delete <plugin-key|id> --yes
```

`review list` is a filtered `plugin list` for pending plugins.

## Runtime Config, Cache, and Stats

```bash
acprctl stats
acprctl cache refresh
acprctl config list
acprctl config set --key PUBLIC_CACHE_MAX_AGE --value 60
acprctl config set --key A --value one --key B --value two
```

Clear an override:

```bash
acprctl config set --key PUBLIC_CACHE_MAX_AGE --value ''
```

Sensitive config values are redacted in `config list`; use `sensitive_status` to see whether they are configured.

## Output and Exit Codes

Successful output is JSON by default. Errors are JSON on stderr:

```json
{
  "error": "Plugin not found",
  "status": 404,
  "code": 4
}
```

Exit codes:

```text
0 success
1 general error
2 auth failure
3 destructive action missing --yes
4 not found
5 wait timeout
6 validation or bad input
```

Use both exit code and JSON `detail` in automation.
