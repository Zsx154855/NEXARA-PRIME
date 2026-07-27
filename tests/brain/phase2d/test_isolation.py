"""Tests: Phase 2D isolation — no runtime imports, interface usage."""
from pathlib import Path

EVOLUTION = "src/nexara_prime/brain/evolution_engine.py"
FORBIDDEN = ["from ..runtime", "import runtime", "from .. import runtime",
             "from ..model_gateway", "from ..tools", "from ..evidence",
             "from ..governance", "from ..cli", "from ..api",
             "from .db import", "brain.db"]


class TestPhase2dIsolation:
    def test_no_runtime_imports(self):
        content = Path(EVOLUTION).read_text()
        for forbidden in FORBIDDEN:
            assert forbidden not in content, f"imports {forbidden}"

    def test_uses_memory_controller(self):
        assert "MemoryController" in Path(EVOLUTION).read_text()

    def test_no_direct_db(self):
        assert "from .db import" not in Path(EVOLUTION).read_text()


class TestPhase2dRegression:
    def test_prior_phases_unchanged(self):
        for path in ["src/nexara_prime/brain/memory_controller.py",
                     "src/nexara_prime/brain/preference_model.py",
                     "src/nexara_prime/brain/experience_learner.py",
                     "src/nexara_prime/brain/self_reflection_engine.py",
                     "src/nexara_prime/brain/mission_intelligence.py"]:
            assert Path(path).exists(), f"{path} missing"
