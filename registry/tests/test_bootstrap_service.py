import pytest

from astrbot_registry.models import User
from astrbot_registry.services import bootstrap_service


class FakeSession:
    def __init__(self, count: int = 0) -> None:
        self.count = count
        self.added: list[User] = []
        self.committed = False

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def scalar(self, statement) -> int:
        return self.count

    def add(self, user: User) -> None:
        self.added.append(user)

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_bootstrap_admin_user_skips_without_credentials(monkeypatch) -> None:
    session = FakeSession()
    monkeypatch.setattr(bootstrap_service.settings, "bootstrap_admin_username", "")
    monkeypatch.setattr(bootstrap_service.settings, "bootstrap_admin_password", "")
    monkeypatch.setattr(bootstrap_service.settings, "bootstrap_admin_role", "admin")
    monkeypatch.setattr(bootstrap_service, "async_session", lambda: session)

    await bootstrap_service.bootstrap_admin_user()

    assert session.added == []
    assert session.committed is False


@pytest.mark.asyncio
async def test_bootstrap_admin_user_creates_first_user(monkeypatch) -> None:
    session = FakeSession(count=0)
    monkeypatch.setattr(bootstrap_service.settings, "bootstrap_admin_username", "admin")
    monkeypatch.setattr(bootstrap_service.settings, "bootstrap_admin_password", "secret")
    monkeypatch.setattr(bootstrap_service.settings, "bootstrap_admin_role", "admin")
    monkeypatch.setattr(bootstrap_service, "async_session", lambda: session)
    monkeypatch.setattr(bootstrap_service, "get_password_hash", lambda password: f"hashed:{password}")

    await bootstrap_service.bootstrap_admin_user()

    assert len(session.added) == 1
    assert session.added[0].username == "admin"
    assert session.added[0].password_hash == "hashed:secret"
    assert session.added[0].role == "admin"
    assert session.committed is True


@pytest.mark.asyncio
async def test_bootstrap_admin_user_skips_when_users_exist(monkeypatch) -> None:
    session = FakeSession(count=1)
    monkeypatch.setattr(bootstrap_service.settings, "bootstrap_admin_username", "admin")
    monkeypatch.setattr(bootstrap_service.settings, "bootstrap_admin_password", "secret")
    monkeypatch.setattr(bootstrap_service.settings, "bootstrap_admin_role", "admin")
    monkeypatch.setattr(bootstrap_service, "async_session", lambda: session)

    await bootstrap_service.bootstrap_admin_user()

    assert session.added == []
    assert session.committed is False
