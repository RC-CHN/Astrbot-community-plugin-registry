import uuid
from datetime import UTC, datetime

from astrbot_registry.models import WorkerTask
from astrbot_registry.services.task_observability import payload_summary, stored_payload, task_to_dict


def test_payload_summary_hides_internal_user_id() -> None:
    summary = payload_summary(
        {
            "plugin_id": "p1",
            "version_id": "v1",
            "version": "1.0.0",
            "user_id": "secret-user",
        }
    )

    assert summary == {"plugin_id": "p1", "version_id": "v1", "version": "1.0.0"}


def test_stored_payload_redacts_temporary_token() -> None:
    payload = stored_payload(
        {
            "repo_url": "https://github.com/example/repo",
            "temporary_token": "ghp_secret",
            "credential_id": "cred-1",
        }
    )

    assert payload == {
        "repo_url": "https://github.com/example/repo",
        "credential_id": "cred-1",
        "temporary_token_present": True,
    }


def test_task_to_dict_uses_payload_summary() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    task = WorkerTask(
        id=uuid.UUID("00000000-0000-0000-0000-000000000123"),
        task_type="build",
        status="queued",
        payload={"plugin_id": "p1", "version": "1.0.0", "user_id": "secret-user"},
        attempts=0,
        max_attempts=3,
        queued_at=now,
        created_at=now,
        updated_at=now,
    )

    data = task_to_dict(task)

    assert data["id"] == "00000000-0000-0000-0000-000000000123"
    assert data["payload_summary"] == {"plugin_id": "p1", "version": "1.0.0"}
