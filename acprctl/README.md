# acprctl

Standalone Go CLI for administering AstrBot Community Plugin Registry.

Build:

```bash
cd acprctl
go build -o acprctl .
```

Use against the dev stack:

```bash
./acprctl --server-url http://localhost:3001 --username admin --password admin123456 stats
```

Manage enabled scan providers without hand-editing the full CSV value:

```bash
./acprctl config providers list
./acprctl config providers enable clamav
./acprctl config providers disable llm_agent
```

The binary has no third-party Go dependencies. It reads config from
`~/.config/acprctl/config.yaml` by default and also supports `ACPRCTL_*`
environment variables.

Release archives include the companion Codex skill at `skills/acprctl/`.
