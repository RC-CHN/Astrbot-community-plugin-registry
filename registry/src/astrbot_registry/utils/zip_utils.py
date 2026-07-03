"""Safe zip inspection and extraction helpers."""

from __future__ import annotations

import stat
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath


class ZipValidationError(ValueError):
    """Raised when an uploaded zip violates registry safety rules."""


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = info.external_attr >> 16
    return stat.S_ISLNK(mode)


def _is_windows_drive_path(name: str) -> bool:
    return PureWindowsPath(name).drive != ""


def _validate_member_path(name: str) -> PurePosixPath:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or _is_windows_drive_path(name):
        raise ZipValidationError(f"zip entry uses an absolute path: {name}")
    if ".." in path.parts:
        raise ZipValidationError(f"zip entry escapes extraction root: {name}")
    if not path.parts:
        raise ZipValidationError("zip entry has an empty path")
    return path


def inspect_zip(
    zip_path: Path,
    *,
    max_total_uncompressed_bytes: int,
    max_file_count: int,
    max_single_file_bytes: int,
    deny_absolute_path: bool = True,
    deny_parent_path: bool = True,
    deny_symlink: bool = True,
) -> None:
    """Validate a zip archive before extraction."""
    total_size = 0
    file_count = 0
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            bad_file = zf.testzip()
            if bad_file is not None:
                raise ZipValidationError(f"zip contains a corrupt file: {bad_file}")

            for info in zf.infolist():
                if info.is_dir():
                    continue
                file_count += 1
                if file_count > max_file_count:
                    raise ZipValidationError("zip contains too many files")
                if info.file_size > max_single_file_bytes:
                    raise ZipValidationError(f"zip entry is too large: {info.filename}")
                total_size += info.file_size
                if total_size > max_total_uncompressed_bytes:
                    raise ZipValidationError("zip uncompressed size is too large")
                if deny_symlink and _is_symlink(info):
                    raise ZipValidationError(f"zip entry is a symlink: {info.filename}")
                if deny_absolute_path or deny_parent_path:
                    _validate_member_path(info.filename)
    except zipfile.BadZipFile as exc:
        raise ZipValidationError("uploaded file is not a valid zip archive") from exc


def safe_unzip(zip_path: Path, extract_dir: Path) -> None:
    """Extract a previously inspected zip without trusting ZipFile.extractall."""
    extract_root = extract_dir.resolve()
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            member_path = _validate_member_path(info.filename)
            target = (extract_root / Path(*member_path.parts)).resolve()
            if not target.is_relative_to(extract_root):
                raise ZipValidationError(f"zip entry escapes extraction root: {info.filename}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as src, target.open("wb") as dst:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    dst.write(chunk)


def find_metadata_yaml(extract_dir: Path) -> Path:
    """Find the single allowed metadata.yaml location in an extracted upload."""
    root_metadata = extract_dir / "metadata.yaml"
    if root_metadata.is_file():
        return root_metadata

    children = [child for child in extract_dir.iterdir() if child.name != "__MACOSX"]
    dirs = [child for child in children if child.is_dir()]
    files = [child for child in children if child.is_file()]
    if len(dirs) == 1 and not files:
        nested = dirs[0] / "metadata.yaml"
        if nested.is_file():
            return nested

    matches = list(extract_dir.rglob("metadata.yaml"))
    if len(matches) == 1:
        raise ZipValidationError("metadata.yaml must be at zip root or single top-level folder")
    if len(matches) > 1:
        raise ZipValidationError("zip contains multiple metadata.yaml files")
    raise ZipValidationError("metadata.yaml not found")
