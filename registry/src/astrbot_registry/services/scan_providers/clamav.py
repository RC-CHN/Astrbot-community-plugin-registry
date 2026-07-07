"""ClamAV scan provider."""

from __future__ import annotations

import asyncio
import struct
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ...models import PluginVersion
from ..runtime_config import runtime_clamav_config
from ..s3_service import download_file
from .base import ScanOutcome, ScanProvider


class ClamAVProvider(ScanProvider):
    name = "clamav"
    label = "ClamAV"

    async def load_config(self, db: AsyncSession) -> dict[str, Any]:
        return await runtime_clamav_config(db)

    def is_configured(self, config: dict[str, Any]) -> bool:
        return bool(config.get("host") and int(config.get("port") or 0) > 0)

    async def scan(
        self,
        version: PluginVersion,
        config: dict[str, Any],
        local_path: Path | None,
    ) -> ScanOutcome:
        return await scan_clamav_for_version(version, config, local_path)


async def scan_clamav_for_version(
    version: PluginVersion,
    config: dict[str, Any],
    local_path: Path | None,
) -> ScanOutcome:
    if local_path is not None:
        return await scan_clamav(local_path, config)

    if not version.s3_key:
        return ScanOutcome(False, "ClamAV scan failed: version artifact is missing", "error")

    with tempfile.TemporaryDirectory() as tmp:
        artifact_path = Path(tmp) / f"{version.id}.zip"
        try:
            await download_file(version.s3_key, artifact_path)
        except Exception as exc:
            return ScanOutcome(False, f"ClamAV scan failed: could not download artifact: {exc}", "error")
        return await scan_clamav(artifact_path, config)


async def scan_clamav(local_path: Path, config: dict[str, Any]) -> ScanOutcome:
    file_size = local_path.stat().st_size
    max_stream_bytes = max(1, int(config["max_stream_bytes"]))
    if file_size > max_stream_bytes:
        return ScanOutcome(
            False,
            f"ClamAV scan failed: file exceeds stream limit ({file_size} > {max_stream_bytes} bytes)",
            "error",
        )

    timeout = max(1, int(config["timeout_seconds"]))
    chunk_size = max(1, int(config["stream_chunk_bytes"]))
    host = str(config["host"])
    port = int(config["port"])

    try:
        reply = await asyncio.wait_for(
            clamav_instream(host, port, local_path, chunk_size),
            timeout=timeout,
        )
    except TimeoutError:
        return ScanOutcome(False, f"ClamAV scan failed: timed out after {timeout} seconds", "error")
    except OSError as exc:
        return ScanOutcome(False, f"ClamAV scan failed: {exc}", "error")

    return format_clamav_reply(reply, file_size=file_size)


async def clamav_instream(host: str, port: int, local_path: Path, chunk_size: int) -> str:
    reader, writer = await asyncio.open_connection(host, port)
    try:
        writer.write(b"zINSTREAM\0")
        with open(local_path, "rb") as artifact:
            while chunk := artifact.read(chunk_size):
                writer.write(struct.pack(">I", len(chunk)))
                writer.write(chunk)
                await writer.drain()
        writer.write(struct.pack(">I", 0))
        await writer.drain()
        data = await reader.read(4096)
    finally:
        writer.close()
        await writer.wait_closed()
    return data.decode("utf-8", errors="replace").replace("\x00", "").strip()


def format_clamav_reply(reply: str, *, file_size: int | None = None) -> ScanOutcome:
    normalized = reply.strip()
    if not normalized:
        return ScanOutcome(False, "ClamAV scan failed: empty response", "error")
    details = _clamav_message_details(normalized, file_size)
    if normalized.endswith(" OK"):
        return ScanOutcome(True, f"ClamAV passed: no signature match ({details})", "real")
    if " FOUND" in normalized:
        signature = _clamav_found_signature(normalized)
        return ScanOutcome(False, f"ClamAV detected malware signature: {signature} ({details})", "real")
    if " ERROR" in normalized or normalized.startswith("ERROR"):
        return ScanOutcome(False, f"ClamAV scan failed: {details}", "error")
    return ScanOutcome(False, f"ClamAV scan failed: unexpected response ({details})", "error")


def _clamav_message_details(reply: str, file_size: int | None) -> str:
    details = ["protocol=INSTREAM"]
    if file_size is not None:
        details.append(f"artifact_size={_human_bytes(file_size)}")
    details.append(f'clamd_reply="{reply}"')
    return "; ".join(details)


def _clamav_found_signature(reply: str) -> str:
    signature = reply.removesuffix(" FOUND")
    if ": " in signature:
        signature = signature.rsplit(": ", 1)[1]
    return signature or "unknown"


def _human_bytes(value: int) -> str:
    size = float(value)
    for unit in ("bytes", "KiB", "MiB", "GiB"):
        if size < 1024 or unit == "GiB":
            if unit == "bytes":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
