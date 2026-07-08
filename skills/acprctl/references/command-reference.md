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

Register a normal user through the public registration API:

```bash
acprctl auth register \
  --username alice \
  --email alice@example.com \
  --password '<password>' \
  [--password-env ACPRCTL_REGISTER_PASSWORD] \
  [--invite-code '<invite-code>'] \
  [--invite-code-env ACPRCTL_INVITE_CODE] \
  [--pow-timeout 30s] \
  [--pow-workers 4] \
  [--pow-max-difficulty 26] \
  [--login] \
  [--save]
```

`auth register` fetches `/auth/register/challenge`, computes the SHA-256 leading-zero-bits PoW locally, and submits `/auth/register`. `--login --save` logs in and stores the token only when the returned user status is `active`; `pending_approval` users must wait for an administrator.

## Command Tree

```text
acprctl
├── configure
├── auth login
├── auth register
├── config list
├── config set
├── config providers list
├── config providers enable
├── config providers disable
├── cache refresh
├── stats
├── task list
├── task show
├── task retry
├── worker status
├── plugin list
├── plugin show
├── plugin inspect-repo
├── plugin resolve-ref
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
├── plugin version delete
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

Inspect a GitHub repository before submitting it:

```bash
acprctl plugin inspect-repo \
  --repo-url https://github.com/org/repo \
  [--ref-type default|branch|tag|commit] \
  [--ref main] \
  [--include-refs true|false] \
  [--github-token '<github-token>'] \
  [--credential-id <stored-credential-id>]
```

Resolve one selected ref without loading branch and tag lists:

```bash
acprctl plugin resolve-ref \
  --repo-url https://github.com/org/repo \
  [--ref-type default|branch|tag|commit] \
  [--ref main] \
  [--github-token '<github-token>'] \
  [--credential-id <stored-credential-id>]
```

Use `inspect-repo` for first-time submission planning. Use `resolve-ref` when the agent only needs the selected commit, metadata preview, and duplicate-match result. `--github-token` is a per-request GitHub access token and is different from global `--token`, which is the registry admin bearer token.

Submit a Git repository:

```bash
acprctl plugin submit \
  --repo-url https://github.com/org/repo \
  [--version v1.0.0] \
  [--ref main] \
  [--changelog "..."] \
  [--github-token '<github-token>'] \
  [--credential-id <stored-credential-id>] \
  [--plugin-key astrbot-plugin-example] \
  [--wait] \
  [--wait-timeout 300s]
```

For Git submissions, omitting `--version` keeps the version from the selected commit's `metadata.yaml`. Providing `--version` overrides the registry version label and rewrites the built artifact's `metadata.yaml` `version` field to the same value. The commit SHA is the artifact identity: the same plugin commit is not built twice, while different commits may share the same metadata version. `--changelog` stores release notes on the registry version record; it does not modify source files.

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

This deletes the plugin record, all version records, and all version artifacts.

Set status:

```bash
acprctl plugin set-status <plugin-key|id> \
  --status active|disabled|deleted|pending \
  [--review-status pending|approved|skipped|rejected]
```

Build:

```bash
acprctl plugin build <plugin-key|id> \
  [--version v1.0.0] \
  [--ref main] \
  [--changelog "..."] \
  [--github-token '<github-token>'] \
  [--credential-id <stored-credential-id>] \
  [--wait]
```

For Git builds, omitting `--version` keeps the version from the selected commit's `metadata.yaml`. Providing `--version` rewrites the packaged `metadata.yaml` version. The selected commit SHA identifies the artifact, so retrying the same plugin commit is a duplicate even when the metadata version is not unique. Use `--changelog` to attach notes to that version record.

For commands that operate on an existing version, `--version` accepts either the metadata version string or the version record id. If multiple records share the same metadata version, use the id from `plugin version list --format json` so the command targets the intended commit.

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

Set the registry current version:

```bash
acprctl plugin version set-latest <plugin-key|id> --version v1.0.0
```

Set status:

```bash
acprctl plugin version set-status <plugin-key|id> \
  --version v1.0.0 \
  --status active|draft|deprecated|deleted
```

Delete one version and its artifact:

```bash
acprctl plugin version delete <plugin-key|id> --version v1.0.0 --yes
```

Run or skip provider scans:

```bash
acprctl plugin version scan run <plugin-key|id> \
  --version v1.0.0 \
  --provider clamav|virustotal|llm_agent|all \
  [--wait]

acprctl plugin version scan skip <plugin-key|id> \
  --version v1.0.0 \
  --provider clamav|virustotal|llm_agent|all
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
`review publish` and `review skip` publish atomically on the backend. They enable the plugin, mark the selected version as a release candidate, set it as the registry current version, and refresh cache only after build succeeds and recorded scan results are non-blocking. `review publish` records human review as approved. `review skip` records human review as skipped; it does not bypass pending, errored, or real failed scan results.

## Runtime Config, Cache, and Stats

```bash
acprctl stats
acprctl cache refresh
acprctl config list
acprctl config set --key PUBLIC_CACHE_MAX_AGE --value 60
acprctl config set --key GITHUB_TOKEN --value '<github-token>'
acprctl config set --key A --value one --key B --value two
acprctl config providers list
acprctl config providers enable clamav
acprctl config providers disable llm_agent
```

Clear an override:

```bash
acprctl config set --key PUBLIC_CACHE_MAX_AGE --value ''
```

Sensitive config values are redacted in `config list`; use `sensitive_status` to see whether they are configured. `GITHUB_TOKEN` is a sensitive runtime key used as the global fallback for GitHub repository inspection, ref lookup, size preflight, and clone when no per-request token is supplied.

`config providers` manages `SCAN_ENABLED_PROVIDERS` without requiring the caller to rewrite the full comma-separated value. Supported providers are `virustotal`, `llm_agent`, and `clamav`.

## Task and Worker Observability

Inspect queue and worker state:

```bash
acprctl worker status
```

List persisted worker tasks:

```bash
acprctl task list \
  [--status queued|delayed|running|retrying|succeeded|failed|dead|cancelled] \
  [--type submit|build|scan|virustotal_poll] \
  [--plugin-id <uuid>] \
  [--version-id <uuid>] \
  [--page 1] \
  [--page-size 20]
```

Show one task:

```bash
acprctl task show <task-id>
```

Retry a failed, cancelled, or dead task:

```bash
acprctl task retry <task-id>
```

Task records are an operational view of queued work. `task retry` creates a new queued task from the original task payload and leaves the old task as history.

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
