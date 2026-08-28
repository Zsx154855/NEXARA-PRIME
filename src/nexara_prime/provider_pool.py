"""ProviderPool — multi-channel free-tier model routing.

Routes each completion through a rotating pool of OpenAI-compatible
channels with:

- per-channel cooldown with exponential backoff (429 / auth / transport)
- per-channel daily token ledger with warn-ratio steering
- priority ordering + load spread across equal-priority channels
- zero-channel-key anonymous tiers (OVHcloud, Kilo, LLM7, ...) supported

Configured via ``NEXARA_MODEL_POOL`` (JSON array).  Example::

    [{"name":"ovh","endpoint":"https://oai.endpoints.kepler.ai.cloud.ovh.net/v1",
      "model":"Qwen3-32B","priority":0,"daily_limit":2800},
     {"name":"zai","endpoint":"https://open.bigmodel.cn/api/paas/v4",
      "model":"glm-4.6v-flash","api_key":"${ZAI_API_KEY}","priority":1}]

``${VAR}`` api-key references resolve against the environment so secrets
never live inside the pool JSON itself.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from .model_gateway import (
    ModelProvider,
    ModelResponse,
    OpenAICompatibleProvider,
    ProviderError,
    ProviderUnavailable,
)

_DAY_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_CooldownClock = Callable[[], float]


@dataclass(frozen=True)
class PoolChannel:
    """Static description of one free-tier channel."""

    name: str
    endpoint: str
    model: str
    api_key: str | None = None
    priority: int = 0
    daily_limit: int = 0  # 0 = unlimited
    anonymous: bool = False  # True = endpoint needs no API key
    supports_images: bool = False  # True = channel accepts image input

    def __post_init__(self) -> None:
        if not self.name or not self.model:
            raise ValueError("pool_channel_requires_name_and_model")


def _resolve_key_ref(value: str) -> str:
    """Expand ``${VAR}`` references inside a configured api_key."""
    match = re.fullmatch(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", value)
    if not match:
        return value
    var = match.group(1)
    if var not in os.environ:
        raise ValueError(f"pool_api_key_env_missing:{var}")
    return os.environ[var]


class ProviderPool:
    """ModelProvider that fans completions out across free-tier channels."""

    name = "pool"

    def __init__(
        self,
        channels: list[PoolChannel],
        *,
        warn_ratio: float = 0.8,
        clock: _CooldownClock | None = None,
        providers: dict[str, ModelProvider] | None = None,
        max_output_tokens: int = 512,
    ) -> None:
        if not channels:
            raise ValueError("pool_requires_at_least_one_channel")
        self.channels = list(channels)
        self.warn_ratio = warn_ratio
        self._clock = clock if clock is not None else time.monotonic
        self._providers = providers or {}
        self._max_output_tokens = max_output_tokens
        self._cooldown_until: dict[str, float] = {}
        self._fail_streak: dict[str, int] = {}
        self._usage: dict[str, int] = {channel.name: 0 for channel in self.channels}
        self._day = date.today().isoformat()
        self.last_attempts: list[str] = []

    # ── Channel construction ───────────────────────────────────────────────

    def _provider_for(self, channel: PoolChannel) -> ModelProvider:
        if channel.name not in self._providers:
            self._providers[channel.name] = OpenAICompatibleProvider(
                channel.endpoint,
                model=channel.model,
                api_key=channel.api_key,
                provider_name=channel.name,
                max_output_tokens=self._max_output_tokens,
                anonymous=channel.anonymous,
            )
        return self._providers[channel.name]

    # ── Ledger / cooldown state ────────────────────────────────────────────

    def _roll_day_if_needed(self) -> None:
        today = date.today().isoformat()
        if today != self._day:
            self._day = today
            self._usage = {channel.name: 0 for channel in self.channels}

    def _force_day(self, day: str) -> None:
        """Test hook: simulate a day rollover."""
        if not _DAY_PATTERN.match(day):
            raise ValueError("invalid_day_format")
        self._day = day
        self._usage = {channel.name: 0 for channel in self.channels}

    def usage_today(self, name: str) -> int:
        self._roll_day_if_needed()
        return self._usage.get(name, 0)

    def _usage_ratio(self, channel: PoolChannel) -> float:
        if channel.daily_limit <= 0:
            return 0.0
        return self._usage.get(channel.name, 0) / channel.daily_limit

    def _over_daily_limit(self, channel: PoolChannel) -> bool:
        return channel.daily_limit > 0 and self._usage.get(channel.name, 0) >= channel.daily_limit

    def _is_cooling(self, channel: PoolChannel) -> bool:
        return self._cooldown_until.get(channel.name, 0.0) > self._clock()

    def _cooldown_remaining(self, name: str) -> float:
        """Test helper: seconds left in cooldown (0 when not cooling)."""
        return max(0.0, self._cooldown_until.get(name, 0.0) - self._clock())

    def _cool(self, channel: PoolChannel) -> None:
        streak = self._fail_streak.get(channel.name, 0) + 1
        self._fail_streak[channel.name] = streak
        backoff = min(8.0 * (2 ** (streak - 1)), 3600.0)
        self._cooldown_until[channel.name] = self._clock() + backoff

    def _clear_failures(self, channel: PoolChannel) -> None:
        self._fail_streak.pop(channel.name, None)
        self._cooldown_until.pop(channel.name, None)

    def _record_tokens(self, channel: PoolChannel, tokens: int) -> None:
        self._roll_day_if_needed()
        self._usage[channel.name] = self._usage.get(channel.name, 0) + max(0, tokens)

    # ── Channel selection ──────────────────────────────────────────────────

    def _pick(self, *, with_images: bool = False) -> PoolChannel | None:
        """Pick the best available channel: healthy, under daily limit,
        lowest priority, and — once usage passes the warn ratio — demoted
        behind less-used channels of the same priority.  Image requests are
        only routed to channels that declare image support."""
        self._roll_day_if_needed()
        candidates = [
            c
            for c in self.channels
            if not self._is_cooling(c)
            and not self._over_daily_limit(c)
            and (not with_images or c.supports_images)
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda c: (c.priority, 0 if self._usage_ratio(c) < self.warn_ratio else 1, self._usage_ratio(c)))
        return candidates[0]

    # ── Completion ─────────────────────────────────────────────────────────

    def complete(
        self,
        system: str,
        task: str,
        context: dict[str, Any] | None = None,
        *,
        trace_id: str = "",
        timeout_seconds: float | None = None,
        images: list[str] | None = None,
    ) -> ModelResponse:
        self.last_attempts = []
        errors: list[str] = []
        while True:
            channel = self._pick(with_images=bool(images))
            if channel is None:
                raise ProviderUnavailable("all_pool_channels_unavailable:" + "|".join(errors))
            self.last_attempts.append(channel.name)
            provider = self._provider_for(channel)
            try:
                response = provider.complete(system, task, context, trace_id=trace_id, timeout_seconds=timeout_seconds, images=images)
            except ProviderError as exc:
                errors.append(f"{channel.name}:{exc.code}")
                self._cool(channel)
                continue
            self._record_tokens(channel, response.total_tokens or response.input_tokens + response.output_tokens)
            self._clear_failures(channel)
            return response

    # ── Env-driven construction ────────────────────────────────────────────

    @classmethod
    def from_env(cls, *, warn_ratio: float = 0.8, max_output_tokens: int = 512) -> "ProviderPool | None":
        """Build a pool from ``NEXARA_MODEL_POOL`` (JSON array of channel
        objects).  Returns None when the variable is absent, raises
        ValueError on malformed JSON or unresolved key references."""
        raw = os.getenv("NEXARA_MODEL_POOL")
        if not raw:
            return None
        try:
            entries = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"nexara_model_pool_invalid_json:{exc.msg}") from exc
        if not isinstance(entries, list):
            raise ValueError("nexara_model_pool_must_be_json_array")
        channels = [
            PoolChannel(
                name=str(item["name"]),
                endpoint=str(item.get("endpoint", "")),
                model=str(item["model"]),
                api_key=_resolve_key_ref(str(item["api_key"])) if item.get("api_key") else None,
                priority=int(item.get("priority", 0)),
                daily_limit=int(item.get("daily_limit", 0)),
                anonymous=bool(item.get("anonymous", False)),
                supports_images=bool(item.get("supports_images", False)),
            )
            for item in entries
        ]
        return cls(channels, warn_ratio=warn_ratio, max_output_tokens=max_output_tokens)
