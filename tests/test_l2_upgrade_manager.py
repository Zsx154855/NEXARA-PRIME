"""Tests for L2 UpgradeManager — versioned upgrade lifecycle."""
import json
import pytest
from pathlib import Path
from nexara_prime.upgrade_manager import UpgradeManager, UpgradeStage


@pytest.fixture
def manifest(tmp_path):
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps({
        "runtime_version": "0.1.0",
        "git_sha": "abc12345",
        "schema_version": "1",
    }))
    return p


@pytest.fixture
def manager(manifest):
    return UpgradeManager(manifest)


class TestUpgradeManager:
    def test_preflight(self, manager):
        result = manager.preflight("0.2.0")
        assert result.ok is True
        assert result.detail["current"] == "0.1.0"
        assert result.detail["target"] == "0.2.0"

    def test_snapshot(self, manager):
        result = manager.snapshot()
        assert result.ok is True
        assert result.detail["version"] == "0.1.0"

    def test_upgrade(self, manager):
        manager.snapshot()
        result = manager.upgrade("0.2.0")
        assert result.ok is True
        assert result.detail["to"] == "0.2.0"
        m = json.loads(manager.manifest_path.read_text())
        assert m["runtime_version"] == "0.2.0"

    def test_rollback(self, manager):
        manager.snapshot()
        manager.upgrade("0.2.0")
        result = manager.rollback()
        assert result.ok is True
        m = json.loads(manager.manifest_path.read_text())
        assert m["runtime_version"] == "0.1.0"

    def test_rollback_no_snapshot(self, manager):
        result = manager.rollback()
        assert result.ok is False

    def test_seal(self, manager):
        result = manager.seal()
        assert result.ok is True
        m = json.loads(manager.manifest_path.read_text())
        assert m["sealed"] is True
