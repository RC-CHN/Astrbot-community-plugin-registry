from pathlib import Path
import zipfile

import pytest

from astrbot_registry.utils.zip_utils import (
    ZipValidationError,
    find_metadata_yaml,
    inspect_zip,
    safe_unzip,
)


def _write_zip(path: Path, entries: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)


def test_safe_zip_with_single_top_level_folder(tmp_path: Path) -> None:
    zip_path = tmp_path / "plugin.zip"
    _write_zip(
        zip_path,
        {
            "plugin/metadata.yaml": "name: astrbot_plugin_test\nauthor: tester\nversion: v1\n",
            "plugin/main.py": "print('ok')",
        },
    )

    inspect_zip(
        zip_path,
        max_total_uncompressed_bytes=1024 * 1024,
        max_file_count=10,
        max_single_file_bytes=1024 * 1024,
    )
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()
    safe_unzip(zip_path, extract_dir)

    assert find_metadata_yaml(extract_dir) == extract_dir / "plugin" / "metadata.yaml"


def test_zip_rejects_parent_path(tmp_path: Path) -> None:
    zip_path = tmp_path / "bad.zip"
    _write_zip(zip_path, {"../metadata.yaml": "bad"})

    with pytest.raises(ZipValidationError):
        inspect_zip(
            zip_path,
            max_total_uncompressed_bytes=1024 * 1024,
            max_file_count=10,
            max_single_file_bytes=1024 * 1024,
        )


def test_zip_rejects_multiple_metadata_files(tmp_path: Path) -> None:
    zip_path = tmp_path / "bad.zip"
    _write_zip(
        zip_path,
        {
            "a/metadata.yaml": "name: a",
            "b/metadata.yaml": "name: b",
        },
    )
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()
    safe_unzip(zip_path, extract_dir)

    with pytest.raises(ZipValidationError):
        find_metadata_yaml(extract_dir)
