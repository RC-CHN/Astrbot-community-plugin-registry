"""VirusTotal and LLM security scanning."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..config import settings
from ..models import PluginVersion, SecurityScan


async def scan_version(db: AsyncSession, version_id: uuid.UUID) -> SecurityScan:
    """Run security scans on a plugin version.

    This is a placeholder implementation. When ``VIRUSTOTAL_API_KEY`` or an LLM
    agent is configured, the real scan results should be stored here.
    """
    version = await db.get(PluginVersion, version_id)
    if version is None:
        raise ValueError("Version not found")

    result = await db.execute(
        select(SecurityScan).where(SecurityScan.version_id == version.id)
    )
    scan = result.scalar_one_or_none()
    if scan is None:
        scan = SecurityScan(version_id=version.id)
        db.add(scan)

    scan.virustotal_pass = settings.scan_pass_when_unconfigured
    scan.virustotal_msg = settings.scan_unconfigured_message
    scan.llm_agent_pass = settings.scan_pass_when_unconfigured
    scan.llm_agent_msg = settings.scan_unconfigured_message
    await db.commit()
    await db.refresh(scan)
    from ..services.registry_service import refresh_cache

    await refresh_cache(db)
    return scan
