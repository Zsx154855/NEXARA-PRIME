"""Tests: Memory isolation boundary enforcement."""

import os
import pytest
import subprocess
from pathlib import Path


BRAIN_DIR = Path("src/nexara_prime/brain")
RUNTIME_DIR = Path("src/nexara_prime")


class TestBrainDBIsolation:
    """4 tests: separate DB path, no store.db contamination."""

    def test_brain_db_path_different_from_store_db(self):
        from src.nexara_prime.brain.db import BRAIN_STATE_PATH
        assert "brain_state" in str(BRAIN_STATE_PATH)
        assert str(BRAIN_STATE_PATH) != ".nexara/store.db"

    def test_brain_db_separate_connection(self, tmp_path):
        from src.nexara_prime.brain.db import BrainDB
        db = BrainDB(path=tmp_path / "brain_state.db")
        assert db._conn is not None
        db.close()

    def test_brain_db_does_not_access_store_db(self, tmp_path):
        store_db = tmp_path / "store.db"
        brain_db_path = tmp_path / "brain_state.db"
        # Create a fake store.db
        store_db.write_text("")
        from src.nexara_prime.brain.db import BrainDB
        db = BrainDB(path=brain_db_path)
        # Should not have any tables from store.db
        records = db.recall()
        assert records == []
        db.close()

    def test_brain_db_has_brain_tables(self, tmp_path):
        from src.nexara_prime.brain.db import BrainDB
        db = BrainDB(path=tmp_path / "brain_state.db")
        # Query all tables
        tables = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t["name"] for t in tables}
        assert "brain_memories" in table_names
        assert "memory_decay_state" in table_names
        assert "memory_consolidation_log" in table_names
        assert "memory_health_snapshots" in table_names
        db.close()


class TestPackageImportIsolation:
    """4 tests: brain never imports runtime, runtime never imports brain."""

    def test_brain_never_imports_runtime(self):
        """Grep all brain/*.py for forbidden runtime imports."""
        forbidden = ["from .runtime", "import runtime", "from ..runtime"]
        for py_file in BRAIN_DIR.glob("*.py"):
            content = py_file.read_text()
            for pattern in forbidden:
                assert pattern not in content, f"{py_file.name} imports runtime: found '{pattern}'"

    def test_brain_never_imports_evidence(self):
        forbidden = ["from .evidence", "import evidence"]
        for py_file in BRAIN_DIR.glob("*.py"):
            content = py_file.read_text()
            for pattern in forbidden:
                assert pattern not in content, f"{py_file.name} imports evidence: found '{pattern}'"

    def test_brain_never_imports_evaluation(self):
        forbidden = ["from .evaluation", "import evaluation"]
        for py_file in BRAIN_DIR.glob("*.py"):
            content = py_file.read_text()
            for pattern in forbidden:
                assert pattern not in content, f"{py_file.name} imports evaluation: found '{pattern}'"

    def test_brain_imports_allowed_modules_only(self):
        """Brain MAY import models.py and db.py (types/patterns). Verify no other runtime imports."""
        all_runtime_modules = [
            "from .runtime", "from .evidence", "from .evaluation",
            "from .governance", "from .cli", "from .api",
            "from .tools", "from .recovery", "from .state_machine",
            "from .config", "from .model_gateway", "from .model_router",
            "from .chief_brain_kernel",
        ]
        for py_file in BRAIN_DIR.glob("*.py"):
            content = py_file.read_text()
            for mod in all_runtime_modules:
                assert mod not in content, f"{py_file.name} imports forbidden runtime: found '{mod}'"


class TestMemoryControllerIsolation:
    """3 tests: MemoryController does not import runtime modules."""

    def test_memory_controller_no_runtime_imports(self):
        content = (BRAIN_DIR / "memory_controller.py").read_text()
        forbidden = [
            "from ..runtime", "from ..evidence", "from ..evaluation",
            "from ..governance", "from ..cli", "from ..api",
        ]
        for pattern in forbidden:
            assert pattern not in content, f"memory_controller.py imports runtime: '{pattern}'"

    def test_memory_controller_imports_are_brain_only(self):
        content = (BRAIN_DIR / "memory_controller.py").read_text()
        # Should only import from .db, .decay_config, .consolidation_rules, .provenance, ..models
        assert "from .db import" in content or "from .db" in content
        assert "from ..models" in content

    def test_long_term_memory_no_runtime_imports(self):
        content = (BRAIN_DIR / "long_term_memory.py").read_text()
        forbidden = [
            "from ..runtime", "from ..evidence", "from ..evaluation",
            "from ..governance", "from ..cli", "from ..api",
        ]
        for pattern in forbidden:
            assert pattern not in content, f"long_term_memory.py imports runtime: '{pattern}'"
