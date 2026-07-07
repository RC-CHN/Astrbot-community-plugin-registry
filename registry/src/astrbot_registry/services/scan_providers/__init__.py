"""Pluggable scan providers."""

from .base import ScanOutcome, ScanProvider
from .registry import (
    DEFAULT_SCAN_PROVIDER_REGISTRY,
    ScanProviderRegistry,
    get_scan_provider_registry,
    reset_scan_provider_registry,
    set_scan_provider_registry,
)

__all__ = [
    "DEFAULT_SCAN_PROVIDER_REGISTRY",
    "ScanOutcome",
    "ScanProvider",
    "ScanProviderRegistry",
    "get_scan_provider_registry",
    "reset_scan_provider_registry",
    "set_scan_provider_registry",
]
