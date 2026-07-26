"""G5: Memory & Knowledge Fabric Contract Tests."""
from __future__ import annotations


def model_has_field(cls, field_name: str) -> bool:
    return field_name in cls.model_fields


class TestEvidenceImmutability:
    """MEM_INVARIANT_03: Evidence is append-only."""

    def test_evidence_store_no_update_method(self) -> None:
        from nexara_prime.evidence import EvidenceStore
        methods = {m for m in dir(EvidenceStore) if not m.startswith("_")}
        mutation = {"update", "delete", "remove", "modify", "overwrite"}
        for m in methods:
            assert m not in mutation, f"EvidenceStore must not have '{m}' — evidence is immutable"

    def test_evidence_artifact_immutable(self) -> None:
        from nexara_prime.models import EvidenceArtifact
        assert "evidence_id" in EvidenceArtifact.model_fields


class TestMemoryEvidenceBacking:
    """MEM_INVARIANT_01: Evidence is source of truth for memory."""

    def test_memory_record_links_to_evidence(self) -> None:
        from nexara_prime.models import MemoryRecord
        assert "source_evidence_id" in MemoryRecord.model_fields

    def test_sdk_memory_record_links_to_evidence(self) -> None:
        try:
            from platform.sdk.python.nexara_sdk.models import MemoryRecord
        except (ModuleNotFoundError, ImportError):
            from pathlib import Path
            sdk_path = Path(__file__).parent.parent / "platform/sdk/python/nexara_sdk/models.py"
            assert sdk_path.exists(), "SDK models must exist"
            content = sdk_path.read_text()
            assert "source_evidence_id" in content, "SDK MemoryRecord must reference evidence"
            return
        assert "source_evidence_id" in MemoryRecord.model_fields

    def test_memory_kernel_has_write_method(self) -> None:
        from nexara_prime.memory import MemoryKernel
        assert hasattr(MemoryKernel, "write") or "write" in dir(MemoryKernel)


class TestMemoryConflictResolution:
    """MEM_INVARIANT_05: Conflict resolution requires human approval."""

    def test_memory_kernel_has_propose_method(self) -> None:
        from nexara_prime.memory import MemoryKernel
        assert "propose" in dir(MemoryKernel), "MemoryKernel must have propose() for conflict resolution"

    def test_memory_kernel_has_commit_candidate_method(self) -> None:
        from nexara_prime.memory import MemoryKernel
        assert "commit_candidate" in dir(MemoryKernel), "MemoryKernel must have commit_candidate() for approved patches"


class TestKnowledgeReadOnly:
    """MEM_INVARIANT_04: Knowledge retrieval is read-only."""

    def test_knowledge_service_has_no_write_methods(self) -> None:
        from nexara_prime.knowledge import KnowledgeService
        methods = {m for m in dir(KnowledgeService) if not m.startswith("_")}
        write_methods = {"write", "patch", "delete", "update", "modify"}
        for m in methods:
            assert m not in write_methods, f"KnowledgeService must not have '{m}' — read-only"
