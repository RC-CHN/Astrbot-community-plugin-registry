from astrbot_registry.config import Settings


def test_settings_parse_env_overrides() -> None:
    settings = Settings(
        app_host="127.0.0.1",
        app_port=9000,
        public_cache_max_age=120,
        redis_task_queue_key="custom_queue",
        s3_plugins_prefix="custom-plugins",
        scan_pass_when_unconfigured=False,
        scan_unconfigured_message="disabled",
        webhook_auto_version="from-webhook",
    )

    assert settings.app_host == "127.0.0.1"
    assert settings.app_port == 9000
    assert settings.public_cache_max_age == 120
    assert settings.redis_task_queue_key == "custom_queue"
    assert settings.s3_plugins_prefix == "custom-plugins"
    assert settings.scan_pass_when_unconfigured is False
    assert settings.scan_unconfigured_message == "disabled"
    assert settings.webhook_auto_version == "from-webhook"


def test_settings_parse_allowed_git_hosts_csv() -> None:
    settings = Settings(git_allowed_hosts="github.com,git.example.com")

    assert settings.git_allowed_hosts == ["github.com", "git.example.com"]
