"""ProviderPool tests: channel rotation, cooldown backoff, daily ledger,
priority ordering, warn-ratio steering, day rollover, and env parsing."""

from __future__ import annotations

import json

import pytest

from nexara_prime.model_gateway import (
    ModelResponse,
    ProviderError,
    ProviderUnavailable,
)
from nexara_prime.provider_pool import PoolChannel, ProviderPool


def _channel_provider(name: str, behaviour):
    """Build a ModelProvider whose complete() is controlled by `behaviour`.

    `behaviour` is a callable receiving the provider instance and returning
    either a ModelResponse or raising ProviderError.
    """

    class _Fake:
        provider_name = name
        calls: list[str] = []

        def complete(self, system, task, context=None, *, trace_id="", timeout_seconds=None, images=None):
            self.calls.append(self.provider_name)
            return behaviour(self)

    return _Fake()


def _response(provider_name: str, tokens: int = 5) -> ModelResponse:
    return ModelResponse(provider_name, "fake-model", "ok", tokens, tokens)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def clock():
    """Injectable monotonic clock for deterministic cooldown tests."""
    state = {"now": 1_000_000.0}

    def now() -> float:
        return state["now"]

    def advance(seconds: float) -> None:
        state["now"] += seconds

    return now, advance


def make_pool(channels, *, warn_ratio=0.8, clock=None, providers=None):
    return ProviderPool(channels, warn_ratio=warn_ratio, clock=clock[0] if clock else None, providers=providers)


# ── Construction ─────────────────────────────────────────────────────────────


def test_empty_pool_raises():
    with pytest.raises(ValueError):
        ProviderPool([])


def test_channel_without_model_raises():
    with pytest.raises(ValueError):
        PoolChannel(name="x", endpoint="https://example.com/v1", model="")


# ── Routing ──────────────────────────────────────────────────────────────────


def test_single_channel_success_records_usage():
    ch = _channel_provider("a", lambda p: _response("a"))
    pool = ProviderPool([PoolChannel("a", "https://a/v1", "m")], providers={"a": ch})
    pool.complete("sys", "task")
    assert ch.calls == ["a"]
    assert pool.usage_today("a") > 0


def test_priority_order_picks_lowest_first():
    ch_a = _channel_provider("a", lambda p: _response("a"))
    ch_b = _channel_provider("b", lambda p: _response("b"))
    pool = ProviderPool(
        [PoolChannel("a", "https://a/v1", "m", priority=10), PoolChannel("b", "https://b/v1", "m", priority=1)],
        providers={"a": ch_a, "b": ch_b},
    )
    pool.complete("sys", "task")
    assert ch_b.calls == ["b"]
    assert ch_a.calls == []


def test_rate_limited_channel_cooled_and_next_used():
    def fail_429(_):
        raise ProviderError("a_rate_limited", code="rate_limited", retryable=True)

    ch_a = _channel_provider("a", fail_429)
    ch_b = _channel_provider("b", lambda p: _response("b"))
    pool = ProviderPool(
        [PoolChannel("a", "https://a/v1", "m"), PoolChannel("b", "https://b/v1", "m")],
        providers={"a": ch_a, "b": ch_b},
    )
    result = pool.complete("sys", "task")
    assert result.provider == "b"
    assert ch_a.calls == ["a"]
    # channel a is now cooling: a second call goes straight to b
    pool.complete("sys", "task")
    assert ch_a.calls == ["a"]
    assert ch_b.calls == ["b", "b"]


def test_auth_failure_cools_channel_long_and_tries_next():
    def fail_401(_):
        raise ProviderError("a_authentication_failed", code="authentication_failed", retryable=False)

    ch_a = _channel_provider("a", fail_401)
    ch_b = _channel_provider("b", lambda p: _response("b"))
    pool = ProviderPool(
        [PoolChannel("a", "https://a/v1", "m"), PoolChannel("b", "https://b/v1", "m")],
        providers={"a": ch_a, "b": ch_b},
    )
    result = pool.complete("sys", "task")
    assert result.provider == "b"
    pool.complete("sys", "task")
    assert ch_a.calls == ["a"]  # still cooling, never retried


def test_transport_error_tries_next_channel():
    def fail_transport(_):
        raise ProviderError("a_transport", code="transport_error", retryable=True)

    ch_a = _channel_provider("a", fail_transport)
    ch_b = _channel_provider("b", lambda p: _response("b"))
    pool = ProviderPool(
        [PoolChannel("a", "https://a/v1", "m"), PoolChannel("b", "https://b/v1", "m")],
        providers={"a": ch_a, "b": ch_b},
    )
    assert pool.complete("sys", "task").provider == "b"


def test_all_channels_failing_raises_unavailable():
    def fail(_):
        raise ProviderError("rate_limited", code="rate_limited", retryable=True)

    ch_a = _channel_provider("a", fail)
    ch_b = _channel_provider("b", fail)
    pool = ProviderPool(
        [PoolChannel("a", "https://a/v1", "m"), PoolChannel("b", "https://b/v1", "m")],
        providers={"a": ch_a, "b": ch_b},
    )
    with pytest.raises(ProviderUnavailable):
        pool.complete("sys", "task")


def test_non_retryable_invalid_response_still_tries_next_channel():
    def fail_invalid(_):
        raise ProviderError("a_invalid_response", code="invalid_response", retryable=False)

    ch_a = _channel_provider("a", fail_invalid)
    ch_b = _channel_provider("b", lambda p: _response("b"))
    pool = ProviderPool(
        [PoolChannel("a", "https://a/v1", "m"), PoolChannel("b", "https://b/v1", "m")],
        providers={"a": ch_a, "b": ch_b},
    )
    assert pool.complete("sys", "task").provider == "b"


# ── Cooldown ─────────────────────────────────────────────────────────────────


def test_cooldown_expires_and_channel_recovers(clock):
    state, advance = clock
    failures = {"n": 0}

    def fail_then_ok(_):
        failures["n"] += 1
        if failures["n"] == 1:
            raise ProviderError("a_rate_limited", code="rate_limited", retryable=True)
        return _response("a")

    ch_a = _channel_provider("a", fail_then_ok)
    pool = make_pool([PoolChannel("a", "https://a/v1", "m")], clock=clock, providers={"a": ch_a})

    with pytest.raises(ProviderUnavailable):
        pool.complete("sys", "task")  # first call fails -> cooldown
    advance(61.0)  # first backoff cap is 30s; 61s clears it
    result = pool.complete("sys", "task")
    assert result.provider == "a"


def test_exponential_backoff_caps_at_one_hour(clock):
    state, advance = clock
    failures = {"n": 0}

    def fail(_):
        failures["n"] += 1
        raise ProviderError("a_rate_limited", code="rate_limited", retryable=True)

    ch_a = _channel_provider("a", fail)
    pool = make_pool([PoolChannel("a", "https://a/v1", "m")], clock=clock, providers={"a": ch_a})

    for _ in range(8):
        with pytest.raises(ProviderUnavailable):
            pool.complete("sys", "task")
    # after 8 consecutive failures the channel is cooling for 1h (cap)
    assert pool._cooldown_remaining("a") <= 3600.0
    advance(3601.0)
    assert pool._cooldown_remaining("a") == 0.0


# ── Daily ledger ─────────────────────────────────────────────────────────────


def test_daily_limit_exhausted_falls_to_next_channel():
    ch_a = _channel_provider("a", lambda p: _response("a", tokens=10))
    ch_b = _channel_provider("b", lambda p: _response("b"))
    pool = ProviderPool(
        [PoolChannel("a", "https://a/v1", "m", daily_limit=15), PoolChannel("b", "https://b/v1", "m")],
        providers={"a": ch_a, "b": ch_b},
    )
    assert pool.complete("sys", "task").provider == "a"  # 10 tokens used
    assert pool.complete("sys", "task").provider == "b"  # 20 > 15 limit
    assert ch_a.calls == ["a"]


def test_warn_ratio_prefers_less_used_channel():
    ch_a = _channel_provider("a", lambda p: _response("a", tokens=9))
    ch_b = _channel_provider("b", lambda p: _response("b", tokens=1))
    pool = ProviderPool(
        [PoolChannel("a", "https://a/v1", "m", daily_limit=10), PoolChannel("b", "https://b/v1", "m", daily_limit=10)],
        providers={"a": ch_a, "b": ch_b},
        warn_ratio=0.8,
    )
    pool.complete("sys", "task")  # a: 9/10 = 90% >= 80% warn
    pool.complete("sys", "task")  # picks b (0/10), not a
    assert ch_b.calls == ["b"]


def test_day_rollover_resets_ledger():
    ch_a = _channel_provider("a", lambda p: _response("a", tokens=10))
    pool = ProviderPool(
        [PoolChannel("a", "https://a/v1", "m", daily_limit=15)],
        providers={"a": ch_a},
    )
    pool.complete("sys", "task")
    pool._force_day("2099-01-01")
    assert pool.usage_today("a") == 0


def test_images_route_only_to_image_capable_channels():
    ch_text = _channel_provider("text", lambda p: _response("text"))
    ch_vl = _channel_provider("vl", lambda p: _response("vl"))
    pool = ProviderPool(
        [PoolChannel("text", "https://t/v1", "m", priority=0), PoolChannel("vl", "https://v/v1", "m", priority=1, supports_images=True)],
        providers={"text": ch_text, "vl": ch_vl},
    )
    result = pool.complete("sys", "task", images=["data:image/png;base64,AAA"])
    assert result.provider == "vl"
    assert ch_text.calls == []


def test_images_with_no_image_capable_channel_raises():
    ch_text = _channel_provider("text", lambda p: _response("text"))
    pool = ProviderPool(
        [PoolChannel("text", "https://t/v1", "m")],
        providers={"text": ch_text},
    )
    with pytest.raises(ProviderUnavailable):
        pool.complete("sys", "task", images=["data:image/png;base64,AAA"])
    assert ch_text.calls == []


# ── Env parsing ──────────────────────────────────────────────────────────────


def test_from_env_parses_json_channels(monkeypatch):
    payload = json.dumps([
        {"name": "ovh", "endpoint": "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1", "model": "Qwen3-32B", "priority": 0, "anonymous": True},
        {"name": "kilo", "endpoint": "https://api.kilo.ai/api/gateway", "model": "kilo-auto/free", "priority": 1, "daily_limit": 200, "anonymous": True},
        {"name": "zai", "endpoint": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4.6v-flash", "api_key": "${ZAI_API_KEY}", "priority": 2},
    ])
    monkeypatch.setenv("NEXARA_MODEL_POOL", payload)
    monkeypatch.setenv("ZAI_API_KEY", "secret-key")
    pool = ProviderPool.from_env()
    assert pool is not None
    assert [c.name for c in pool.channels] == ["ovh", "kilo", "zai"]
    assert pool.channels[0].anonymous is True
    assert pool.channels[2].api_key == "secret-key"
    assert pool.channels[2].anonymous is False


def test_from_env_missing_env_returns_none(monkeypatch):
    monkeypatch.delenv("NEXARA_MODEL_POOL", raising=False)
    assert ProviderPool.from_env() is None


def test_from_env_invalid_json_raises(monkeypatch):
    monkeypatch.setenv("NEXARA_MODEL_POOL", "{not json")
    with pytest.raises(ValueError):
        ProviderPool.from_env()


def test_env_key_ref_missing_var_raises(monkeypatch):
    payload = json.dumps([
        {"name": "zai", "endpoint": "https://z/v1", "model": "m", "api_key": "${MISSING_KEY}"},
    ])
    monkeypatch.setenv("NEXARA_MODEL_POOL", payload)
    monkeypatch.delenv("MISSING_KEY", raising=False)
    with pytest.raises(ValueError):
        ProviderPool.from_env()
