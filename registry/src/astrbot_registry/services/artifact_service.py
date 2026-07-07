"""Read-only artifact package inspection helpers."""

from __future__ import annotations

import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from tempfile import TemporaryDirectory
from typing import Any

from ..models import PluginVersion
from .s3_service import download_file

MAX_PREVIEW_BYTES = 512 * 1024

BINARY_EXTENSIONS = {
    ".7z",
    ".bin",
    ".bmp",
    ".db",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".pyc",
    ".rar",
    ".so",
    ".sqlite",
    ".webp",
    ".zip",
}

LANGUAGE_BY_EXTENSION = {
    ".css": "css",
    ".env": "dotenv",
    ".html": "html",
    ".js": "javascript",
    ".json": "json",
    ".md": "markdown",
    ".py": "python",
    ".sh": "shell",
    ".toml": "toml",
    ".ts": "typescript",
    ".txt": "plaintext",
    ".vue": "vue",
    ".yaml": "yaml",
    ".yml": "yaml",
}


class ArtifactError(RuntimeError):
    """Raised when an artifact cannot be inspected."""


async def list_artifact_tree(version: PluginVersion) -> dict[str, Any]:
    with TemporaryDirectory(prefix="astrbot-artifact-") as tmp:
        zip_path = await _download_artifact(version, Path(tmp))
        return _read_artifact_tree(zip_path)


async def read_artifact_file(version: PluginVersion, file_path: str) -> dict[str, Any]:
    with TemporaryDirectory(prefix="astrbot-artifact-") as tmp:
        zip_path = await _download_artifact(version, Path(tmp))
        return _read_artifact_file(zip_path, file_path)


async def _download_artifact(version: PluginVersion, workdir: Path) -> Path:
    if not version.s3_key:
        raise ArtifactError("Version artifact is missing")
    zip_path = workdir / f"{version.id}.zip"
    try:
        await download_file(version.s3_key, zip_path)
    except Exception as exc:
        raise ArtifactError(f"Could not download artifact: {exc}") from exc
    return zip_path


def _read_artifact_tree(zip_path: Path) -> dict[str, Any]:
    entries: dict[str, dict[str, Any]] = {}
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                path = _normalize_member_path(info.filename)
                if not path:
                    continue
                _add_parent_dirs(entries, path)
                if info.is_dir():
                    entries.setdefault(
                        path,
                        {"path": path, "name": PurePosixPath(path).name, "kind": "dir", "size": None},
                    )
                    continue
                entries[path] = {
                    "path": path,
                    "name": PurePosixPath(path).name,
                    "kind": "file",
                    "size": info.file_size,
                }
    except zipfile.BadZipFile as exc:
        raise ArtifactError("Artifact is not a valid zip archive") from exc
    return {
        "entries": sorted(
            entries.values(),
            key=lambda item: (item["path"].count("/"), item["kind"] == "file", item["path"].lower()),
        )
    }


def _read_artifact_file(zip_path: Path, file_path: str) -> dict[str, Any]:
    requested_path = _normalize_requested_path(file_path)
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            info = _find_member(zf, requested_path)
            if info is None or info.is_dir():
                raise ArtifactError("Artifact file not found")

            language = _language_for_path(requested_path)
            binary = PurePosixPath(requested_path).suffix.lower() in BINARY_EXTENSIONS
            if binary:
                return _file_payload(requested_path, info.file_size, language, binary=True)

            with zf.open(info, "r") as file:
                raw = file.read(MAX_PREVIEW_BYTES + 1)
            truncated = len(raw) > MAX_PREVIEW_BYTES or info.file_size > MAX_PREVIEW_BYTES
            raw = raw[:MAX_PREVIEW_BYTES]
            if b"\x00" in raw:
                return _file_payload(requested_path, info.file_size, language, binary=True)

            content = raw.decode("utf-8", errors="replace")
            return _file_payload(
                requested_path,
                info.file_size,
                language,
                content=content,
                truncated=truncated,
            )
    except zipfile.BadZipFile as exc:
        raise ArtifactError("Artifact is not a valid zip archive") from exc


def _file_payload(
    path: str,
    size: int,
    language: str,
    *,
    content: str | None = None,
    truncated: bool = False,
    binary: bool = False,
) -> dict[str, Any]:
    return {
        "path": path,
        "name": PurePosixPath(path).name,
        "size": size,
        "language": language,
        "content": content,
        "truncated": truncated,
        "binary": binary,
    }


def _add_parent_dirs(entries: dict[str, dict[str, Any]], path: str) -> None:
    parts = PurePosixPath(path).parts
    for index in range(1, len(parts)):
        parent = "/".join(parts[:index])
        entries.setdefault(
            parent,
            {"path": parent, "name": parts[index - 1], "kind": "dir", "size": None},
        )


def _find_member(zf: zipfile.ZipFile, requested_path: str) -> zipfile.ZipInfo | None:
    for info in zf.infolist():
        if _normalize_member_path(info.filename) == requested_path:
            return info
    return None


def _normalize_member_path(name: str) -> str:
    normalized = name.replace("\\", "/").strip("/")
    if not normalized:
        return ""
    path = PurePosixPath(normalized)
    if path.is_absolute() or PureWindowsPath(name).drive or ".." in path.parts:
        raise ArtifactError(f"Unsafe artifact path: {name}")
    return path.as_posix()


def _normalize_requested_path(name: str) -> str:
    path = _normalize_member_path(name)
    if not path:
        raise ArtifactError("Artifact file path is required")
    return path


def _language_for_path(path: str) -> str:
    return LANGUAGE_BY_EXTENSION.get(PurePosixPath(path).suffix.lower(), "plaintext")
