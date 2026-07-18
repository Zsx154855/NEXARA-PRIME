"""DEPRECATED — compatibility alias for CapabilityRegistry (capabilities.py).

This module exists for backwards-compatibility only.
Import from ``nexara_prime.capabilities`` directly for the authoritative registry.

Will be removed in v0.2.0.
"""
# flake8: noqa

from .capabilities import CapabilityRegistry, CapabilityRegistryV2  # noqa: F401 — re-export
