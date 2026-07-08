"""Base scan provider contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ...models import PluginVersion, SecurityScan


@dataclass(frozen=True)
class ScanOutcome:
    passed: bool | None
    message: str
    mode: str
    virustotal_analysis_id: str | None = None
    virustotal_file_sha256: str | None = None
    virustotal_submitted_at: datetime | None = None
    virustotal_deadline_at: datetime | None = None
    virustotal_next_poll_at: datetime | None = None
    virustotal_poll_attempts: int | None = None


class ScanProvider(ABC):
    """A pluggable machine scan provider.

    Providers own their runtime config, configured-state check, and concrete
    scan implementation. The orchestration layer only decides which providers
    are enabled, runs configured providers in parallel, and persists outcomes.
    """

    name: str
    label: str
    legacy_public: bool = False

    @abstractmethod
    async def load_config(self, db: AsyncSession) -> dict[str, Any]:
        """Load runtime config for this provider."""

    @abstractmethod
    def is_configured(self, config: dict[str, Any]) -> bool:
        """Return whether a real scan can run with the config."""

    @abstractmethod
    async def scan(
        self,
        version: PluginVersion,
        config: dict[str, Any],
        local_path: Path | None,
    ) -> ScanOutcome:
        """Run the provider scan and return a normalized outcome."""

    def apply_tracking(self, scan: SecurityScan, outcome: ScanOutcome) -> None:
        """Persist provider-specific tracking fields on legacy scan records."""

    def clear_tracking(self, scan: SecurityScan) -> None:
        """Clear provider-specific pending tracking fields on legacy scan records."""
