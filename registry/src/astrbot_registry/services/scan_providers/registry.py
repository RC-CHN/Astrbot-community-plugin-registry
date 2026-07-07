"""Scan provider registry and dependency-injection entry points."""

from __future__ import annotations

from collections.abc import Iterable

from .base import ScanProvider
from .clamav import ClamAVProvider
from .llm_agent import LLMAgentProvider
from .virustotal import VirusTotalProvider


class ScanProviderRegistry:
    def __init__(self, providers: Iterable[ScanProvider]):
        self._providers = {provider.name: provider for provider in providers}

    @property
    def providers(self) -> dict[str, ScanProvider]:
        return dict(self._providers)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._providers)

    @property
    def legacy_public_names(self) -> tuple[str, ...]:
        return tuple(provider.name for provider in self._providers.values() if provider.legacy_public)

    def get(self, name: str) -> ScanProvider | None:
        return self._providers.get(name)

    def validate(self, names: Iterable[str]) -> list[str]:
        selected = list(names)
        invalid = sorted(set(selected) - set(self._providers))
        if invalid:
            raise ValueError(f"Invalid scan providers: {', '.join(invalid)}")
        return [name for name in self._providers if name in selected]


DEFAULT_SCAN_PROVIDER_REGISTRY = ScanProviderRegistry(
    (
        ClamAVProvider(),
        VirusTotalProvider(),
        LLMAgentProvider(),
    )
)


_scan_provider_registry = DEFAULT_SCAN_PROVIDER_REGISTRY


def get_scan_provider_registry() -> ScanProviderRegistry:
    return _scan_provider_registry


def set_scan_provider_registry(registry: ScanProviderRegistry) -> None:
    global _scan_provider_registry
    _scan_provider_registry = registry


def reset_scan_provider_registry() -> None:
    set_scan_provider_registry(DEFAULT_SCAN_PROVIDER_REGISTRY)
