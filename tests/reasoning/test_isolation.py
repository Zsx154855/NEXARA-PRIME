"""Tests: Reasoning Kernel isolation — no runtime/model/tool imports."""

import inspect
from pathlib import Path


REASONING_DIR = Path("src/nexara_prime/brain/reasoning")


class TestReasoningIsolation:
    """10 tests: import isolation, no brain.db, no runtime."""

    def test_no_brain_db_import(self):
        for py_file in REASONING_DIR.glob("*.py"):
            content = py_file.read_text()
            # Check for actual import statements, not docstring mentions
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("from") and "brain.db" in line:
                    assert False, f"{py_file.name}: imports brain.db: {line}"
                if line.startswith("import") and "BrainDB" in line and "from" not in line:
                    assert False, f"{py_file.name}: imports BrainDB: {line}"

    def test_no_runtime_import(self):
        for py_file in REASONING_DIR.glob("*.py"):
            content = py_file.read_text()
            assert "from ..runtime" not in content, f"{py_file.name} imports runtime"

    def test_no_evidence_import(self):
        for py_file in REASONING_DIR.glob("*.py"):
            content = py_file.read_text()
            assert "from ..evidence" not in content, f"{py_file.name} imports evidence"

    def test_no_evaluation_import(self):
        for py_file in REASONING_DIR.glob("*.py"):
            content = py_file.read_text()
            assert "from ..evaluation" not in content, f"{py_file.name} imports evaluation"

    def test_no_tools_import(self):
        for py_file in REASONING_DIR.glob("*.py"):
            content = py_file.read_text()
            assert "from ..tools" not in content, f"{py_file.name} imports tools"

    def test_no_model_gateway_import(self):
        for py_file in REASONING_DIR.glob("*.py"):
            content = py_file.read_text()
            assert "from ..model_gateway" not in content, f"{py_file.name} imports model_gateway"

    def test_no_governance_import(self):
        for py_file in REASONING_DIR.glob("*.py"):
            content = py_file.read_text()
            assert "from ..governance" not in content, f"{py_file.name} imports governance"

    def test_no_state_machine_import(self):
        for py_file in REASONING_DIR.glob("*.py"):
            content = py_file.read_text()
            assert "from ..state_machine" not in content, f"{py_file.name} imports state_machine"

    def test_no_api_import(self):
        for py_file in REASONING_DIR.glob("*.py"):
            content = py_file.read_text()
            assert "from ..api" not in content, f"{py_file.name} imports api"

    def test_allowed_imports_only(self):
        """Reasoning may import: .models, ..models, typing, dataclasses, TYPE_CHECKING."""
        for py_file in REASONING_DIR.glob("*.py"):
            content = py_file.read_text()
            # These are the only allowed parent-package imports
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("from ...") and not line.startswith("from ...models"):
                    # Allow TYPE_CHECKING guards for memory_controller
                    if "TYPE_CHECKING" in content and "memory_controller" in line:
                        continue
                    # Also allow imports from brain-level modules through triple-dot
                    if any(allowed in line for allowed in ["models", "__future__"]):
                        continue
                    assert False, f"{py_file.name}: forbidden import: {line}"
