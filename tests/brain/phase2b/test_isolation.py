"""Tests: Phase 2B isolation — no runtime imports."""

PHASE2B = "src/nexara_prime/brain"
FORBIDDEN = ["runtime.py", "models.py (import)", "evidence.py", "tools.py",
             "model_gateway.py", "governance.py", "cli.py", "api.py"]


class TestPhase2bIsolation:
    def test_preference_model_no_runtime_imports(self):
        with open(f"{PHASE2B}/preference_model.py") as f:
            content = f.read()
        for forbidden in FORBIDDEN:
            assert f"from ..{forbidden}" not in content, f"preference_model imports {forbidden}"
            assert "import src.nexara_prime.runtime" not in content

    def test_experience_learner_no_runtime_imports(self):
        with open(f"{PHASE2B}/experience_learner.py") as f:
            content = f.read()
        for forbidden in FORBIDDEN:
            assert f"from ..{forbidden}" not in content, f"experience_learner imports {forbidden}"

    def test_both_modules_use_memory_controller_interface(self):
        with open(f"{PHASE2B}/preference_model.py") as f:
            assert "MemoryController" in f.read()
        with open(f"{PHASE2B}/experience_learner.py") as f:
            assert "MemoryController" in f.read()

    def test_no_direct_db_imports(self):
        for module in ["preference_model.py", "experience_learner.py"]:
            with open(f"{PHASE2B}/{module}") as f:
                content = f.read()
            assert "from .db import" not in content, f"{module} imports BrainDB directly"
            assert "brain.db" not in content, f"{module} references brain.db"
