"""VirusTotal and LLM security scanning."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models import PluginVersion, SecurityScan
from .runtime_config import runtime_scan_defaults


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

    defaults = await runtime_scan_defaults(db)
    scan.virustotal_pass = defaults["pass_when_unconfigured"]
    scan.virustotal_msg = defaults["message"]
    scan.llm_agent_pass = defaults["pass_when_unconfigured"]
    scan.llm_agent_msg = defaults["message"]
    await db.commit()
    await db.refresh(scan)
    from ..services.registry_service import refresh_cache

    await refresh_cache(db)
    return scan
