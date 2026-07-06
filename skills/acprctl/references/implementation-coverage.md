# acprctl Capability Coverage

Use this reference to answer what the released `acprctl` CLI can do.

## Summary

The CLI covers the administrator workflows needed to operate AstrBot Community Plugin Registry:

- service connection through `--server-url`
- config/env/flag resolution
- username/password login and bearer token use
- structured JSON output and structured stderr errors
- plugin key and UUID references
- async waits for submit/build/scan workflows
- multipart upload for plugin and version zip files
- plugin, version, review, config, cache, and stats administration

## Coverage Matrix

| Area | Status | Notes |
|---|---:|---|
| Standalone binary | Supported | Operate with the installed `acprctl` binary. |
| Service URL normalization | Supported | Origin, `/api`, and `/api/v1` inputs work. |
| Flag/env/config priority | Supported | Flags override `ACPRCTL_*`, which override config file values. |
| Default config path | Supported | `~/.config/acprctl/config.yaml`, or `XDG_CONFIG_HOME/acprctl/config.yaml`. |
| `configure` | Supported | Validates login and stores token when credentials are supplied. |
| Token auth | Supported | Existing token can be supplied with `--token` or `ACPRCTL_TOKEN`. |
| Username/password login | Supported | Used when no token is available. |
| 401 retry | Supported | Retries login once when credentials are available. |
| `auth login` | Supported | Prints token response. |
| JSON output | Supported | Default output is indented JSON. |
| Table output | Supported | Generic table renderer for maps/lists. |
| Structured errors | Supported | JSON on stderr with `error`, `code`, optional `status` and `detail`. |
| Exit codes 0-6 | Supported | Stable for automation. |
| `--verbose` | Supported | Logs HTTP method and URL to stderr. |
| `--help` | Supported | Prints top-level help without server config. |
| Plugin-key resolution | Supported | Non-UUID refs query admin plugin list and require exact key match. |
| Explicit `--id` | Supported | Works anywhere a plugin ref is accepted. |
| Async wait | Supported | Polls plugin detail and build/scan state; timeout exits 5. |
| `plugin submit --wait` | Supported | Most reliable with explicit `--plugin-key`. |
| Multipart upload | Supported | `plugin upload` and `plugin version upload`. |
| Version name to UUID | Supported | Version commands resolve version names or IDs. |
| `config list` | Supported | Returns deployment, effective, runtime override, and sensitive status fields. |
| `config set` | Supported | Supports repeated `--key/--value` pairs. |
| Cache refresh | Supported | Refreshes public registry cache. |
| Stats | Supported | Shows total and pending plugin counts. |

## Command Coverage

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

## Known Operational Boundaries

- Config parsing is intentionally simple and supports the flat key-value config that `configure` writes. It is not a general YAML parser.
- Some enum validation is delegated to the server, so invalid statuses/providers may return server validation errors.
- Wait success for build workflows is based on a version reaching `build_status=success`.
- Wait success for scan workflows requires selected scan providers to have completed passing or skipped results.
- `review publish` is not transactional. If a later server call fails, inspect the plugin and repair the specific version/status/latest state.
- Public plugin search and user management are outside the current administrator CLI scope.
