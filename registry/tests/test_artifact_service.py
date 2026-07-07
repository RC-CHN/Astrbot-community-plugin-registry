import zipfile

from astrbot_registry.services.artifact_service import (
    MAX_PREVIEW_BYTES,
    _read_artifact_file,
    _read_artifact_tree,
)


def test_read_artifact_tree_includes_parent_dirs(tmp_path) -> None:
    zip_path = tmp_path / "plugin.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("metadata.yaml", "name: demo\n")
        zf.writestr("pkg/main.py", "print('ok')\n")

    result = _read_artifact_tree(zip_path)

    entries = {item["path"]: item for item in result["entries"]}
    assert entries == {
        "metadata.yaml": {"path": "metadata.yaml", "name": "metadata.yaml", "kind": "file", "size": 11},
        "pkg": {"path": "pkg", "name": "pkg", "kind": "dir", "size": None},
        "pkg/main.py": {"path": "pkg/main.py", "name": "main.py", "kind": "file", "size": 12},
    }


def test_read_artifact_file_returns_text_preview(tmp_path) -> None:
    zip_path = tmp_path / "plugin.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("main.py", "print('ok')\n")

    result = _read_artifact_file(zip_path, "main.py")

    assert result["binary"] is False
    assert result["truncated"] is False
    assert result["language"] == "python"
    assert result["content"] == "print('ok')\n"


def test_read_artifact_file_truncates_large_text(tmp_path) -> None:
    zip_path = tmp_path / "plugin.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("large.txt", "a" * (MAX_PREVIEW_BYTES + 10))

    result = _read_artifact_file(zip_path, "large.txt")

    assert result["binary"] is False
    assert result["truncated"] is True
    assert len(result["content"]) == MAX_PREVIEW_BYTES


def test_read_artifact_file_marks_binary(tmp_path) -> None:
    zip_path = tmp_path / "plugin.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("image.png", b"\x89PNG\x00")

    result = _read_artifact_file(zip_path, "image.png")

    assert result["binary"] is True
    assert result["content"] is None
