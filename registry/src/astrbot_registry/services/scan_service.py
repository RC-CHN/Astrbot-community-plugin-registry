"""VirusTotal and LLM security scanning."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import PluginVersion, SecurityScan


async def scan_version(db: AsyncSession, version_id: uuid.UUID) -> SecurityScan:
    """Run security scans on a plugin version.

    This is a placeholder implementation. When ``VIRUSTOTAL_API_KEY`` or an LLM
    agent is configured, the real scan results should be stored here.
    """
    version = await db.get(PluginVersion, version_id)
    if version is None:
        raise ValueError("Version not found")

    scan = SecurityScan(
        version_id=version.id,
        virustotal_pass=True,
        virustotal_msg="Scan not configured",
        llm_agent_pass=True,
        llm_agent_msg="Scan not configured",
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)
    return scan
