# acprctl Implementation Coverage

Use this reference to answer whether the Go CLI implements `docs/acprctl-cli-interaction-design.md`.

## Summary

The Go implementation in `acprctl/main.go` implements the concrete administrator features described in sections 1-10 of the interaction design:

- standalone Go binary, not a Python package command
- config/env/flag resolution
- login and token use
- structured JSON output and error codes
- plugin key / UUID resolution
- async wait support for submit/build/scan workflows
- multipart upload
- all plugin, version, review, config, cache, and stats commands listed in the command tree

The design's section 12 items remain intentionally unresolved, not implemented requirements:

- rollback on partial `review publish` failure
- batch operations such as deleting multiple plugin keys in one command
- hand-curated table columns beyond the generic table renderer

## Coverage Matrix

| Design area | Status | Notes |
|---|---:|---|
| Standalone Go CLI | Implemented | Source lives in `acprctl/`; build with `go build -o acprctl .`. |
| No Python package command | Implemented | Do not add `acprctl` to `registry/pyproject.toml`. |
| API base normalization | Implemented | `--server-url` accepts origin, `/api`, or `/api/v1`. |
| Flag/env/config priority | Implemented | Flags override `ACPRCTL_*`, which override config file. |
| Default config path | Implemented | `~/.config/acprctl/config.yaml`, or `XDG_CONFIG_HOME/acprctl/config.yaml`. |
| `configure` | Implemented | Writes config with 0600 permissions and validates username/password by login. |
| Token auth | Implemented | Existing token is used directly. |
| Username/password login | Implemented | Auto-login when token is absent. |
| 401 retry | Implemented | Retries login once when credentials are available. |
| `auth login` | Implemented | Prints token response. |
| JSON output | Implemented | Default output is indented JSON. |
| table output | Implemented | Generic table renderer for maps/lists; not a per-command custom table. |
| no ANSI color | Implemented | CLI emits plain text only. |
| structured errors | Implemented | JSON on stderr with `error`, `code`, optional `status` and `detail`. |
| exit codes 0-6 | Implemented | Matches the design table. |
| `--verbose` | Implemented | Logs HTTP method and URL to stderr. |
| `--help` | Implemented | Prints top-level help without requiring server config. |
| plugin-key resolution | Implemented | Non-UUID refs query `/admin/plugins?q=...` and require exact key match. |
| explicit `--id` | Implemented | Works anywhere a plugin ref is accepted. |
| async wait | Implemented | Polls plugin detail and version `build_status`; timeout exits 5. |
| `plugin submit --wait` | Implemented | Uses response `plugin_id`, explicit `--plugin-key`, then repo-name inference. |
| multipart upload | Implemented | `plugin upload` and `plugin version upload`. |
| version name to UUID | Implemented | Version commands list versions and resolve by `id` or `version`. |
| `config list` | Implemented | Returns full runtime config response. |
| `config set` | Implemented | Supports repeated `--key/--value` pairs. |
| cache refresh | Implemented | Calls admin cache refresh endpoint. |
| stats | Implemented | Calls admin stats endpoint. |

## Command Coverage

Implemented command tree:

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

## Known Boundaries

- Config parsing is intentionally simple and supports the flat key-value config that `configure` writes. It is not a general YAML parser.
- Some enum validation is delegated to the backend, so invalid statuses/providers may return backend validation errors rather than local parser errors.
- Wait success is based on version `build_status == "success"` because the backend sets that state after scan workflows complete.
- `review publish` is not transactional. If a later backend call fails, the CLI reports the failure and does not roll back prior successful calls.
- Public plugin search and user management are explicitly outside the administrator CLI scope.

## Validation Checklist

After CLI edits:

```bash
cd acprctl
gofmt -w main.go main_test.go
go test ./...
go build -o /tmp/acprctl-test .
```

After backend API edits:

```bash
uv run pytest -q
uv run ruff check registry/src registry/tests
```

Dev-stack smoke test:

```bash
/tmp/acprctl-test --server-url http://localhost:3001 --username admin --password admin123456 stats
/tmp/acprctl-test --server-url http://localhost:3001 --username admin --password admin123456 plugin list --page-size 5
/tmp/acprctl-test --server-url http://localhost:3001 --username admin --password admin123456 plugin show --id 11111111-1111-1111-1111-111111111111
```

The final command should return structured 404 with exit code 4 when the UUID does not exist.
