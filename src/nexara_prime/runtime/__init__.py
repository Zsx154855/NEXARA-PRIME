"""NEXARA PRIME Runtime — composition root, lifecycle, heartbeat, doctor."""
from nexara_prime.runtime.nexara_prime import NexaraPrime
from nexara_prime.runtime.lifecycle import LifecycleState, RuntimeLifecycle
from nexara_prime.runtime.heartbeat import Heartbeat
from nexara_prime.runtime.doctor import Doctor

# Re-export the v1 NexaraRuntime from the legacy runtime module for backward compat
from nexara_prime.runtime.nexara_runtime_v1 import NexaraRuntime  # noqa: F401

__all__ = [
    "NexaraPrime",
    "NexaraRuntime",
    "LifecycleState",
    "RuntimeLifecycle",
    "Heartbeat",
    "Doctor",
]
