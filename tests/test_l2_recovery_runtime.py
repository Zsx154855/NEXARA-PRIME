"""Tests for L2 RecoveryExecutor — deterministic recovery decisions."""
import pytest
from nexara_prime.recovery_runtime import RecoveryExecutor
from nexara_prime.error_taxonomy import ErrorTaxonomy


class TestRecoveryExecutorClassify:
    def setup_method(self):
        self.executor = RecoveryExecutor()

    def test_classify_timeout(self):
        result = self.executor.classify("TimeoutError")
        assert result["error_code"] == "TIMEOUT"
        assert result["retryable"] is True

    def test_classify_permission_denied(self):
        result = self.executor.classify("PermissionError", "access forbidden")
        assert result["error_code"] == "TOOL_PERMISSION_DENIED"
        assert result["retryable"] is False

    def test_classify_idempotency_from_message(self):
        result = self.executor.classify("SomeError", "idempotency key conflict")
        assert result["error_code"] == "TOOL_IDEMPOTENCY_CONFLICT"
        assert result["recovery_strategy"] == "reuse_existing"

    def test_classify_unknown_fails_closed(self):
        result = self.executor.classify("WeirdCustomError")
        assert result["error_code"] == "UNKNOWN"
        assert result["retryable"] is False


class TestRecoveryExecutorShouldRetry:
    def setup_method(self):
        self.executor = RecoveryExecutor()

    def test_retryable_within_limit(self):
        assert self.executor.should_retry(0, "TIMEOUT") is True
        assert self.executor.should_retry(2, "TIMEOUT") is True

    def test_retryable_exceeds_limit(self):
        assert self.executor.should_retry(3, "TIMEOUT") is False

    def test_non_retryable_always_false(self):
        assert self.executor.should_retry(0, "TOOL_PERMISSION_DENIED") is False

    def test_camel_case_normalization(self):
        result = self.executor.classify("RateLimitError")
        assert result["error_code"] == "RATE_LIMIT"
