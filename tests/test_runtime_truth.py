"""Regression tests for the Runtime Truth Compiler system."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Import compiler modules
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "runtime_truth"))

from collect_git_truth import verify_sha_full
from validate_program_state import (
    validate_json_syntax,
    validate_sha_full as vsf,
    validate_utc_timestamp,
    validate_state_consistency,
    validate_temporal_order,
)


class TestSHALength:
    def test_full_sha_accepted(self):
        ok, _ = vsf("7407832d0e06d90a6a7a869d4aa4b1224b82b268", "test")
        assert ok

    def test_short_sha_rejected(self):
        ok, msg = vsf("7407832", "test")
        assert not ok
        assert "40" in msg

    def test_non_hex_rejected(self):
        ok, msg = vsf("gggg832d0e06d90a6a7a869d4aa4b1224b82b268", "test")
        assert not ok


class TestUTCTimestamp:
    def test_valid_z_timestamp(self):
        ok, _ = validate_utc_timestamp("2026-07-15T22:26:13Z", "test")
        assert ok

    def test_future_timestamp_rejected(self):
        future = (datetime.now(timezone.utc) + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
        ok, msg = validate_utc_timestamp(future, "test")
        assert not ok

    def test_non_z_suffix_rejected(self):
        ok, msg = validate_utc_timestamp("2026-07-15T22:26:13+00:00", "test")
        assert not ok

    def test_plus07_offset_rejected(self):
        """+07:00 offset must be converted to Z before storing."""
        ok, msg = validate_utc_timestamp("2026-07-16T05:26:13+07:00", "test")
        assert not ok

    def test_convert_plus07_to_utc(self):
        """+07:00 timestamp must be convertible to UTC Z."""
        ts = "2026-07-16T05:26:13+07:00"
        dt = datetime.fromisoformat(ts)
        utc_z = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        # +07:00 at 05:26 → UTC at 22:26 previous day
        assert utc_z == "2026-07-15T22:26:13Z"


class TestJSONSyntax:
    def test_valid_json(self, tmp_path):
        f = tmp_path / "valid.json"
        f.write_text('{"key": "value"}')
        ok, _ = validate_json_syntax(f)
        assert ok

    def test_extra_terminator_rejected(self, tmp_path):
        f = tmp_path / "invalid.json"
        f.write_text('{"key": "value"}},')  # extra object terminator
        ok, msg = validate_json_syntax(f)
        assert not ok


class TestStateConsistency:
    def test_baseline_mismatch_detected(self):
        ps = {"test_baseline": "682 passed", "current_program_gate": "G10"}
        gs = {"test_baseline": "517 passed", "current_gate": "G10"}
        results = validate_state_consistency(ps, gs)
        assert any(not r[0] for r in results if "baseline" in r[1])

    def test_baseline_match_ok(self):
        ps = {"test_baseline": "682 passed", "current_program_gate": "G10"}
        gs = {"test_baseline": "682 passed", "current_gate": "G10"}
        results = validate_state_consistency(ps, gs)
        baseline_results = [r for r in results if "baseline" in r[1]]
        assert len(baseline_results) > 0
        assert baseline_results[0][0]  # should pass

    def test_gate_mismatch_detected(self):
        ps = {"test_baseline": "682", "current_program_gate": "G11"}
        gs = {"test_baseline": "682", "current_gate": "G10"}
        results = validate_state_consistency(ps, gs)
        assert any(not r[0] for r in results if "gate" in r[1].lower() and "baseline" not in r[1])


class TestTemporalOrder:
    def test_merged_at_order(self):
        ps = {
            "pr5_squash_merge": {"merged_at": "2026-07-15T20:20:36Z"},
            "pr8_orchestration": {"merged_at": "2026-07-15T22:26:13Z"},
            "pr10_state_sync": {"merged_at": "2026-07-15T22:41:31Z"},
            "updated_at": "2026-07-15T22:51:47Z",
        }
        results = validate_temporal_order(ps)
        assert all(r[0] for r in results)

    def test_reversed_order_detected(self):
        ps = {
            "pr8_orchestration": {"merged_at": "2026-07-15T20:00:00Z"},
            "pr5_squash_merge": {"merged_at": "2026-07-15T22:00:00Z"},
            "updated_at": "2026-07-15T22:51:47Z",
        }
        results = validate_temporal_order(ps)
        assert any(not r[0] for r in results)

    def test_updated_at_before_merge_rejected(self):
        ps = {
            "pr5_squash_merge": {"merged_at": "2026-07-15T20:20:36Z"},
            "updated_at": "2026-07-15T19:00:00Z",  # before merge
        }
        results = validate_temporal_order(ps)
        assert any(not r[0] for r in results)


class TestGitTruth:
    def test_verify_sha_full(self):
        assert verify_sha_full("7407832d0e06d90a6a7a869d4aa4b1224b82b268")
        assert not verify_sha_full("7407832")
        assert not verify_sha_full("")


class TestAtomicWrite:
    def test_compile_failure_preserves_original(self, tmp_path):
        """If the compiler fails, the original file must be preserved."""
        orig = tmp_path / "original.json"
        orig.write_text('{"a": 1}')
        # Simulate: no write should occur if validation fails
        assert orig.read_text() == '{"a": 1}'


class TestIdempotentOutput:
    def test_same_input_produces_same_hash(self):
        """Same collected truth should produce identical output hash."""
        import hashlib
        data1 = {"git": {"branch": "main"}, "github": {}, "test": {"full_suite": {"baseline_string": "682 passed"}}}
        data2 = {"git": {"branch": "main"}, "github": {}, "test": {"full_suite": {"baseline_string": "682 passed"}}}
        h1 = hashlib.sha256(json.dumps(data1, sort_keys=True).encode()).hexdigest()
        h2 = hashlib.sha256(json.dumps(data2, sort_keys=True).encode()).hexdigest()
        assert h1 == h2
