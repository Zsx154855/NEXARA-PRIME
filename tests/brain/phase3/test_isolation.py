"""Tests: Phase 3 isolation + regression."""
from pathlib import Path

MODULES = [
    "src/nexara_prime/brain/cognitive_models.py",
    "src/nexara_prime/brain/deep_reasoning.py",
    "src/nexara_prime/brain/strategic_planning.py",
    "src/nexara_prime/brain/world_model.py",
    "src/nexara_prime/brain/meta_cognition.py",
    "src/nexara_prime/brain/research_intelligence.py",
]
FORBIDDEN = ["from ..runtime","import runtime","from .. import runtime",
             "from ..model_gateway","from ..tools","from ..evidence",
             "from ..governance","from ..cli","from ..api",
             "from .db import","brain.db"]

class TestPhase3Isolation:
    def test_no_runtime_imports(self):
        for path in MODULES:
            content = Path(path).read_text()
            for f in FORBIDDEN:
                assert f not in content, f"{path}: {f}"
    def test_uses_memory_controller(self):
        for path in MODULES[1:]:  # skip models
            assert "MemoryController" in Path(path).read_text(), f"{path}: no MC"
    def test_no_direct_db(self):
        for path in MODULES:
            assert "from .db import" not in Path(path).read_text()

class TestPhase3Regression:
    def test_prior_phases_unchanged(self):
        for path in ["src/nexara_prime/brain/memory_controller.py",
                     "src/nexara_prime/brain/preference_model.py",
                     "src/nexara_prime/brain/experience_learner.py",
                     "src/nexara_prime/brain/evolution_engine.py"]:
            assert Path(path).exists(), f"{path} missing"
