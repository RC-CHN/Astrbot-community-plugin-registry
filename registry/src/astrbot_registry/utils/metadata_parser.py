"""metadata.yaml parsing and validation."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class PluginMetadata(BaseModel):
    """Parsed metadata.yaml for an AstrBot plugin."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    display_name: str | None = None
    desc: str | None = Field(default=None, alias="description")
    short_desc: str | None = None
    author: str
    version: str
    repo: str | None = None
    tags: list[str] = []
    category: str | None = None
    social_link: str | None = None
    logo: str | None = None
    astrbot_version: str | None = None
    support_platforms: list[str] = []
    i18n: dict[str, Any] = {}

    @model_validator(mode="after")
    def normalize(self) -> "PluginMetadata":
        if not self.display_name:
            self.display_name = self.name
        if not self.desc:
            self.desc = self.short_desc or ""
        if self.tags is None:
            self.tags = []
        if self.support_platforms is None:
            self.support_platforms = []
        if self.i18n is None:
            self.i18n = {}
        return self


def parse_metadata_yaml(path: Path) -> PluginMetadata:
    """Parse a metadata.yaml file into a PluginMetadata instance."""
    with open(path, "r", encoding="utf-8") as f:
        return parse_metadata_yaml_text(f.read())


def parse_metadata_yaml_text(content: str) -> PluginMetadata:
    """Parse metadata.yaml content into a PluginMetadata instance."""
    data = yaml.safe_load(content)
    if not isinstance(data, dict):
        raise ValueError("metadata.yaml must be a YAML mapping")
    return PluginMetadata.model_validate(data)


def overwrite_metadata_version(path: Path, version: str) -> None:
    """Update the version field in metadata.yaml."""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("metadata.yaml must be a YAML mapping")
    data["version"] = version
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def infer_plugin_key(name: str) -> str:
    """Derive a registry plugin key from the plugin package name.

    Example: ``astrbot_plugin_nezhatz`` -> ``astrbot-plugin-nezhatz``.
    """
    return name.strip().lower().replace("_", "-")
