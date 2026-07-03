"""Database migration helpers."""

import logging

from alembic import command
from alembic.config import Config

from ..config import ROOT_DIR, settings

logger = logging.getLogger(__name__)


def run_database_migrations() -> None:
    """Run Alembic migrations up to the latest revision."""
    if not settings.database_auto_migrate:
        return

    registry_dir = ROOT_DIR / "registry"
    alembic_config = Config(str(registry_dir / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(registry_dir / "alembic"))
    alembic_config.set_main_option("sqlalchemy.url", settings.database_url)

    logger.info("Running database migrations")
    command.upgrade(alembic_config, "head")
