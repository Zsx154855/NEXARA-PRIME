"""DEPRECATED — compatibility alias for TokenCompiler (token_compiler.py).

This module exists for backwards-compatibility only.
Import from ``nexara_prime.token_compiler`` directly for the authoritative compiler.

Will be removed in v0.2.0.
"""
# flake8: noqa

from .token_compiler import TokenCompiler, TokenCompilerV2  # noqa: F401 — re-export
