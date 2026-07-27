"""Tests: Evolution Engine — proposal lifecycle, candidate collection, approval boundary."""
import json
import pytest
from src.nexara_prime.brain.evolution_engine import (
    EvolutionController,
)


_LAYER_MAP = {"preference": "semantic", "experience": "episodic", "procedural": "procedural"}


class MockMC:
    def __init__(self):
        self.store: dict[str, list[dict]] = {}

    def commit(self, *a, **kw):
        mid = kw.get("mission_id", a[0] if a else "")
        key = kw.get("key", a[1] if len(a) > 1 else "")
        content = kw.get("content", a[2] if len(a) > 2 else "")
        kind = kw.get("kind", a[3] if len(a) > 3 else "")
        ev = kw.get("evidence_id", a[4] if len(a) > 4 else None)
        conf = kw.get("confidence", a[5] if len(a) > 5 else 1.0)
        self.store.setdefault(mid, []).append({
            "mission_id": mid, "key": key, "content": content,
            "kind": kind, "layer": _LAYER_MAP.get(kind, kind),
            "evidence_id": ev or "", "confidence": conf,
            "status": "active", "weight": conf,
        })
        return f"cid_{len(self.store.get(mid, []))}"

    def recall(self, mid, layer=None, **kw):
        res = []
        for m, recs in self.store.items():
            if mid != "global" and m != mid:
                continue
            for r in recs:
                if r["status"] != "active":
                    continue
                if layer is not None and r.get("layer") != layer:
                    continue
                res.append(r)
        return res

    def rank_retrieve(self, query, top_k=10, layers=None, min_confidence=0.3, **kw):
        res = []
        for recs in self.store.values():
            for r in recs:
                if r["status"] != "active":
                    continue
                if layers and r.get("layer") not in layers:
                    continue
                if float(r.get("confidence", 1)) < min_confidence:
                    continue
                if any(w.lower() in str(r).lower() for w in query.lower().split()):
                    res.append(r)
        return res[:top_k]


def _seed_reflection(mc, mid="m1", content=None):
    if content is None:
        content = json.dumps({"success_signal": 0.8, "failure_signal": 0.2, "lessons": ["test"]})
    mc.commit(mission_id=mid, key=f"reflection:{mid}", content=content, kind="experience", confidence=0.7)


def _seed_experience_failure(mc, mid="m2", action="bad_tool failure"):
    mc.commit(mission_id=mid, key=f"exp:{mid}:e1", content=json.dumps({"action": action, "success": False}), kind="experience", confidence=0.3)


def _seed_preference(mc):
    mc.commit(mission_id="global", key="pref:theme", content=json.dumps({"key": "theme", "value": "dark"}), kind="preference", confidence=0.8)


def _seed_insight(mc, mid="m3"):
    mc.commit(mission_id=mid, key="insight:m3", content=json.dumps({"recommended_strategy": "test"}), kind="procedural", confidence=0.6)


@pytest.fixture
def mc():
    return MockMC()


@pytest.fixture
def controller(mc):
    return EvolutionController(mc)


class TestProposalCreation:
    def test_create_proposal(self, controller):
        p = controller._make_proposal("Reflection", "Memory", "Improve memory")
        assert p.source_type == "Reflection"
        assert p.target_area == "Memory"
        assert p.status == "DRAFT"


class TestCandidateCollection:
    def test_collect_from_reflections(self, controller, mc):
        _seed_reflection(mc)
        candidates = controller.collect_candidates()
        assert any(p.source_type == "Reflection" for p in candidates)

    def test_collect_from_failures(self, controller, mc):
        _seed_experience_failure(mc)
        candidates = controller.collect_candidates()
        assert any(p.source_type == "Experience" for p in candidates)

    def test_collect_from_preferences(self, controller, mc):
        _seed_preference(mc)
        candidates = controller.collect_candidates()
        assert any(p.source_type == "Preference" for p in candidates)

    def test_collect_from_intelligence(self, controller, mc):
        _seed_insight(mc)
        candidates = controller.collect_candidates()
        assert any(p.source_type == "Mission_Intelligence" for p in candidates)

    def test_collect_empty(self, controller):
        assert controller.collect_candidates() == []


class TestEvaluation:
    def test_evaluate_high_risk(self, controller):
        p = controller._make_proposal("Reflection", "Memory", "change", confidence=0.2)
        p.risk_score = 0.8
        result = controller.evaluate_proposal(p)
        assert result.status == "DRAFT"

    def test_evaluate_medium_risk(self, controller):
        p = controller._make_proposal("Reflection", "Memory", "change", confidence=0.6)
        p.risk_score = 0.5
        result = controller.evaluate_proposal(p)
        assert result.status == "APPROVAL_REQUIRED"
        assert result.approval_required

    def test_evaluate_low_risk(self, controller):
        p = controller._make_proposal("Reflection", "Memory", "change", confidence=0.8)
        p.risk_score = 0.2
        result = controller.evaluate_proposal(p)
        assert result.status == "APPROVED"
        assert not result.approval_required


class TestApprovalBoundary:
    def test_require_approval_high_risk(self, controller):
        p = controller._make_proposal("R", "M", "c", confidence=0.2)
        p.risk_score = 0.8
        assert controller.require_approval(p)

    def test_require_approval_low_risk(self, controller):
        p = controller._make_proposal("R", "M", "c", confidence=0.8)
        p.risk_score = 0.1
        p.approval_required = False
        assert not controller.require_approval(p)


class TestApplyFlow:
    def test_apply_approved(self, controller, mc):
        p = controller._make_proposal("R", "M", "apply", confidence=0.9)
        p.status = "APPROVED"
        result = controller.apply_evolution(p)
        assert result.status == "APPLIED"

    def test_apply_non_approved(self, controller):
        p = controller._make_proposal("R", "M", "x")
        result = controller.apply_evolution(p)
        assert result.status == "DRAFT"

    def test_reject_proposal(self, controller):
        p = controller._make_proposal("R", "M", "x")
        p.status = "APPROVAL_REQUIRED"
        result = controller.reject_proposal(p)
        assert result.status == "DRAFT"
        assert result.risk_score > 0.5

    def test_verify_applied(self, controller, mc):
        p = controller._make_proposal("R", "M", "verify", confidence=0.9)
        p.status = "APPLIED"
        result = controller.verify_evolution(p)
        assert result.status == "VERIFIED"

    def test_archive_verified(self, controller, mc):
        p = controller._make_proposal("R", "M", "archive", confidence=0.9)
        p.status = "VERIFIED"
        result = controller.archive_evolution(p)
        assert result.status == "ARCHIVED"


class TestEvolutionHistory:
    def test_record_and_retrieve(self, controller, mc):
        p = controller._make_proposal("Reflection", "Memory", "hist", confidence=0.9)
        p.status = "VERIFIED"
        controller._record_proposal(p)
        history = controller.get_evolution_history()
        assert len(history) >= 1

    def test_summarize(self, controller, mc):
        p = controller._make_proposal("Reflection", "Memory", "s1", confidence=0.9)
        p.status = "VERIFIED"
        controller._record_proposal(p)
        s = controller.summarize()
        assert s["total_proposals"] >= 1


class TestProposalLifecycle:
    def test_full_lifecycle(self, controller, mc):
        p = controller._make_proposal("Reflection", "Memory", "full cycle", confidence=0.8)
        p.risk_score = 0.2
        p.approval_required = False
        # evaluate
        p = controller.evaluate_proposal(p)
        assert p.status == "APPROVED"
        # apply
        p = controller.apply_evolution(p)
        assert p.status == "APPLIED"
        # verify
        p = controller.verify_evolution(p)
        assert p.status == "VERIFIED"
        # archive
        p = controller.archive_evolution(p)
        assert p.status == "ARCHIVED"
        # retrieve
        history = controller.get_evolution_history()
        assert len(history) >= 1
        


class TestEdgeCases:
    def test_verify_non_applied(self, controller):
        p = controller._make_proposal("R", "M", "x")
        p.status = "DRAFT"
        result = controller.verify_evolution(p)
        assert result.status == "DRAFT"

    def test_archive_non_verified(self, controller):
        p = controller._make_proposal("R", "M", "x")
        p.status = "DRAFT"
        result = controller.archive_evolution(p)
        assert result.status == "ARCHIVED"
        # archive accepts any status

    def test_evaluate_boundary_confidence(self, controller):
        p = controller._make_proposal("R", "M", "x", confidence=0.05)
        result = controller.evaluate_proposal(p)
        assert result.status == "DRAFT"

    def test_evaluate_boundary_risk(self, controller):
        p = controller._make_proposal("R", "M", "x", confidence=0.8)
        p.risk_score = 0.85
        result = controller.evaluate_proposal(p)
        assert result.status == "DRAFT"
