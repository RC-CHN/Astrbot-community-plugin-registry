# Operations Workflows

Use this reference for real registry administration through `acprctl`.

## Baseline Inspection

Start every session with:

```bash
acprctl stats
acprctl plugin list --page-size 20
acprctl review list
acprctl worker status
acprctl task list --page-size 20
acprctl config list
```

Use `--format json` when an agent needs to parse output:

```bash
acprctl --format json plugin show astrbot-plugin-example
```

## Submit a Public GitHub Plugin

Submit from a Git repository:

```bash
acprctl plugin submit \
  --repo-url https://github.com/org/astrbot_plugin_example \
  --version v1.0.0 \
  --ref main \
  --plugin-key astrbot-plugin-example \
  --wait \
  --wait-timeout 300s
```

Use `--plugin-key` with `--wait`; the backend submit response may only say queued, so the CLI needs a stable ref to poll.

After the wait succeeds:

```bash
acprctl plugin show astrbot-plugin-example
acprctl review list
```

## Upload a New Plugin Zip

Upload when the artifact already exists locally:

```bash
acprctl plugin upload --file ./plugin.zip --wait --wait-timeout 300s
```

The zip must include valid plugin metadata. The backend validates upload size, unzip size, zip entry count, and single-file limits.

## Build a New Version From an Existing Plugin Repo

Trigger a build for an already registered plugin:

```bash
acprctl plugin build astrbot-plugin-example \
  --version v1.1.0 \
  --ref main \
  --wait \
  --wait-timeout 300s
```

Then inspect:

```bash
acprctl plugin version list astrbot-plugin-example
acprctl plugin show astrbot-plugin-example
```

## Upload a Version Zip

```bash
acprctl plugin version upload astrbot-plugin-example \
  --file ./plugin-v1.1.0.zip \
  --version v1.1.0 \
  --changelog "Update dependencies" \
  --wait \
  --wait-timeout 300s
```

## Scan Operations

Inspect enabled providers:

```bash
acprctl config providers list
```

Enable or disable providers without rewriting the full provider list:

```bash
acprctl config providers enable virustotal
acprctl config providers enable llm_agent
acprctl config providers enable clamav
acprctl config providers disable clamav
```

Run all scans for one version:

```bash
acprctl plugin scan astrbot-plugin-example --version v1.1.0 --wait --wait-timeout 300s
```

Run one provider:

```bash
acprctl plugin version scan run astrbot-plugin-example \
  --version v1.1.0 \
  --provider clamav \
  --wait
```

Skip a provider after manual review:

```bash
acprctl plugin version scan skip astrbot-plugin-example \
  --version v1.1.0 \
  --provider virustotal
```

Provider names are `clamav`, `virustotal`, `llm_agent`, and `all`.

## Task and Worker Inspection

Use this when a submit, build, scan, webhook, or VirusTotal poll appears stuck.

Check worker and Redis queue state:

```bash
acprctl --format json worker status
```

Inspect recent tasks:

```bash
acprctl --format json task list --page-size 50
```

Filter by status or type:

```bash
acprctl --format json task list --status dead
acprctl --format json task list --type scan --status running
acprctl --format json task list --type virustotal_poll --status delayed
```

Show a specific task:

```bash
acprctl --format json task show <task-id>
```

Retry only after inspecting the previous error and confirming the root cause is fixed:

```bash
acprctl task retry <task-id>
```

Use task records to locate the operational blocker, then inspect the related plugin/version with `plugin show` when the task references a plugin or version id.

## Review and Publish

Mark human review approved without publishing a version:

```bash
acprctl review approve astrbot-plugin-example
```

Publish a specific version and record human review as approved:

```bash
acprctl review publish astrbot-plugin-example --version v1.1.0
```

Publish a specific version and record human review as skipped:

```bash
acprctl review skip astrbot-plugin-example --version v1.1.0
```

Disable a plugin:

```bash
acprctl review disable astrbot-plugin-example
```

Delete only with explicit user intent:

```bash
acprctl review delete astrbot-plugin-example --yes
```

Publishing is a backend-atomic operation. It enables the plugin, records the human review status, marks the selected version as a release candidate, sets it as the registry current version, and refreshes the registry cache only after build succeeds and recorded scan results are non-blocking. Blocking scan results are pending, errored, or real failed results; skipped providers do not block.

## Version Management

List versions:

```bash
acprctl plugin version list astrbot-plugin-example
```

Set the registry current version:

```bash
acprctl plugin version set-latest astrbot-plugin-example --version v1.1.0
```

Set version status:

```bash
acprctl plugin version set-status astrbot-plugin-example \
  --version v1.1.0 \
  --status active
```

Common statuses are delegated to the backend. Use `active`, `draft`, `deprecated`, or `deleted` according to the backend response.

## Metadata and Status Updates

Update metadata:

```bash
acprctl plugin update astrbot-plugin-example \
  --display-name "Example Plugin" \
  --description "Short admin-visible description" \
  --category "tool" \
  --tags utility,automation \
  --support-platforms linux,windows \
  --astrbot-version "3.0+"
```

Set plugin status:

```bash
acprctl plugin set-status astrbot-plugin-example \
  --status active \
  --review-status approved
```

Delete only with explicit user intent:

```bash
acprctl plugin delete astrbot-plugin-example --yes
```

## Runtime Config and Cache

Inspect config:

```bash
acprctl config list
```

Set one value:

```bash
acprctl config set --key PUBLIC_CACHE_MAX_AGE --value 60
```

Set multiple values atomically in one request:

```bash
acprctl config set \
  --key SCAN_PASS_WHEN_UNCONFIGURED --value true \
  --key WEBHOOK_AUTO_VERSION --value auto
```

Manage scan providers:

```bash
acprctl config providers list
acprctl config providers enable clamav
acprctl config providers disable llm_agent
```

Clear a runtime override with an empty value:

```bash
acprctl config set --key PUBLIC_CACHE_MAX_AGE --value ''
```

Refresh public registry cache after manual repairs:

```bash
acprctl cache refresh
```
