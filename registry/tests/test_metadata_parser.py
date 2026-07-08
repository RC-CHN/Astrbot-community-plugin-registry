import tempfile
from pathlib import Path

from astrbot_registry.utils.metadata_parser import (
    PluginMetadata,
    infer_plugin_key,
    overwrite_metadata_version,
    parse_metadata_yaml,
)

SAMPLE_METADATA = """
name: astrbot_plugin_nezhatz
display_name: 哪吒探针
desc: 查看哪吒监控站点的服务器状态等信息
author: 叹号大帝
version: v1.0.0
repo: https://github.com/thTag/astrbot_plugin_nezhatz
tags:
  - monitor
  - nezha
category: utilities
astrbot_version: ">=4.16"
support_platforms:
  - aiocqhttp
i18n:
  en-US:
    desc: Monitor plugin
"""


def test_parse_metadata_yaml() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "metadata.yaml"
        path.write_text(SAMPLE_METADATA, encoding="utf-8")
        meta = parse_metadata_yaml(path)

    assert isinstance(meta, PluginMetadata)
    assert meta.name == "astrbot_plugin_nezhatz"
    assert meta.display_name == "哪吒探针"
    assert meta.desc == "查看哪吒监控站点的服务器状态等信息"
    assert meta.author == "叹号大帝"
    assert meta.version == "v1.0.0"
    assert meta.tags == ["monitor", "nezha"]
    assert meta.category == "utilities"
    assert meta.astrbot_version == ">=4.16"
    assert meta.support_platforms == ["aiocqhttp"]
    assert meta.i18n == {"en-US": {"desc": "Monitor plugin"}}


def test_infer_plugin_key() -> None:
    assert infer_plugin_key("astrbot_plugin_nezhatz") == "astrbot-plugin-nezhatz"


def test_overwrite_metadata_version() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "metadata.yaml"
        path.write_text(SAMPLE_METADATA, encoding="utf-8")

        overwrite_metadata_version(path, "v2.0.0")
        meta = parse_metadata_yaml(path)

    assert meta.version == "v2.0.0"
    assert meta.name == "astrbot_plugin_nezhatz"
