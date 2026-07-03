from astrbot_registry.services import migration_service


def test_run_database_migrations_skips_when_disabled(monkeypatch) -> None:
    calls = []

    monkeypatch.setattr(migration_service.settings, "database_auto_migrate", False)
    monkeypatch.setattr(migration_service.command, "upgrade", lambda *args: calls.append(args))

    migration_service.run_database_migrations()

    assert calls == []


def test_run_database_migrations_upgrades_to_head(monkeypatch) -> None:
    calls = []

    monkeypatch.setattr(migration_service.settings, "database_auto_migrate", True)
    monkeypatch.setattr(migration_service.command, "upgrade", lambda *args: calls.append(args))

    migration_service.run_database_migrations()

    assert len(calls) == 1
    config, revision = calls[0]
    assert revision == "head"
    assert config.get_main_option("script_location").endswith("registry/alembic")
