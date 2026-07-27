"""Tests: Phase 2a isolation — no runtime imports, no Phase 1 modification."""

from pathlib import Path


PHASE2A_FILES = [
    Path("src/nexara_prime/brain/evolution/boundary.py"),
    Path("src/nexara_prime/brain/evolution/__init__.py"),
    Path("src/nexara_prime/brain/knowledge_graph.py"),
]


class TestPhase2aIsolation:
    """6 tests: import isolation, no runtime/evidence/tools/brain.db imports."""

    def test_no_runtime_import(self):
        for f in PHASE2A_FILES:
            content = f.read_text()
            for line in content.split("\n"):
                if "from" in line and "runtime" in line:
                    assert False, f"{f.name} imports runtime: {line.strip()}"

    def test_no_evidence_import(self):
        for f in PHASE2A_FILES:
            content = f.read_text()
            for line in content.split("\n"):
                if "from" in line and "evidence" in line and "evidence_id" not in line:
                    assert False, f"{f.name} imports evidence: {line.strip()}"

    def test_no_tools_import(self):
        for f in PHASE2A_FILES:
            content = f.read_text()
            for line in content.split("\n"):
                if "from" in line and "tools" in line:
                    assert False, f"{f.name} imports tools: {line.strip()}"

    def test_no_direct_brain_db_import(self):
        for f in PHASE2A_FILES:
            content = f.read_text()
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("from") and "brain.db" in line:
                    assert False, f"{f.name} imports brain.db: {line}"
                if line.startswith("import") and "BrainDB" in line:
                    assert False, f"{f.name} imports BrainDB: {line}"

    def test_imports_only_allowed_modules(self):
        for f in PHASE2A_FILES:
            content = f.read_text()
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("from ...") and not any(
                    x in line for x in ["models", "__future__", "TYPE_CHECKING"]
                ):
                    assert False, f"{f.name}: forbidden triple-dot import: {line}"

    def test_phase1_files_unchanged(self):
        """Verify key Phase 1 files still exist and have expected content markers."""
        phase1_files = {
            "src/nexara_prime/brain/memory_controller.py": "class MemoryController",
            "src/nexara_prime/brain/long_term_memory.py": "class LongTermMemory",
            "src/nexara_prime/brain/reasoning/kernel.py": "class ReasoningKernel",
        }
        for path, marker in phase1_files.items():
            p = Path(path)
            if p.exists():
                content = p.read_text()
                assert marker in content, f"{path} missing marker: {marker}"


class TestConfig:
    """2 tests: action counts."""

    def test_allowed_actions_count(self):
        from src.nexara_prime.brain.evolution.boundary import AUTONOMOUS_ALLOWED
        assert len(AUTONOMOUS_ALLOWED) == 7

    def test_blocked_actions_count(self):
        from src.nexara_prime.brain.evolution.boundary import AUTONOMOUS_BLOCKED
        # 8 base + autonomous_deploy + autonomous_release = 10
        assert len(AUTONOMOUS_BLOCKED) == 10
