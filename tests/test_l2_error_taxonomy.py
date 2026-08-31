"""Tests for L2 ErrorTaxonomy — deterministic error classification."""
import pytest
from nexara_prime.error_taxonomy import ErrorTaxonomy, ErrorTaxonomyEntry


class TestErrorTaxonomyLookup:
    def test_known_code(self):
        entry = ErrorTaxonomy.lookup("TRANSIENT")
        assert entry.retryable is True
        assert entry.max_retry == 5
        assert entry.backoff == "exponential"

    def test_case_insensitive(self):
        entry = ErrorTaxonomy.lookup("timeout")
        assert entry.error_code == "TIMEOUT"

    def test_unknown_falls_to_unknown(self):
        entry = ErrorTaxonomy.lookup("NONEXISTENT_ERROR")
        assert entry.error_code == "UNKNOWN"
        assert entry.retryable is False
        assert entry.evidence_required is True

    def test_idempotency_conflict_not_retryable(self):
        entry = ErrorTaxonomy.lookup("TOOL_IDEMPOTENCY_CONFLICT")
        assert entry.retryable is False
        assert entry.recovery_strategy == "reuse_existing"

    def test_all_entries_count(self):
        entries = ErrorTaxonomy.all_entries()
        assert len(entries) == 15

    def test_codes_returns_strings(self):
        codes = ErrorTaxonomy.codes()
        assert "TRANSIENT" in codes
        assert "UNKNOWN" in codes
